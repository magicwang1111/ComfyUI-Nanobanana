import base64
import copy
import io

import numpy
import PIL.Image
import torch

from .capabilities import DEFAULT_RESPONSE_MODE


def empty_image_tensor(size=64):
    return torch.zeros((1, size, size, 3), dtype=torch.float32)


def _tensor_to_pil_images(images):
    if images is None:
        return []

    if not isinstance(images, torch.Tensor):
        raise ValueError("images must be a torch.Tensor.")

    if images.ndim == 3:
        images = images.unsqueeze(0)
    elif images.ndim != 4:
        raise ValueError("images must be a 3D or 4D tensor.")

    np_images = numpy.clip(images.detach().cpu().numpy() * 255.0, 0.0, 255.0).astype(numpy.uint8)
    return [PIL.Image.fromarray(np_image, mode="RGB") for np_image in np_images]


def _pil_images_to_tensor(images):
    if not images:
        raise ValueError("At least one image is required to build an IMAGE tensor.")

    tensors = []
    for image in images:
        rgb_image = image.convert("RGB")
        image_np = numpy.array(rgb_image).astype(numpy.float32) / 255.0
        tensors.append(torch.from_numpy(image_np))
    return torch.stack(tensors)


def _encode_image_to_base64(image):
    bytes_io = io.BytesIO()
    image.save(bytes_io, format="PNG")
    return base64.b64encode(bytes_io.getvalue()).decode("utf-8")


def build_generation_payload(
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
    parts = [{"text": prompt.strip()}]
    for image in _tensor_to_pil_images(images):
        parts.append(
            {
                "inlineData": {
                    "mimeType": "image/png",
                    "data": _encode_image_to_base64(image),
                }
            }
        )

    generation_config = {
        "responseModalities": ["IMAGE"] if response_mode == "IMAGE" else ["TEXT", "IMAGE"],
    }
    if seed is not None:
        generation_config["seed"] = seed

    image_config = {}
    if aspect_ratio and aspect_ratio != "auto":
        image_config["aspectRatio"] = aspect_ratio
    if resolution:
        image_config["imageSize"] = resolution
    if image_config:
        generation_config["imageConfig"] = image_config

    thinking_config = {}
    if thinking_level:
        thinking_config["thinkingLevel"] = thinking_level.capitalize()
    if include_thoughts:
        thinking_config["includeThoughts"] = True
    if thinking_config:
        generation_config["thinkingConfig"] = thinking_config

    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": generation_config,
    }
    cleaned_system_prompt = system_prompt.strip() if isinstance(system_prompt, str) else ""
    if cleaned_system_prompt:
        payload["systemInstruction"] = {
            "parts": [{"text": cleaned_system_prompt}],
            "role": None,
        }
    return payload


def _sanitize_payload(value, parent_key=None):
    if isinstance(value, dict):
        sanitized = {}
        for key, item in value.items():
            if key == "data" and parent_key in {"inlineData", "inline_data"} and isinstance(item, str):
                sanitized[key] = f"<base64 omitted ({len(item)} chars)>"
            else:
                sanitized[key] = _sanitize_payload(item, key)
        return sanitized

    if isinstance(value, list):
        return [_sanitize_payload(item, parent_key) for item in value]

    return value


def sanitize_response_for_debug(response_payload):
    return _sanitize_payload(copy.deepcopy(response_payload))


def _decode_inline_image(part):
    inline_data = part.get("inlineData") or part.get("inline_data")
    if not isinstance(inline_data, dict):
        return None

    mime_type = inline_data.get("mimeType") or inline_data.get("mime_type") or ""
    data = inline_data.get("data")
    if not isinstance(data, str) or not mime_type.startswith("image/"):
        return None

    image_bytes = base64.b64decode(data)
    with io.BytesIO(image_bytes) as bytes_io:
        return PIL.Image.open(bytes_io).convert("RGB")


def extract_generation_output(response_payload):
    text_parts = []
    result_images = []
    thought_images = []

    for candidate in response_payload.get("candidates", []):
        content = candidate.get("content", {})
        for part in content.get("parts", []):
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                text_parts.append(text.strip())

            image = _decode_inline_image(part)
            if image is None:
                continue

            if part.get("thought") is True:
                thought_images.append(image)
            else:
                result_images.append(image)

    joined_text = "\n".join(text_parts).strip()
    if not result_images:
        if joined_text:
            raise ValueError(f"Gemini did not generate an image. Model response: {joined_text}")
        raise ValueError("Gemini did not generate an image for this request.")

    return {
        "images": _pil_images_to_tensor(result_images),
        "thought_images": _pil_images_to_tensor(thought_images) if thought_images else None,
        "text": joined_text,
    }
