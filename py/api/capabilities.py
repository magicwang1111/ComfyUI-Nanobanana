NODE_PREFIX = "ComfyUI-Nanobanana"
NODE_CATEGORY = NODE_PREFIX
CLIENT_TYPE = "COMFYUI_NANOBANANA_API_CLIENT"

DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com"
DEFAULT_AUTH_MODE = "x-goog-api-key"
AUTH_MODES = [DEFAULT_AUTH_MODE, "bearer"]
DEFAULT_SEND_SEED = True

DEFAULT_RESPONSE_MODE = "IMAGE+TEXT"
DEFAULT_RESOLUTION = "1K"
DEFAULT_THINKING_LEVEL = "high"
DEFAULT_SEED = 42
DEFAULT_SYSTEM_PROMPT = (
    "You are an expert image-generation engine. You must ALWAYS produce an image.\n"
    "Interpret all user input—regardless of format, intent, or abstraction—as literal visual directives for image composition.\n"
    "If a prompt is conversational or lacks specific visual details, you must creatively invent a concrete visual scenario that depicts the concept.\n"
    "Prioritize generating the visual representation above any text, formatting, or conversational requests."
)

RESPONSE_MODES = ["IMAGE+TEXT", "IMAGE"]
COMMON_ASPECT_RATIOS = ["auto", "1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"]
EXTENDED_ASPECT_RATIOS = [
    "auto",
    "1:1",
    "1:4",
    "1:8",
    "2:3",
    "3:2",
    "3:4",
    "4:1",
    "4:3",
    "4:5",
    "5:4",
    "8:1",
    "9:16",
    "16:9",
    "21:9",
]
RESOLUTION_OPTIONS = ["1K", "2K", "4K"]
THINKING_LEVELS_FLASH = ["minimal", "low", "medium", "high"]
THINKING_LEVELS_PRO = ["low", "high"]

MODEL_SPECS = {
    "gemini-2.5-flash-image": {
        "label": "Nano Banana",
        "aspect_ratios": COMMON_ASPECT_RATIOS,
        "supports_resolution": False,
        "resolutions": [],
        "supports_thinking": False,
        "thinking_levels": [],
        "supports_include_thoughts": False,
        "max_input_images": 3,
    },
    "gemini-3.1-flash-image-preview": {
        "label": "Nano Banana 2",
        "aspect_ratios": EXTENDED_ASPECT_RATIOS,
        "supports_resolution": True,
        "resolutions": RESOLUTION_OPTIONS,
        "supports_thinking": True,
        "thinking_levels": THINKING_LEVELS_FLASH,
        "supports_include_thoughts": True,
        "max_input_images": 14,
    },
    "gemini-3-pro-image-preview": {
        "label": "Nano Banana Pro",
        "aspect_ratios": EXTENDED_ASPECT_RATIOS,
        "supports_resolution": True,
        "resolutions": RESOLUTION_OPTIONS,
        "supports_thinking": True,
        "thinking_levels": THINKING_LEVELS_PRO,
        "supports_include_thoughts": False,
        "max_input_images": 14,
    },
}


def get_model_spec(model_name):
    if model_name not in MODEL_SPECS:
        raise ValueError(f"Unsupported Nano Banana model: {model_name}")
    return MODEL_SPECS[model_name]


def _count_input_images(images):
    if images is None:
        return 0

    shape = getattr(images, "shape", None)
    if shape is None:
        raise ValueError("images must be a ComfyUI IMAGE tensor.")

    if len(shape) == 3:
        return 1
    if len(shape) == 4:
        return int(shape[0])

    raise ValueError("images must be a 3D or 4D tensor.")


def validate_generation_request(
    model_name,
    prompt,
    images=None,
    aspect_ratio="auto",
    response_mode=DEFAULT_RESPONSE_MODE,
    seed=None,
    resolution=None,
    thinking_level=None,
    include_thoughts=False,
    system_prompt=None,
):
    spec = get_model_spec(model_name)

    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt is required.")

    if aspect_ratio not in spec["aspect_ratios"]:
        raise ValueError(
            f"Model {model_name} only supports aspect ratios: {', '.join(spec['aspect_ratios'])}."
        )

    if response_mode not in RESPONSE_MODES:
        raise ValueError(f"response_mode must be one of: {', '.join(RESPONSE_MODES)}.")

    if seed is not None:
        if not isinstance(seed, int):
            raise ValueError("seed must be an integer.")
        if seed < 0:
            raise ValueError("seed must be greater than or equal to 0.")

    image_count = _count_input_images(images)
    if image_count > spec["max_input_images"]:
        raise ValueError(
            f"Model {model_name} supports at most {spec['max_input_images']} input images in this node."
        )

    if system_prompt is not None and not isinstance(system_prompt, str):
        raise ValueError("system_prompt must be a string.")

    if resolution is not None:
        if not spec["supports_resolution"]:
            raise ValueError(f"Model {model_name} does not support resolution selection.")
        if resolution not in spec["resolutions"]:
            raise ValueError(
                f"Model {model_name} only supports resolutions: {', '.join(spec['resolutions'])}."
            )

    if thinking_level is not None:
        if not spec["supports_thinking"]:
            raise ValueError(f"Model {model_name} does not support thinking configuration.")
        if thinking_level not in spec["thinking_levels"]:
            raise ValueError(
                f"Model {model_name} only supports thinking levels: {', '.join(spec['thinking_levels'])}."
            )

    if include_thoughts and not spec["supports_include_thoughts"]:
        raise ValueError(f"Model {model_name} does not support include_thoughts.")

    return spec
