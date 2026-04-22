import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from _loader import import_module

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


class FakeResolvedAsyncClient(FakeResolvedClient):
    async def close(self):
        pass


class RuntimeConfigResolutionTests(unittest.TestCase):
    def test_json_values_have_highest_priority(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            json_path = Path(temp_dir) / "config.local.json"
            json_path.write_text(
                json.dumps(
                    {
                        "api_key": "json-key",
                        "request_timeout": 90,
                        "base_url": "https://json.example.com/",
                        "auth_mode": "bearer",
                        "send_seed": False,
                    }
                ),
                encoding="utf-8",
            )
            legacy_path = Path(temp_dir) / "config.ini"
            legacy_path.write_text(
                "[API]\n"
                "NANOBANANA_API_KEY = legacy-key\n"
                "NANOBANANA_BASE_URL = https://legacy.example.com\n"
                "NANOBANANA_AUTH_MODE = x-goog-api-key\n"
                "NANOBANANA_SEND_SEED = true\n",
                encoding="utf-8",
            )

            with patch.dict(
                "os.environ",
                {
                    "NANOBANANA_API_KEY": "env-key",
                    "NANOBANANA_BASE_URL": "https://env.example.com",
                    "NANOBANANA_AUTH_MODE": "x-goog-api-key",
                    "NANOBANANA_SEND_SEED": "true",
                    "GEMINI_API_KEY": "gemini-env-key",
                },
                clear=False,
            ):
                with patch.object(nodes, "CONFIG_JSON_PATH", json_path):
                    with patch.object(nodes, "LEGACY_CONFIG_PATH", legacy_path):
                        with patch.object(nodes, "Client", FakeResolvedClient):
                            client = nodes._create_runtime_client()
                            self.assertEqual(client.api_key, "json-key")
                            self.assertEqual(client.timeout, 90)
                            self.assertEqual(client.base_url, "https://json.example.com")
                            self.assertEqual(client.auth_mode, "bearer")
                            self.assertFalse(client.send_seed)
                            client.close()

    def test_env_values_beat_legacy_config_when_json_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            json_path = Path(temp_dir) / "config.local.json"
            legacy_path = Path(temp_dir) / "config.ini"
            legacy_path.write_text(
                "[API]\n"
                "NANOBANANA_API_KEY = legacy-key\n"
                "NANOBANANA_BASE_URL = https://legacy.example.com\n"
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
                with patch.object(nodes, "CONFIG_JSON_PATH", json_path):
                    with patch.object(nodes, "LEGACY_CONFIG_PATH", legacy_path):
                        with patch.object(nodes, "Client", FakeResolvedClient):
                            client = nodes._create_runtime_client()
                            self.assertEqual(client.api_key, "env-key")
                            self.assertEqual(client.timeout, nodes.DEFAULT_REQUEST_TIMEOUT)
                            self.assertEqual(client.base_url, "https://env.example.com")
                            self.assertEqual(client.auth_mode, "bearer")
                            self.assertFalse(client.send_seed)
                            client.close()

    def test_legacy_config_used_when_json_and_env_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            json_path = Path(temp_dir) / "config.local.json"
            legacy_path = Path(temp_dir) / "config.ini"
            legacy_path.write_text(
                "[API]\n"
                "NANOBANANA_API_KEY = legacy-key\n"
                "NANOBANANA_BASE_URL = https://legacy.example.com/\n"
                "NANOBANANA_AUTH_MODE = bearer\n"
                "NANOBANANA_SEND_SEED = false\n",
                encoding="utf-8",
            )

            with patch.dict("os.environ", {}, clear=True):
                with patch.object(nodes, "CONFIG_JSON_PATH", json_path):
                    with patch.object(nodes, "LEGACY_CONFIG_PATH", legacy_path):
                        with patch.object(nodes, "Client", FakeResolvedClient):
                            client = nodes._create_runtime_client()
                            self.assertEqual(client.api_key, "legacy-key")
                            self.assertEqual(client.timeout, nodes.DEFAULT_REQUEST_TIMEOUT)
                            self.assertEqual(client.base_url, "https://legacy.example.com")
                            self.assertEqual(client.auth_mode, "bearer")
                            self.assertFalse(client.send_seed)
                            client.close()

    def test_gemini_env_key_remains_supported(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            json_path = Path(temp_dir) / "config.local.json"
            legacy_path = Path(temp_dir) / "config.ini"
            legacy_path.write_text("[API]\nGEMINI_API_KEY = legacy-key\n", encoding="utf-8")

            with patch.dict("os.environ", {"GEMINI_API_KEY": "env-key"}, clear=False):
                with patch.object(nodes, "CONFIG_JSON_PATH", json_path):
                    with patch.object(nodes, "LEGACY_CONFIG_PATH", legacy_path):
                        with patch.object(nodes, "Client", FakeResolvedClient):
                            client = nodes._create_runtime_client()
                            self.assertEqual(client.api_key, "env-key")
                            self.assertEqual(client.timeout, nodes.DEFAULT_REQUEST_TIMEOUT)
                            self.assertEqual(client.base_url, client_module.DEFAULT_BASE_URL)
                            self.assertEqual(client.auth_mode, client_module.DEFAULT_AUTH_MODE)
                            self.assertTrue(client.send_seed)
                            client.close()

    def test_request_timeout_only_comes_from_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            json_path = Path(temp_dir) / "config.local.json"
            json_path.write_text(
                json.dumps(
                    {
                        "api_key": "json-key",
                        "request_timeout": 120,
                    }
                ),
                encoding="utf-8",
            )
            legacy_path = Path(temp_dir) / "config.ini"
            legacy_path.write_text(
                "[API]\n"
                "NANOBANANA_API_KEY = legacy-key\n",
                encoding="utf-8",
            )

            with patch.dict("os.environ", {}, clear=True):
                with patch.object(nodes, "CONFIG_JSON_PATH", json_path):
                    with patch.object(nodes, "LEGACY_CONFIG_PATH", legacy_path):
                        with patch.object(nodes, "Client", FakeResolvedClient):
                            client = nodes._create_runtime_client()
                            self.assertEqual(client.timeout, 120)
                            client.close()

    def test_async_runtime_client_uses_same_resolved_values(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            json_path = Path(temp_dir) / "config.local.json"
            json_path.write_text(
                json.dumps(
                    {
                        "api_key": "json-key",
                        "request_timeout": 75,
                        "base_url": "https://json.example.com/",
                        "auth_mode": "bearer",
                        "send_seed": False,
                    }
                ),
                encoding="utf-8",
            )
            legacy_path = Path(temp_dir) / "config.ini"
            legacy_path.write_text("[API]\nGEMINI_API_KEY = legacy-key\n", encoding="utf-8")

            with patch.dict("os.environ", {}, clear=True):
                with patch.object(nodes, "CONFIG_JSON_PATH", json_path):
                    with patch.object(nodes, "LEGACY_CONFIG_PATH", legacy_path):
                        with patch.object(nodes, "AsyncClient", FakeResolvedAsyncClient):
                            client = nodes._create_runtime_async_client()
                            self.assertEqual(client.api_key, "json-key")
                            self.assertEqual(client.timeout, 75)
                            self.assertEqual(client.base_url, "https://json.example.com")
                            self.assertEqual(client.auth_mode, "bearer")
                            self.assertFalse(client.send_seed)
                            asyncio.run(client.close())

    def test_missing_key_raises(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            json_path = Path(temp_dir) / "config.local.json"
            legacy_path = Path(temp_dir) / "config.ini"
            legacy_path.write_text("[API]\nGEMINI_API_KEY = \n", encoding="utf-8")

            with patch.dict("os.environ", {}, clear=True):
                with patch.object(nodes, "CONFIG_JSON_PATH", json_path):
                    with patch.object(nodes, "LEGACY_CONFIG_PATH", legacy_path):
                        with self.assertRaises(ValueError):
                            nodes._create_runtime_client()


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

    def test_async_client_builds_google_api_key_headers(self):
        client = client_module.AsyncClient("google-key")
        try:
            self.assertEqual(client.auth_mode, "x-goog-api-key")
            self.assertTrue(client.send_seed)
            self.assertEqual(client._client.headers.get("x-goog-api-key"), "google-key")
            self.assertIsNone(client._client.headers.get("Authorization"))
        finally:
            asyncio.run(client.close())


if __name__ == "__main__":
    unittest.main()
