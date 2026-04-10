import configparser
import json
import os
from pathlib import Path

from .api import (
    AUTH_MODES,
    CLIENT_TYPE,
    DEFAULT_AUTH_MODE,
    DEFAULT_BASE_URL,
    DEFAULT_RESPONSE_MODE,
    DEFAULT_RESOLUTION,
    DEFAULT_SEED,
    DEFAULT_SEND_SEED,
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_THINKING_LEVEL,
    RESPONSE_MODES,
    Client,
    NanoBananaAPIError,
    build_generation_payload,
    empty_image_tensor,
    extract_generation_output,
    get_model_spec,
    sanitize_response_for_debug,
    validate_generation_request,
)
from .api.capabilities import NODE_CATEGORY

ROOT_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT_DIR / "config.ini"
CONFIG_SECTION = "API"


def _load_config_value(*keys):
    config = configparser.ConfigParser()
    config.read(CONFIG_PATH, encoding="utf-8")
    for key in keys:
        value = config.get(CONFIG_SECTION, key, fallback="").strip()
        if value:
            return value
    return ""


def _load_config_api_key():
    return _load_config_value("NANOBANANA_API_KEY", "GEMINI_API_KEY")


def _load_config_base_url():
    return _load_config_value("NANOBANANA_BASE_URL")


def _load_config_auth_mode():
    return _load_config_value("NANOBANANA_AUTH_MODE")


def _load_config_send_seed():
    return _load_config_value("NANOBANANA_SEND_SEED")


def _load_env_value(*keys):
    for key in keys:
        value = os.getenv(key, "").strip()
        if value:
            return value
    return ""


def _parse_bool(value, field_name):
    if isinstance(value, bool):
        return value

    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{field_name} must be a boolean value.")


def _resolve_api_key(explicit_api_key):
    if isinstance(explicit_api_key, str) and explicit_api_key.strip():
        return explicit_api_key.strip()

    env_api_key = _load_env_value("NANOBANANA_API_KEY", "GEMINI_API_KEY")
    if env_api_key:
        return env_api_key

    config_api_key = _load_config_api_key()
    if config_api_key:
        return config_api_key

    raise ValueError(
        "An API key is required. Fill it in the Client node, set NANOBANANA_API_KEY or GEMINI_API_KEY, "
        "or add NANOBANANA_API_KEY / GEMINI_API_KEY to config.ini."
    )


def _resolve_base_url(explicit_base_url):
    normalized_explicit = explicit_base_url.strip().rstrip("/") if isinstance(explicit_base_url, str) else ""
    if normalized_explicit and normalized_explicit != DEFAULT_BASE_URL:
        return normalized_explicit

    env_base_url = _load_env_value("NANOBANANA_BASE_URL")
    if env_base_url:
        return env_base_url.rstrip("/")

    config_base_url = _load_config_base_url()
    if config_base_url:
        return config_base_url.rstrip("/")

    return DEFAULT_BASE_URL


def _resolve_auth_mode(explicit_auth_mode):
    auth_mode = explicit_auth_mode.strip() if isinstance(explicit_auth_mode, str) else ""
    if not auth_mode or auth_mode == DEFAULT_AUTH_MODE:
        auth_mode = _load_env_value("NANOBANANA_AUTH_MODE")
    if not isinstance(auth_mode, str) or not auth_mode.strip():
        auth_mode = _load_config_auth_mode()
    if not isinstance(auth_mode, str) or not auth_mode.strip():
        auth_mode = DEFAULT_AUTH_MODE
    return Client.normalize_auth_mode(auth_mode)


def _resolve_send_seed(explicit_send_seed):
    if isinstance(explicit_send_seed, bool) and explicit_send_seed is not DEFAULT_SEND_SEED:
        return explicit_send_seed

    env_send_seed = _load_env_value("NANOBANANA_SEND_SEED")
    if env_send_seed:
        return _parse_bool(env_send_seed, "NANOBANANA_SEND_SEED")

    config_send_seed = _load_config_send_seed()
    if config_send_seed:
        return _parse_bool(config_send_seed, "NANOBANANA_SEND_SEED")

    return explicit_send_seed if isinstance(explicit_send_seed, bool) else DEFAULT_SEND_SEED


def _resolve_model_name(default_model_name, model_override):
    if model_override is None:
        return default_model_name
    if not isinstance(model_override, str):
        raise ValueError("model_override must be a string.")

    override = model_override.strip()
    return override or default_model_name


def _raise_with_api_guidance(exc):
    if exc.status_code in {401, 403}:
        raise ValueError(
            f"API request was rejected with {exc.status_code} {exc.status or 'ERROR'}. "
            "Check that api_key, base_url, auth_mode, billing, and the selected model are correct."
        ) from exc

    if exc.status_code == 429:
        raise ValueError("API rate limit exceeded (429). Wait and retry, or use a project with higher quota.") from exc

    raise ValueError(str(exc)) from exc


def _build_response_json(response_payload):
    sanitized = sanitize_response_for_debug(response_payload)
    return json.dumps(sanitized, ensure_ascii=False, indent=2)


class NanoBananaClientNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "api_key": ("STRING", {"multiline": False, "default": ""}),
                "request_timeout": ("INT", {"default": 60, "min": 5, "max": 300, "step": 1}),
                "base_url": ("STRING", {"multiline": False, "default": DEFAULT_BASE_URL}),
                "auth_mode": (AUTH_MODES, {"default": DEFAULT_AUTH_MODE}),
                "send_seed": ("BOOLEAN", {"default": DEFAULT_SEND_SEED}),
            }
        }

    RETURN_TYPES = (CLIENT_TYPE,)
    RETURN_NAMES = ("client",)
    FUNCTION = "create_client"
    OUTPUT_NODE = False
    CATEGORY = NODE_CATEGORY

    def create_client(self, api_key, request_timeout, base_url, auth_mode, send_seed):
        resolved_api_key = _resolve_api_key(api_key)
        resolved_base_url = _resolve_base_url(base_url)
        resolved_auth_mode = _resolve_auth_mode(auth_mode)
        resolved_send_seed = _resolve_send_seed(send_seed)
        client = Client(
            resolved_api_key,
            timeout=request_timeout,
            base_url=resolved_base_url,
            auth_mode=resolved_auth_mode,
            send_seed=resolved_send_seed,
        )
        return (client,)


class _BaseNanoBananaNode:
    MODEL_NAME = None
    OUTPUT_NODE = False
    CATEGORY = NODE_CATEGORY
    FUNCTION = "generate"

    @classmethod
    def _model_spec(cls):
        return get_model_spec(cls.MODEL_NAME)

    @classmethod
    def INPUT_TYPES(cls):
        spec = cls._model_spec()
        required = {
            "client": (CLIENT_TYPE,),
            "prompt": ("STRING", {"multiline": True, "default": ""}),
            "seed": ("INT", {"default": DEFAULT_SEED, "min": 0, "max": 0xFFFFFFFFFFFFFFFF, "control_after_generate": True}),
            "aspect_ratio": (spec["aspect_ratios"], {"default": "auto"}),
            "response_mode": (RESPONSE_MODES, {"default": DEFAULT_RESPONSE_MODE}),
        }
        optional = {
            "images": ("IMAGE",),
            "system_prompt": ("STRING", {"multiline": True, "default": DEFAULT_SYSTEM_PROMPT}),
            "model_override": ("STRING", {"multiline": False, "default": ""}),
        }

        if spec["supports_resolution"]:
            optional["resolution"] = (spec["resolutions"], {"default": DEFAULT_RESOLUTION})

        if spec["supports_thinking"]:
            default_thinking = DEFAULT_THINKING_LEVEL
            if default_thinking not in spec["thinking_levels"]:
                default_thinking = spec["thinking_levels"][-1]
            optional["thinking_level"] = (spec["thinking_levels"], {"default": default_thinking})

        if spec["supports_include_thoughts"]:
            optional["include_thoughts"] = ("BOOLEAN", {"default": False})

        return {"required": required, "optional": optional}

    def _execute_request(
        self,
        client,
        prompt,
        seed,
        aspect_ratio,
        response_mode,
        images=None,
        resolution=None,
        thinking_level=None,
        include_thoughts=False,
        system_prompt=DEFAULT_SYSTEM_PROMPT,
        model_override="",
    ):
        validate_generation_request(
            self.MODEL_NAME,
            prompt=prompt,
            images=images,
            aspect_ratio=aspect_ratio,
            response_mode=response_mode,
            seed=seed,
            resolution=resolution,
            thinking_level=thinking_level,
            include_thoughts=include_thoughts,
            system_prompt=system_prompt,
        )
        request_model_name = _resolve_model_name(self.MODEL_NAME, model_override)
        request_seed = seed if getattr(client, "send_seed", True) else None

        payload = build_generation_payload(
            prompt=prompt,
            images=images,
            aspect_ratio=aspect_ratio,
            response_mode=response_mode,
            seed=request_seed,
            resolution=resolution,
            thinking_level=thinking_level,
            include_thoughts=include_thoughts,
            system_prompt=system_prompt,
        )

        try:
            response_payload = client.generate_content(request_model_name, payload)
        except NanoBananaAPIError as exc:
            _raise_with_api_guidance(exc)

        print(f"[ComfyUI-Nanobanana] {request_model_name} request completed")
        parsed_output = extract_generation_output(response_payload)
        return parsed_output, _build_response_json(response_payload)


class NanoBanana25Node(_BaseNanoBananaNode):
    MODEL_NAME = "gemini-2.5-flash-image"

    RETURN_TYPES = ("IMAGE", "STRING", "STRING")
    RETURN_NAMES = ("image", "text", "response_json")

    def generate(
        self,
        client,
        prompt,
        seed=DEFAULT_SEED,
        aspect_ratio="auto",
        response_mode=DEFAULT_RESPONSE_MODE,
        images=None,
        system_prompt=DEFAULT_SYSTEM_PROMPT,
        model_override="",
    ):
        parsed_output, response_json = self._execute_request(
            client=client,
            prompt=prompt,
            seed=seed,
            aspect_ratio=aspect_ratio,
            response_mode=response_mode,
            images=images,
            system_prompt=system_prompt,
            model_override=model_override,
        )
        return (parsed_output["images"], parsed_output["text"], response_json)


class NanoBanana31Node(_BaseNanoBananaNode):
    MODEL_NAME = "gemini-3.1-flash-image-preview"

    RETURN_TYPES = ("IMAGE", "STRING", "IMAGE", "STRING")
    RETURN_NAMES = ("image", "text", "thought_image", "response_json")

    def generate(
        self,
        client,
        prompt,
        seed=DEFAULT_SEED,
        aspect_ratio="auto",
        response_mode=DEFAULT_RESPONSE_MODE,
        images=None,
        resolution=DEFAULT_RESOLUTION,
        thinking_level=DEFAULT_THINKING_LEVEL,
        include_thoughts=False,
        system_prompt=DEFAULT_SYSTEM_PROMPT,
        model_override="",
    ):
        parsed_output, response_json = self._execute_request(
            client=client,
            prompt=prompt,
            seed=seed,
            aspect_ratio=aspect_ratio,
            response_mode=response_mode,
            images=images,
            resolution=resolution,
            thinking_level=thinking_level,
            include_thoughts=include_thoughts,
            system_prompt=system_prompt,
            model_override=model_override,
        )
        thought_images = parsed_output["thought_images"] or empty_image_tensor()
        return (parsed_output["images"], parsed_output["text"], thought_images, response_json)


class NanoBananaProNode(_BaseNanoBananaNode):
    MODEL_NAME = "gemini-3-pro-image-preview"

    RETURN_TYPES = ("IMAGE", "STRING", "STRING")
    RETURN_NAMES = ("image", "text", "response_json")

    def generate(
        self,
        client,
        prompt,
        seed=DEFAULT_SEED,
        aspect_ratio="auto",
        response_mode=DEFAULT_RESPONSE_MODE,
        images=None,
        resolution=DEFAULT_RESOLUTION,
        thinking_level=DEFAULT_THINKING_LEVEL,
        system_prompt=DEFAULT_SYSTEM_PROMPT,
        model_override="",
    ):
        parsed_output, response_json = self._execute_request(
            client=client,
            prompt=prompt,
            seed=seed,
            aspect_ratio=aspect_ratio,
            response_mode=response_mode,
            images=images,
            resolution=resolution,
            thinking_level=thinking_level,
            system_prompt=system_prompt,
            model_override=model_override,
        )
        return (parsed_output["images"], parsed_output["text"], response_json)
