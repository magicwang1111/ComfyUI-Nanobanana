import unittest

from _loader import import_module

import torch

capabilities = import_module("py.api.capabilities")


class CapabilityTests(unittest.TestCase):
    def test_validate_nano_banana_rejects_resolution(self):
        with self.assertRaises(ValueError):
            capabilities.validate_generation_request(
                "gemini-2.5-flash-image",
                prompt="test",
                resolution="2K",
            )

    def test_validate_nano_banana_2_accepts_thoughts(self):
        spec = capabilities.validate_generation_request(
            "gemini-3.1-flash-image-preview",
            prompt="test",
            resolution="2K",
            thinking_level="medium",
            include_thoughts=True,
        )
        self.assertTrue(spec["supports_include_thoughts"])

    def test_validate_input_image_limit(self):
        images = torch.zeros((4, 8, 8, 3), dtype=torch.float32)
        with self.assertRaises(ValueError):
            capabilities.validate_generation_request(
                "gemini-2.5-flash-image",
                prompt="test",
                images=images,
            )


if __name__ == "__main__":
    unittest.main()
