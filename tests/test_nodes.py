import base64
import io
import unittest

import PIL.Image

from _loader import import_module

nodes = import_module("py.nodes")


def _make_base64_png(color):
    image = PIL.Image.new("RGB", (4, 4), color=color)
    bytes_io = io.BytesIO()
    image.save(bytes_io, format="PNG")
    return base64.b64encode(bytes_io.getvalue()).decode("utf-8")


class FakeClient:
    def __init__(self, send_seed=True, base_url="https://generativelanguage.googleapis.com"):
        self.calls = []
        self.send_seed = send_seed
        self.base_url = base_url

    def generate_content(self, model_name, payload):
        self.calls.append((model_name, payload))
        return {
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
                        ]
                    }
                }
            ]
        }


class ModelOverrideTests(unittest.TestCase):
    def test_blank_model_override_uses_builtin_model_name(self):
        client = FakeClient()

        nodes.NanoBanana25Node().generate(
            client,
            "hello",
            model_override="",
        )

        self.assertEqual(client.calls[0][0], "gemini-2.5-flash-image")

    def test_model_override_only_changes_outbound_model_name(self):
        client = FakeClient()

        nodes.NanoBanana31Node().generate(
            client,
            "hello",
            resolution="2K",
            thinking_level="medium",
            include_thoughts=True,
            model_override="relay-gemini-image",
        )

        request_model_name, payload = client.calls[0]
        self.assertEqual(request_model_name, "relay-gemini-image")
        self.assertEqual(payload["generationConfig"]["imageConfig"]["imageSize"], "2K")
        self.assertEqual(payload["generationConfig"]["thinkingConfig"]["thinkingLevel"], "Medium")
        self.assertTrue(payload["generationConfig"]["thinkingConfig"]["includeThoughts"])

    def test_client_can_disable_seed_forwarding(self):
        client = FakeClient(send_seed=False)

        nodes.NanoBanana25Node().generate(
            client,
            "hello",
            seed=123,
        )

        _, payload = client.calls[0]
        self.assertNotIn("seed", payload["generationConfig"])

    def test_aihubmix_pro_strips_explicit_thinking_level(self):
        client = FakeClient(base_url="https://aihubmix.com/gemini")

        nodes.NanoBananaProNode().generate(
            client,
            "hello",
            resolution="2K",
            thinking_level="high",
        )

        _, payload = client.calls[0]
        self.assertNotIn("thinkingConfig", payload["generationConfig"])

    def test_aihubmix_nano_banana_2_keeps_thinking_level(self):
        client = FakeClient(base_url="https://aihubmix.com/gemini")

        nodes.NanoBanana31Node().generate(
            client,
            "hello",
            resolution="2K",
            thinking_level="medium",
        )

        _, payload = client.calls[0]
        self.assertEqual(payload["generationConfig"]["thinkingConfig"]["thinkingLevel"], "Medium")

    def test_non_aihubmix_pro_keeps_thinking_level(self):
        client = FakeClient(base_url="https://relay.example.com")

        nodes.NanoBananaProNode().generate(
            client,
            "hello",
            resolution="2K",
            thinking_level="high",
        )

        _, payload = client.calls[0]
        self.assertEqual(payload["generationConfig"]["thinkingConfig"]["thinkingLevel"], "High")


if __name__ == "__main__":
    unittest.main()
