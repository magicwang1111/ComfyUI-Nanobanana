import base64
import io
import unittest
from unittest.mock import patch

import PIL.Image

from _loader import ensure_package_loaded, import_module

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
        self.closed = False

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

    def close(self):
        self.closed = True


class NodeExecutionTests(unittest.TestCase):
    def test_client_node_is_not_registered(self):
        package = ensure_package_loaded()

        self.assertNotIn("ComfyUI-Nanobanana Client", package.NODE_CLASS_MAPPINGS)

    def test_generation_nodes_do_not_require_client_input(self):
        nano_banana_inputs = nodes.NanoBanana25Node.INPUT_TYPES()
        nano_banana_2_inputs = nodes.NanoBanana31Node.INPUT_TYPES()
        nano_banana_pro_inputs = nodes.NanoBananaProNode.INPUT_TYPES()

        self.assertNotIn("client", nano_banana_inputs["required"])
        self.assertNotIn("client", nano_banana_2_inputs["required"])
        self.assertNotIn("client", nano_banana_pro_inputs["required"])

    def test_blank_model_override_uses_builtin_model_name(self):
        client = FakeClient()

        with patch.object(nodes, "_create_runtime_client", return_value=client):
            nodes.NanoBanana25Node().generate(
                "hello",
                model_override="",
            )

        self.assertEqual(client.calls[0][0], "gemini-2.5-flash-image")
        self.assertTrue(client.closed)

    def test_model_override_only_changes_outbound_model_name(self):
        client = FakeClient()

        with patch.object(nodes, "_create_runtime_client", return_value=client):
            nodes.NanoBanana31Node().generate(
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
        self.assertTrue(client.closed)

    def test_client_can_disable_seed_forwarding(self):
        client = FakeClient(send_seed=False)

        with patch.object(nodes, "_create_runtime_client", return_value=client):
            nodes.NanoBanana25Node().generate(
                "hello",
                seed=123,
            )

        _, payload = client.calls[0]
        self.assertNotIn("seed", payload["generationConfig"])
        self.assertTrue(client.closed)

    def test_aihubmix_pro_strips_explicit_thinking_level(self):
        client = FakeClient(base_url="https://aihubmix.com/gemini")

        with patch.object(nodes, "_create_runtime_client", return_value=client):
            nodes.NanoBananaProNode().generate(
                "hello",
                resolution="2K",
                thinking_level="high",
            )

        _, payload = client.calls[0]
        self.assertNotIn("thinkingConfig", payload["generationConfig"])
        self.assertTrue(client.closed)

    def test_aihubmix_nano_banana_2_keeps_thinking_level(self):
        client = FakeClient(base_url="https://aihubmix.com/gemini")

        with patch.object(nodes, "_create_runtime_client", return_value=client):
            nodes.NanoBanana31Node().generate(
                "hello",
                resolution="2K",
                thinking_level="medium",
            )

        _, payload = client.calls[0]
        self.assertEqual(payload["generationConfig"]["thinkingConfig"]["thinkingLevel"], "Medium")
        self.assertTrue(client.closed)

    def test_non_aihubmix_pro_keeps_thinking_level(self):
        client = FakeClient(base_url="https://relay.example.com")

        with patch.object(nodes, "_create_runtime_client", return_value=client):
            nodes.NanoBananaProNode().generate(
                "hello",
                resolution="2K",
                thinking_level="high",
            )

        _, payload = client.calls[0]
        self.assertEqual(payload["generationConfig"]["thinkingConfig"]["thinkingLevel"], "High")
        self.assertTrue(client.closed)


if __name__ == "__main__":
    unittest.main()
