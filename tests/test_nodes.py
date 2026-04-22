import asyncio
import base64
import io
import time
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


class FakeAsyncClient:
    def __init__(self, send_seed=True, base_url="https://generativelanguage.googleapis.com"):
        self.calls = []
        self.send_seed = send_seed
        self.base_url = base_url
        self.closed = False

    async def generate_content(self, model_name, payload):
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

    async def close(self):
        self.closed = True


class SlowFakeAsyncClient(FakeAsyncClient):
    def __init__(self, delay=0.1, **kwargs):
        super().__init__(**kwargs)
        self.delay = delay

    async def generate_content(self, model_name, payload):
        await asyncio.sleep(self.delay)
        return await super().generate_content(model_name, payload)


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
        client = FakeAsyncClient()

        with patch.object(nodes, "_create_runtime_async_client", return_value=client):
            asyncio.run(nodes.NanoBanana25Node().generate(
                "hello",
                model_override="",
            ))

        self.assertEqual(client.calls[0][0], "gemini-2.5-flash-image")
        self.assertTrue(client.closed)

    def test_model_override_only_changes_outbound_model_name(self):
        client = FakeAsyncClient()

        with patch.object(nodes, "_create_runtime_async_client", return_value=client):
            asyncio.run(nodes.NanoBanana31Node().generate(
                "hello",
                resolution="2K",
                thinking_level="medium",
                include_thoughts=True,
                model_override="relay-gemini-image",
            ))

        request_model_name, payload = client.calls[0]
        self.assertEqual(request_model_name, "relay-gemini-image")
        self.assertEqual(payload["generationConfig"]["imageConfig"]["imageSize"], "2K")
        self.assertEqual(payload["generationConfig"]["thinkingConfig"]["thinkingLevel"], "Medium")
        self.assertTrue(payload["generationConfig"]["thinkingConfig"]["includeThoughts"])
        self.assertTrue(client.closed)

    def test_client_can_disable_seed_forwarding(self):
        client = FakeAsyncClient(send_seed=False)

        with patch.object(nodes, "_create_runtime_async_client", return_value=client):
            asyncio.run(nodes.NanoBanana25Node().generate(
                "hello",
                seed=123,
            ))

        _, payload = client.calls[0]
        self.assertNotIn("seed", payload["generationConfig"])
        self.assertTrue(client.closed)

    def test_aihubmix_pro_strips_explicit_thinking_level(self):
        client = FakeAsyncClient(base_url="https://aihubmix.com/gemini")

        with patch.object(nodes, "_create_runtime_async_client", return_value=client):
            asyncio.run(nodes.NanoBananaProNode().generate(
                "hello",
                resolution="2K",
                thinking_level="high",
            ))

        _, payload = client.calls[0]
        self.assertNotIn("thinkingConfig", payload["generationConfig"])
        self.assertTrue(client.closed)

    def test_aihubmix_nano_banana_2_keeps_thinking_level(self):
        client = FakeAsyncClient(base_url="https://aihubmix.com/gemini")

        with patch.object(nodes, "_create_runtime_async_client", return_value=client):
            asyncio.run(nodes.NanoBanana31Node().generate(
                "hello",
                resolution="2K",
                thinking_level="medium",
            ))

        _, payload = client.calls[0]
        self.assertEqual(payload["generationConfig"]["thinkingConfig"]["thinkingLevel"], "Medium")
        self.assertTrue(client.closed)

    def test_non_aihubmix_pro_keeps_thinking_level(self):
        client = FakeAsyncClient(base_url="https://relay.example.com")

        with patch.object(nodes, "_create_runtime_async_client", return_value=client):
            asyncio.run(nodes.NanoBananaProNode().generate(
                "hello",
                resolution="2K",
                thinking_level="high",
            ))

        _, payload = client.calls[0]
        self.assertEqual(payload["generationConfig"]["thinkingConfig"]["thinkingLevel"], "High")
        self.assertTrue(client.closed)

    def test_generation_nodes_are_async_and_can_overlap(self):
        created_clients = []

        def create_client():
            client = SlowFakeAsyncClient(delay=0.1)
            created_clients.append(client)
            return client

        async def run_parallel_generations():
            return await asyncio.gather(
                nodes.NanoBanana25Node().generate("hello 1"),
                nodes.NanoBanana25Node().generate("hello 2"),
            )

        with patch.object(nodes, "_create_runtime_async_client", side_effect=create_client):
            started = time.perf_counter()
            asyncio.run(run_parallel_generations())
            elapsed = time.perf_counter() - started

        self.assertLess(elapsed, 0.16)
        self.assertEqual(len(created_clients), 2)
        self.assertTrue(all(client.closed for client in created_clients))

    def test_single_node_parallel_requests_can_overlap_and_merge_outputs(self):
        created_clients = []

        def create_client():
            client = SlowFakeAsyncClient(delay=0.1)
            created_clients.append(client)
            return client

        with patch.object(nodes, "_create_runtime_async_client", side_effect=create_client):
            started = time.perf_counter()
            image, text, response_json = asyncio.run(
                nodes.NanoBanana25Node().generate(
                    "hello",
                    parallel_requests=2,
                )
            )
            elapsed = time.perf_counter() - started

        self.assertLess(elapsed, 0.16)
        self.assertEqual(len(created_clients), 2)
        self.assertTrue(all(client.closed for client in created_clients))
        self.assertEqual(tuple(image.shape), (2, 4, 4, 3))
        self.assertEqual(text, "[request 1] done\n\n[request 2] done")
        self.assertTrue(response_json.startswith("["))


if __name__ == "__main__":
    unittest.main()
