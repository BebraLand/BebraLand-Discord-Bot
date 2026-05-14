import unittest
from types import SimpleNamespace

from src.features.status.minecraft import _serialize_status_response


class MinecraftStatusTests(unittest.TestCase):
    def test_serialize_status_response_keeps_mcstatus_fields(self):
        response = SimpleNamespace(
            players=SimpleNamespace(online=12, max=50),
            version=SimpleNamespace(name="1.21.4", protocol=769),
            latency=42.5,
            description="BebraLand",
        )

        self.assertEqual(
            _serialize_status_response(response),
            {
                "players": {"online": 12, "max": 50},
                "version": {"name": "1.21.4", "protocol": 769},
                "latency": 42.5,
                "motd": "BebraLand",
            },
        )


if __name__ == "__main__":
    unittest.main()
