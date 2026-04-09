import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from _loader import import_module

nodes = import_module("py.nodes")


class ClientResolutionTests(unittest.TestCase):
    def test_node_input_key_has_highest_priority(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.ini"
            config_path.write_text("[API]\nGEMINI_API_KEY = config-key\n", encoding="utf-8")

            with patch.dict("os.environ", {"GEMINI_API_KEY": "env-key"}, clear=False):
                with patch.object(nodes, "CONFIG_PATH", config_path):
                    client = nodes.NanoBananaClientNode().create_client("node-key", 60)[0]
                    self.assertEqual(client.api_key, "node-key")

    def test_env_key_beats_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.ini"
            config_path.write_text("[API]\nGEMINI_API_KEY = config-key\n", encoding="utf-8")

            with patch.dict("os.environ", {"GEMINI_API_KEY": "env-key"}, clear=False):
                with patch.object(nodes, "CONFIG_PATH", config_path):
                    client = nodes.NanoBananaClientNode().create_client("", 60)[0]
                    self.assertEqual(client.api_key, "env-key")

    def test_missing_key_raises(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.ini"
            config_path.write_text("[API]\nGEMINI_API_KEY = \n", encoding="utf-8")

            with patch.dict("os.environ", {}, clear=True):
                with patch.object(nodes, "CONFIG_PATH", config_path):
                    with self.assertRaises(ValueError):
                        nodes.NanoBananaClientNode().create_client("", 60)


if __name__ == "__main__":
    unittest.main()
