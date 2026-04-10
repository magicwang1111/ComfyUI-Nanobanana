import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from _loader import import_module

capabilities = import_module("py.api.capabilities")
client_module = import_module("py.api.client")
nodes = import_module("py.nodes")


class FakeResolvedClient:
    def __init__(self, api_key, timeout=60, base_url=None, auth_mode=None, send_seed=True):
        self.api_key = api_key
        self.timeout = timeout
        self.base_url = base_url
        self.auth_mode = auth_mode
        self.send_seed = send_seed

    @staticmethod
    def normalize_auth_mode(auth_mode):
        return client_module.Client.normalize_auth_mode(auth_mode)

    def close(self):
        pass


class ClientResolutionTests(unittest.TestCase):
    def test_node_input_key_has_highest_priority(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.ini"
            config_path.write_text(
                "[API]\n"
                "GEMINI_API_KEY = config-key\n"
                "NANOBANANA_BASE_URL = https://config.example.com\n"
                "NANOBANANA_AUTH_MODE = x-goog-api-key\n",
                encoding="utf-8",
            )

            with patch.dict(
                "os.environ",
                {
                    "GEMINI_API_KEY": "env-key",
                    "NANOBANANA_BASE_URL": "https://env.example.com",
                    "NANOBANANA_AUTH_MODE": "x-goog-api-key",
                    "NANOBANANA_SEND_SEED": "true",
                },
                clear=False,
            ):
                with patch.object(nodes, "CONFIG_PATH", config_path):
                    with patch.object(nodes, "Client", FakeResolvedClient):
                        client = nodes.NanoBananaClientNode().create_client(
                            "node-key",
                            60,
                            "https://node.example.com/",
                            "bearer",
                            False,
                        )[0]
                        self.assertEqual(client.api_key, "node-key")
                        self.assertEqual(client.base_url, "https://node.example.com")
                        self.assertEqual(client.auth_mode, "bearer")
                        self.assertFalse(client.send_seed)
                        client.close()

    def test_env_values_beat_config_when_client_uses_defaults(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.ini"
            config_path.write_text(
                "[API]\n"
                "NANOBANANA_API_KEY = config-key\n"
                "NANOBANANA_BASE_URL = https://config.example.com\n"
                "NANOBANANA_AUTH_MODE = x-goog-api-key\n"
                "NANOBANANA_SEND_SEED = true\n",
                encoding="utf-8",
            )

            with patch.dict(
                "os.environ",
                {
                    "NANOBANANA_API_KEY": "env-key",
                    "NANOBANANA_BASE_URL": "https://env.example.com/",
                    "NANOBANANA_AUTH_MODE": "bearer",
                    "NANOBANANA_SEND_SEED": "false",
                },
                clear=False,
            ):
                with patch.object(nodes, "CONFIG_PATH", config_path):
                    with patch.object(nodes, "Client", FakeResolvedClient):
                        client = nodes.NanoBananaClientNode().create_client(
                            "",
                            60,
                            capabilities.DEFAULT_BASE_URL,
                            capabilities.DEFAULT_AUTH_MODE,
                            capabilities.DEFAULT_SEND_SEED,
                        )[0]
                        self.assertEqual(client.api_key, "env-key")
                        self.assertEqual(client.base_url, "https://env.example.com")
                        self.assertEqual(client.auth_mode, "bearer")
                        self.assertFalse(client.send_seed)
                        client.close()

    def test_config_values_used_when_env_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.ini"
            config_path.write_text(
                "[API]\n"
                "NANOBANANA_API_KEY = config-key\n"
                "NANOBANANA_BASE_URL = https://config.example.com/\n"
                "NANOBANANA_AUTH_MODE = bearer\n"
                "NANOBANANA_SEND_SEED = false\n",
                encoding="utf-8",
            )

            with patch.dict("os.environ", {}, clear=True):
                with patch.object(nodes, "CONFIG_PATH", config_path):
                    with patch.object(nodes, "Client", FakeResolvedClient):
                        client = nodes.NanoBananaClientNode().create_client(
                            "",
                            60,
                            capabilities.DEFAULT_BASE_URL,
                            capabilities.DEFAULT_AUTH_MODE,
                            capabilities.DEFAULT_SEND_SEED,
                        )[0]
                        self.assertEqual(client.api_key, "config-key")
                        self.assertEqual(client.base_url, "https://config.example.com")
                        self.assertEqual(client.auth_mode, "bearer")
                        self.assertFalse(client.send_seed)
                        client.close()

    def test_gemini_env_key_remains_supported(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.ini"
            config_path.write_text("[API]\nGEMINI_API_KEY = config-key\n", encoding="utf-8")

            with patch.dict("os.environ", {"GEMINI_API_KEY": "env-key"}, clear=False):
                with patch.object(nodes, "CONFIG_PATH", config_path):
                    with patch.object(nodes, "Client", FakeResolvedClient):
                        client = nodes.NanoBananaClientNode().create_client(
                            "",
                            60,
                            capabilities.DEFAULT_BASE_URL,
                            capabilities.DEFAULT_AUTH_MODE,
                            capabilities.DEFAULT_SEND_SEED,
                        )[0]
                        self.assertEqual(client.api_key, "env-key")
                        self.assertTrue(client.send_seed)
                        client.close()

    def test_missing_key_raises(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.ini"
            config_path.write_text("[API]\nGEMINI_API_KEY = \n", encoding="utf-8")

            with patch.dict("os.environ", {}, clear=True):
                with patch.object(nodes, "CONFIG_PATH", config_path):
                    with self.assertRaises(ValueError):
                        nodes.NanoBananaClientNode().create_client(
                            "",
                            60,
                            capabilities.DEFAULT_BASE_URL,
                            capabilities.DEFAULT_AUTH_MODE,
                            capabilities.DEFAULT_SEND_SEED,
                        )


class ClientTransportTests(unittest.TestCase):
    def test_builds_google_api_key_headers(self):
        client = client_module.Client("google-key")
        try:
            self.assertEqual(client.auth_mode, "x-goog-api-key")
            self.assertTrue(client.send_seed)
            self.assertEqual(client._client.headers.get("x-goog-api-key"), "google-key")
            self.assertIsNone(client._client.headers.get("Authorization"))
        finally:
            client.close()

    def test_builds_bearer_headers(self):
        client = client_module.Client(
            "relay-key",
            base_url="https://relay.example.com",
            auth_mode="bearer",
            send_seed=False,
        )
        try:
            self.assertEqual(client.auth_mode, "bearer")
            self.assertEqual(client.base_url, "https://relay.example.com")
            self.assertFalse(client.send_seed)
            self.assertEqual(client._client.headers.get("Authorization"), "Bearer relay-key")
            self.assertIsNone(client._client.headers.get("x-goog-api-key"))
        finally:
            client.close()

    def test_invalid_auth_mode_raises(self):
        with self.assertRaises(ValueError):
            client_module.Client("relay-key", auth_mode="invalid")


if __name__ == "__main__":
    unittest.main()
