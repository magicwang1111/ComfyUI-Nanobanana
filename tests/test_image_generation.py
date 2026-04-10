import base64
import io
import unittest

import PIL.Image

from _loader import import_module

import torch

image_generation = import_module("py.api.image_generation")


def _make_base64_png(color):
    image = PIL.Image.new("RGB", (4, 4), color=color)
    bytes_io = io.BytesIO()
    image.save(bytes_io, format="PNG")
    return base64.b64encode(bytes_io.getvalue()).decode("utf-8")


class ImageGenerationTests(unittest.TestCase):
    def test_build_payload_includes_images_and_config(self):
        images = torch.zeros((2, 8, 8, 3), dtype=torch.float32)
        payload = image_generation.build_generation_payload(
            prompt="hello",
            images=images,
            aspect_ratio="16:9",
            response_mode="IMAGE+TEXT",
            seed=123,
            resolution="2K",
            thinking_level="high",
            include_thoughts=True,
            system_prompt="system text",
        )

        self.assertEqual(payload["contents"][0]["parts"][0]["text"], "hello")
        self.assertEqual(len(payload["contents"][0]["parts"]), 3)
        self.assertEqual(payload["generationConfig"]["seed"], 123)
        self.assertEqual(payload["generationConfig"]["imageConfig"]["aspectRatio"], "16:9")
        self.assertEqual(payload["generationConfig"]["imageConfig"]["imageSize"], "2K")
        self.assertTrue(payload["generationConfig"]["thinkingConfig"]["includeThoughts"])
        self.assertEqual(payload["generationConfig"]["thinkingConfig"]["thinkingLevel"], "High")
        self.assertEqual(payload["systemInstruction"]["parts"][0]["text"], "system text")

    def test_build_payload_omits_blank_system_prompt(self):
        payload = image_generation.build_generation_payload(
            prompt="hello",
            system_prompt="   ",
        )
        self.assertNotIn("systemInstruction", payload)

    def test_extract_generation_output_splits_thought_images(self):
        response_payload = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "done"},
                            {
                                "inlineData": {
                                    "mimeType": "image/png",
                                    "data": _make_base64_png((255, 0, 0)),
                                }
                            },
                            {
                                "thought": True,
                                "inlineData": {
                                    "mimeType": "image/png",
                                    "data": _make_base64_png((0, 255, 0)),
                                }
                            }
                        ]
                    }
                }
            ]
        }

        output = image_generation.extract_generation_output(response_payload)
        self.assertEqual(tuple(output["images"].shape), (1, 4, 4, 3))
        self.assertEqual(tuple(output["thought_images"].shape), (1, 4, 4, 3))
        self.assertEqual(output["text"], "done")

    def test_sanitize_response_replaces_base64(self):
        payload = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "inlineData": {
                                    "mimeType": "image/png",
                                    "data": "abc123",
                                }
                            }
                        ]
                    }
                }
            ]
        }

        sanitized = image_generation.sanitize_response_for_debug(payload)
        part = sanitized["candidates"][0]["content"]["parts"][0]["inlineData"]["data"]
        self.assertIn("base64 omitted", part)


if __name__ == "__main__":
    unittest.main()
