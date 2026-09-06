import unittest
from unittest.mock import Mock

from watcher import database, matches, poll, resolve_room, validate


def post(number, text="New RELEASE", **record):
    return {"uri": f"at://did:plc:test/app.bsky.feed.post/{number}",
            "author": {"did": "did:plc:test", "handle": "test.example"},
            "record": {"text": text, **record}, "indexedAt": "2099-01-01T00:00:00Z"}


class WatcherTests(unittest.TestCase):
    def setUp(self):
        self.db = database(":memory:")
        self.addCleanup(self.db.close)
        self.rule = {"id": "test", "actor": "test.example", "keywords": ["release"]}

    def feed(self, *posts):
        return {"feed": [{"post": p} for p in posts]}

    def baseline(self):
        send = Mock()
        poll(self.rule, self.db, "room", send,
             Mock(side_effect=[{"did": "did:plc:test"}, self.feed(post(1))]))
        send.assert_not_called()

    def test_keyword_modes_and_replies(self):
        self.assertTrue(matches(self.rule, post(1)))
        self.assertFalse(matches(self.rule, post(1, reply={"parent": "x"})))
        self.assertTrue(matches({"keywords": [], "include_replies": True}, post(1, reply={"parent": "x"})))
        self.assertFalse(matches({"keywords": ["release", "linux"], "match": "all"}, post(1)))
        self.assertTrue(matches({"keywords": ["strasse"]}, post(1, "Straße")))

    def test_baseline_pagination_dedup_and_retry(self):
        self.baseline()
        send = Mock(side_effect=[None, RuntimeError("temporary")])
        pages = [{**self.feed(post(3)), "cursor": "next"}, self.feed(post(2), post(1))]
        with self.assertRaises(RuntimeError):
            poll(self.rule, self.db, "room", send, Mock(side_effect=pages))
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM seen").fetchone()[0], 1)
        retry = Mock()
        poll(self.rule, self.db, "room", retry, Mock(side_effect=pages))
        self.assertEqual(retry.call_count, 1)
        self.assertEqual(retry.call_args.args[1], send.call_args.args[1])
        poll(self.rule, self.db, "room", retry, Mock(return_value=self.feed(post(3), post(2), post(1))))
        self.assertEqual(retry.call_count, 1)

    def test_ignore_reposts_and_nonmatching_posts(self):
        self.baseline()
        page = self.feed(post(3, "nothing"), post(1))
        page["feed"].insert(0, {"post": post(4), "reason": {"$type": "repost"}})
        send = Mock()
        poll(self.rule, self.db, "room", send, Mock(return_value=page))
        send.assert_not_called()

    def test_old_history_not_sent_when_boundary_disappears(self):
        self.baseline()
        old = post(0)
        old["indexedAt"] = "2000-01-01T00:00:00Z"
        send = Mock()
        poll(self.rule, self.db, "room", send, Mock(return_value=self.feed(old)))
        send.assert_not_called()

    def test_failed_page_does_not_advance_state(self):
        self.baseline()
        send = Mock()
        with self.assertRaises(RuntimeError):
            poll(self.rule, self.db, "room", send, Mock(side_effect=[
                {**self.feed(post(2)), "cursor": "next"}, RuntimeError("network")]))
        send.assert_not_called()
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM seen").fetchone()[0], 1)

    def test_duplicate_rules_and_invalid_config(self):
        for rules in ([self.rule, self.rule], [{**self.rule, "keywords": "oops"}],
                      [{**self.rule, "match": "typo"}], [{**self.rule, "include_replies": "false"}]):
            with self.assertRaises(ValueError):
                validate({"rules": rules})

    def test_overlap_across_rules_sends_once(self):
        self.baseline()
        other = {**self.rule, "id": "second"}
        send = Mock()
        poll(other, self.db, "room", send, Mock(side_effect=[
            {"did": "did:plc:test"}, self.feed(post(1))]))
        for rule in (self.rule, other):
            poll(rule, self.db, "room", send, Mock(return_value=self.feed(post(2), post(1))))
        self.assertEqual(send.call_count, 1)

    def test_page_cap_preserves_checkpoint(self):
        self.baseline()
        send = Mock()
        with self.assertRaises(RuntimeError):
            poll(self.rule, self.db, "room", send,
                 Mock(return_value={**self.feed(post(2)), "cursor": "next"}))
        send.assert_not_called()
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM seen").fetchone()[0], 1)

    def test_room_alias_resolves_to_stable_id(self):
        get = Mock(return_value={"room_id": "!room:alucard.dev"})
        self.assertEqual(resolve_room("https://matrix", "#bsky:alucard.dev", "token", get), "!room:alucard.dev")
        get.assert_called_once_with("https://matrix/directory/room/%23bsky%3Aalucard.dev", token="token")
        get.reset_mock()
        self.assertEqual(resolve_room("https://matrix", "!room:alucard.dev", "token", get), "!room:alucard.dev")
        get.assert_not_called()


if __name__ == "__main__":
    unittest.main()
