import configparser
import json
import os
from pathlib import Path

from .api import (
    CLIENT_TYPE,
    DEFAULT_RESPONSE_MODE,
    DEFAULT_RESOLUTION,
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


def _load_config_api_key():
    config = configparser.ConfigParser()
    config.read(CONFIG_PATH)
    return config.get("API", "GEMINI_API_KEY", fallback="").strip()


def _resolve_api_key(explicit_api_key):
    if isinstance(explicit_api_key, str) and explicit_api_key.strip():
        return explicit_api_key.strip()

    env_api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if env_api_key:
        return env_api_key

    config_api_key = _load_config_api_key()
    if config_api_key:
        return config_api_key

    raise ValueError(
        "GEMINI_API_KEY is required. Fill it in the Client node, set the GEMINI_API_KEY environment "
        "variable, or add it to config.ini."
    )


def _raise_with_api_guidance(exc):
    if exc.status_code in {401, 403}:
        raise ValueError(
            f"Gemini API rejected the request with {exc.status_code} {exc.status or 'ERROR'}. "
            "Check that the API key is valid, billing is enabled, and the selected Nano Banana model "
            "is available for this project."
        ) from exc

    if exc.status_code == 429:
        raise ValueError(
            "Gemini API rate limit exceeded (429). Wait and retry, or use a project with higher quota."
        ) from exc

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
            }
        }

    RETURN_TYPES = (CLIENT_TYPE,)
    RETURN_NAMES = ("client",)
    FUNCTION = "create_client"
    OUTPUT_NODE = False
    CATEGORY = NODE_CATEGORY

    def create_client(self, api_key, request_timeout):
        resolved_api_key = _resolve_api_key(api_key)
        client = Client(resolved_api_key, timeout=request_timeout)
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
            "aspect_ratio": (spec["aspect_ratios"], {"default": "auto"}),
            "response_mode": (RESPONSE_MODES, {"default": DEFAULT_RESPONSE_MODE}),
        }
        optional = {
            "images": ("IMAGE",),
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
        aspect_ratio,
        response_mode,
        images=None,
        resolution=None,
        thinking_level=None,
        include_thoughts=False,
    ):
        validate_generation_request(
            self.MODEL_NAME,
            prompt=prompt,
            images=images,
            aspect_ratio=aspect_ratio,
            response_mode=response_mode,
            resolution=resolution,
            thinking_level=thinking_level,
            include_thoughts=include_thoughts,
        )

        payload = build_generation_payload(
            prompt=prompt,
            images=images,
            aspect_ratio=aspect_ratio,
            response_mode=response_mode,
            resolution=resolution,
            thinking_level=thinking_level,
            include_thoughts=include_thoughts,
        )

        try:
            response_payload = client.generate_content(self.MODEL_NAME, payload)
        except NanoBananaAPIError as exc:
            _raise_with_api_guidance(exc)

        print(f"[ComfyUI-Nanobanana] {self.MODEL_NAME} request completed")
        parsed_output = extract_generation_output(response_payload)
        return parsed_output, _build_response_json(response_payload)


class NanoBanana25Node(_BaseNanoBananaNode):
    MODEL_NAME = "gemini-2.5-flash-image"

    RETURN_TYPES = ("IMAGE", "STRING", "STRING")
    RETURN_NAMES = ("image", "text", "response_json")

    def generate(self, client, prompt, aspect_ratio="auto", response_mode=DEFAULT_RESPONSE_MODE, images=None):
        parsed_output, response_json = self._execute_request(
            client=client,
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            response_mode=response_mode,
            images=images,
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
        aspect_ratio="auto",
        response_mode=DEFAULT_RESPONSE_MODE,
        images=None,
        resolution=DEFAULT_RESOLUTION,
        thinking_level=DEFAULT_THINKING_LEVEL,
        include_thoughts=False,
    ):
        parsed_output, response_json = self._execute_request(
            client=client,
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            response_mode=response_mode,
            images=images,
            resolution=resolution,
            thinking_level=thinking_level,
            include_thoughts=include_thoughts,
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
        aspect_ratio="auto",
        response_mode=DEFAULT_RESPONSE_MODE,
        images=None,
        resolution=DEFAULT_RESOLUTION,
        thinking_level=DEFAULT_THINKING_LEVEL,
    ):
        parsed_output, response_json = self._execute_request(
            client=client,
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            response_mode=response_mode,
            images=images,
            resolution=resolution,
            thinking_level=thinking_level,
        )
        return (parsed_output["images"], parsed_output["text"], response_json)
