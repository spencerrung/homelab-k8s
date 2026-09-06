import unittest
from unittest.mock import patch
from urllib.error import HTTPError

import bootstrap_room


class BootstrapTests(unittest.TestCase):
    def run_helper(self, execute=False, power=50):
        calls = []
        bot = "@alertmanager:alucard.dev"

        def api(url, method="GET", body=None, token=None):
            calls.append((url, method, body))
            if url.endswith("/rooms/%21space%3Aalucard.dev/state"):
                return [
                    {"type": "m.room.create", "state_key": "", "content": {"type": "m.space"}},
                    {"type": "m.room.name", "state_key": "", "content": {"name": "Alucard"}},
                    {"type": "m.room.power_levels", "state_key": "", "content": {"users": {bot: power}}},
                ]
            if url.endswith("/account/whoami"):
                return {"user_id": bot}
            if "/directory/room/" in url:
                raise HTTPError(url, 404, "Not found", {}, None)
            if url.endswith("/createRoom"):
                return {"room_id": "!new:alucard.dev"}
            return {}

        args = ["bootstrap_room.py", "--space-id", "!space:alucard.dev",
                "--bot-user", bot, "--room-admin", "@spencer:alucard.dev"]
        if execute:
            args.append("--execute")
        with patch.object(bootstrap_room, "request", side_effect=api), patch(
            "sys.argv", args
        ), patch.dict("os.environ", {"MATRIX_ACCESS_TOKEN": "test"}):
            bootstrap_room.main()
        return calls

    def test_default_plan_does_not_write(self):
        self.assertTrue(all(method == "GET" for _, method, _ in self.run_helper()))

    def test_create_invites_human_not_bot_self_and_links_both_directions(self):
        calls = self.run_helper(execute=True)
        created = next(body for url, _, body in calls if url.endswith("/createRoom"))
        self.assertEqual(created["invite"], ["@spencer:alucard.dev"])
        self.assertEqual(created["power_level_content_override"]["users"]["@spencer:alucard.dev"], 100)
        self.assertFalse(any(event.get("type") == "m.room.encryption" for event in created.get("initial_state", [])))
        self.assertEqual(sum(method == "PUT" for _, method, _ in calls), 2)

    def test_missing_space_power_stops_before_creation(self):
        with self.assertRaises(ValueError):
            self.run_helper(execute=True, power=0)


if __name__ == "__main__":
    unittest.main()
