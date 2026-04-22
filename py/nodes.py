import asyncio
import configparser
import json
import os
from pathlib import Path

from .api import (
    DEFAULT_AUTH_MODE,
    DEFAULT_BASE_URL,
    DEFAULT_RESPONSE_MODE,
    DEFAULT_RESOLUTION,
    DEFAULT_SEED,
    DEFAULT_SEND_SEED,
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_THINKING_LEVEL,
    RESPONSE_MODES,
    AsyncClient,
    Client,
    NanoBananaAPIError,
    apply_generation_payload_rules,
    build_generation_payload,
    empty_image_tensor,
    extract_generation_output,
    get_model_spec,
    sanitize_response_for_debug,
    validate_generation_request,
)
from .api.capabilities import NODE_CATEGORY
import torch

ROOT_DIR = Path(__file__).resolve().parents[1]
CONFIG_JSON_PATH = ROOT_DIR / "config.local.json"
LEGACY_CONFIG_PATH = ROOT_DIR / "config.ini"
LEGACY_CONFIG_SECTION = "API"
DEFAULT_REQUEST_TIMEOUT = 60


def _load_legacy_config_value(*keys):
    config = configparser.ConfigParser()
    config.read(LEGACY_CONFIG_PATH, encoding="utf-8")
    for key in keys:
        value = config.get(LEGACY_CONFIG_SECTION, key, fallback="").strip()
        if value:
            return value
    return ""


def _load_legacy_api_key():
    return _load_legacy_config_value("NANOBANANA_API_KEY", "GEMINI_API_KEY")


def _load_legacy_base_url():
    return _load_legacy_config_value("NANOBANANA_BASE_URL")


def _load_legacy_auth_mode():
    return _load_legacy_config_value("NANOBANANA_AUTH_MODE")


def _load_legacy_send_seed():
    return _load_legacy_config_value("NANOBANANA_SEND_SEED")


def _load_json_config():
    if not CONFIG_JSON_PATH.exists():
        return {}

    try:
        with CONFIG_JSON_PATH.open("r", encoding="utf-8") as handle:
            config_data = json.load(handle)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{CONFIG_JSON_PATH.name} is not valid JSON: {exc}") from exc
    except OSError as exc:
        raise ValueError(f"Failed to read {CONFIG_JSON_PATH.name}: {exc}") from exc

    if not isinstance(config_data, dict):
        raise ValueError(f"{CONFIG_JSON_PATH.name} must contain a top-level JSON object.")

    return config_data


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


def _parse_timeout(value):
    if isinstance(value, bool):
        raise ValueError("request_timeout must be an integer.")

    if isinstance(value, int):
        timeout = value
    else:
        try:
            timeout = int(str(value).strip())
        except (TypeError, ValueError) as exc:
            raise ValueError("request_timeout must be an integer.") from exc

    if timeout < 5:
        raise ValueError("request_timeout must be greater than or equal to 5.")

    return timeout


def _json_value_present(config_data, key):
    if key not in config_data:
        return False

    value = config_data[key]
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def _resolve_api_key(config_data):
    if _json_value_present(config_data, "api_key"):
        return str(config_data["api_key"]).strip()

    env_api_key = _load_env_value("NANOBANANA_API_KEY", "GEMINI_API_KEY")
    if env_api_key:
        return env_api_key

    legacy_api_key = _load_legacy_api_key()
    if legacy_api_key:
        return legacy_api_key

    raise ValueError(
        "An API key is required. Add api_key to config.local.json, set NANOBANANA_API_KEY or GEMINI_API_KEY, "
        "or add NANOBANANA_API_KEY / GEMINI_API_KEY to config.ini."
    )


def _resolve_base_url(config_data):
    if _json_value_present(config_data, "base_url"):
        return str(config_data["base_url"]).strip().rstrip("/")

    env_base_url = _load_env_value("NANOBANANA_BASE_URL")
    if env_base_url:
        return env_base_url.rstrip("/")

    legacy_base_url = _load_legacy_base_url()
    if legacy_base_url:
        return legacy_base_url.rstrip("/")

    return DEFAULT_BASE_URL


def _resolve_auth_mode(config_data):
    if _json_value_present(config_data, "auth_mode"):
        return Client.normalize_auth_mode(str(config_data["auth_mode"]).strip())

    env_auth_mode = _load_env_value("NANOBANANA_AUTH_MODE")
    if env_auth_mode:
        return Client.normalize_auth_mode(env_auth_mode)

    legacy_auth_mode = _load_legacy_auth_mode()
    if legacy_auth_mode:
        return Client.normalize_auth_mode(legacy_auth_mode)

    return DEFAULT_AUTH_MODE


def _resolve_send_seed(config_data):
    if _json_value_present(config_data, "send_seed"):
        return _parse_bool(config_data["send_seed"], "send_seed")

    env_send_seed = _load_env_value("NANOBANANA_SEND_SEED")
    if env_send_seed:
        return _parse_bool(env_send_seed, "NANOBANANA_SEND_SEED")

    legacy_send_seed = _load_legacy_send_seed()
    if legacy_send_seed:
        return _parse_bool(legacy_send_seed, "NANOBANANA_SEND_SEED")

    return DEFAULT_SEND_SEED


def _resolve_request_timeout(config_data):
    if _json_value_present(config_data, "request_timeout"):
        return _parse_timeout(config_data["request_timeout"])

    return DEFAULT_REQUEST_TIMEOUT


def _resolve_model_name(default_model_name, model_override):
    if model_override is None:
        return default_model_name
    if not isinstance(model_override, str):
        raise ValueError("model_override must be a string.")

    override = model_override.strip()
    return override or default_model_name


def _resolve_runtime_client_kwargs():
    config_data = _load_json_config()
    return {
        "api_key": _resolve_api_key(config_data),
        "timeout": _resolve_request_timeout(config_data),
        "base_url": _resolve_base_url(config_data),
        "auth_mode": _resolve_auth_mode(config_data),
        "send_seed": _resolve_send_seed(config_data),
    }


def _create_runtime_client():
    return Client(**_resolve_runtime_client_kwargs())


def _create_runtime_async_client():
    return AsyncClient(**_resolve_runtime_client_kwargs())


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


def _merge_image_tensors(images):
    valid_images = [image for image in images if image is not None]
    if not valid_images:
        return None
    if len(valid_images) == 1:
        return valid_images[0]
    return torch.cat(valid_images, dim=0)


def _merge_output_texts(texts):
    normalized = [text.strip() for text in texts if isinstance(text, str) and text.strip()]
    if not normalized:
        return ""
    if len(normalized) == 1:
        return normalized[0]
    return "\n\n".join(f"[request {index}] {text}" for index, text in enumerate(normalized, start=1))


def _build_response_json_list(response_payloads):
    if len(response_payloads) == 1:
        return _build_response_json(response_payloads[0])

    sanitized = [sanitize_response_for_debug(payload) for payload in response_payloads]
    return json.dumps(sanitized, ensure_ascii=False, indent=2)


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
            "prompt": ("STRING", {"multiline": True, "default": ""}),
            "seed": ("INT", {"default": DEFAULT_SEED, "min": 0, "max": 0xFFFFFFFFFFFFFFFF, "control_after_generate": True}),
            "aspect_ratio": (spec["aspect_ratios"], {"default": "auto"}),
            "response_mode": (RESPONSE_MODES, {"default": DEFAULT_RESPONSE_MODE}),
        }
        optional = {
            "images": ("IMAGE",),
            "system_prompt": ("STRING", {"multiline": True, "default": DEFAULT_SYSTEM_PROMPT}),
            "model_override": ("STRING", {"multiline": False, "default": ""}),
            "parallel_requests": ("INT", {"default": 1, "min": 1, "max": 8}),
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

    async def _execute_single_request(
        self,
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

        client = _create_runtime_async_client()
        try:
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
            payload = apply_generation_payload_rules(
                getattr(client, "base_url", ""),
                self.MODEL_NAME,
                request_model_name,
                payload,
            )

            try:
                response_payload = await client.generate_content(request_model_name, payload)
            except NanoBananaAPIError as exc:
                _raise_with_api_guidance(exc)
        finally:
            await client.close()

        print(f"[ComfyUI-Nanobanana] {request_model_name} request completed")
        return extract_generation_output(response_payload), response_payload

    async def _execute_request(
        self,
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
        parallel_requests=1,
    ):
        parallel_requests = int(parallel_requests)
        if parallel_requests < 1:
            raise ValueError("parallel_requests must be greater than or equal to 1.")

        tasks = []
        for request_index in range(parallel_requests):
            request_seed = seed + request_index if seed is not None else None
            tasks.append(
                self._execute_single_request(
                    prompt=prompt,
                    seed=request_seed,
                    aspect_ratio=aspect_ratio,
                    response_mode=response_mode,
                    images=images,
                    resolution=resolution,
                    thinking_level=thinking_level,
                    include_thoughts=include_thoughts,
                    system_prompt=system_prompt,
                    model_override=model_override,
                )
            )

        results = await asyncio.gather(*tasks)
        parsed_outputs = [item[0] for item in results]
        response_payloads = [item[1] for item in results]

        merged_output = {
            "images": _merge_image_tensors([output["images"] for output in parsed_outputs]),
            "thought_images": _merge_image_tensors([output["thought_images"] for output in parsed_outputs]),
            "text": _merge_output_texts([output["text"] for output in parsed_outputs]),
        }
        return merged_output, _build_response_json_list(response_payloads)


class NanoBanana25Node(_BaseNanoBananaNode):
    MODEL_NAME = "gemini-2.5-flash-image"

    RETURN_TYPES = ("IMAGE", "STRING", "STRING")
    RETURN_NAMES = ("image", "text", "response_json")

    async def generate(
        self,
        prompt,
        seed=DEFAULT_SEED,
        aspect_ratio="auto",
        response_mode=DEFAULT_RESPONSE_MODE,
        images=None,
        system_prompt=DEFAULT_SYSTEM_PROMPT,
        model_override="",
        parallel_requests=1,
    ):
        parsed_output, response_json = await self._execute_request(
            prompt=prompt,
            seed=seed,
            aspect_ratio=aspect_ratio,
            response_mode=response_mode,
            images=images,
            system_prompt=system_prompt,
            model_override=model_override,
            parallel_requests=parallel_requests,
        )
        return (parsed_output["images"], parsed_output["text"], response_json)


class NanoBanana31Node(_BaseNanoBananaNode):
    MODEL_NAME = "gemini-3.1-flash-image-preview"

    RETURN_TYPES = ("IMAGE", "STRING", "IMAGE", "STRING")
    RETURN_NAMES = ("image", "text", "thought_image", "response_json")

    async def generate(
        self,
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
        parallel_requests=1,
    ):
        parsed_output, response_json = await self._execute_request(
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
            parallel_requests=parallel_requests,
        )
        thought_images = parsed_output["thought_images"] or empty_image_tensor()
        return (parsed_output["images"], parsed_output["text"], thought_images, response_json)


class NanoBananaProNode(_BaseNanoBananaNode):
    MODEL_NAME = "gemini-3-pro-image-preview"

    RETURN_TYPES = ("IMAGE", "STRING", "STRING")
    RETURN_NAMES = ("image", "text", "response_json")

    async def generate(
        self,
        prompt,
        seed=DEFAULT_SEED,
        aspect_ratio="auto",
        response_mode=DEFAULT_RESPONSE_MODE,
        images=None,
        resolution=DEFAULT_RESOLUTION,
        thinking_level=DEFAULT_THINKING_LEVEL,
        system_prompt=DEFAULT_SYSTEM_PROMPT,
        model_override="",
        parallel_requests=1,
    ):
        parsed_output, response_json = await self._execute_request(
            prompt=prompt,
            seed=seed,
            aspect_ratio=aspect_ratio,
            response_mode=response_mode,
            images=images,
            resolution=resolution,
            thinking_level=thinking_level,
            system_prompt=system_prompt,
            model_override=model_override,
            parallel_requests=parallel_requests,
        )
        return (parsed_output["images"], parsed_output["text"], response_json)
