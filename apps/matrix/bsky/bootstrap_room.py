"""Create/link bsky using a space owner's token; no writes without --execute."""

import argparse
import os
from urllib.error import HTTPError
from urllib.parse import quote

from watcher import request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--space-id", required=True)
    parser.add_argument("--bot-user", required=True)
    parser.add_argument("--room-admin", action="append", default=[],
                        help="Invite this user and grant room-admin power (repeatable)")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    base = os.environ.get("MATRIX_HOMESERVER", "https://matrix.alucard.dev").rstrip("/")
    base += "/_matrix/client/v3"
    token = os.environ["MATRIX_ACCESS_TOKEN"]

    def api(path, method="GET", body=None):
        return request(base + path, method, body, token)

    space = "/rooms/" + quote(args.space_id, safe="")
    state = api(space + "/state")
    events = {(e["type"], e["state_key"]): e["content"] for e in state}
    if events.get(("m.room.create", ""), {}).get("type") != "m.space":
        raise ValueError("Target is not a Matrix space")
    if events.get(("m.room.name", ""), {}).get("name") != "Alucard":
        raise ValueError("Target space is not named Alucard")
    owner = api("/account/whoami")["user_id"]
    invitees = sorted(({args.bot_user} | set(args.room_admin)) - {owner})
    power = events[("m.room.power_levels", "")]
    if power.get("users", {}).get(owner, power.get("users_default", 0)) < power.get(
        "events", {}
    ).get("m.space.child", power.get("state_default", 50)):
        raise ValueError("Token owner cannot add rooms to this space")
    alias = "#bsky:alucard.dev"
    try:
        room = api("/directory/room/" + quote(alias, safe=""))["room_id"]
        # Only reuse a room already owned by this user, with the intended name.
        room_state = api("/rooms/" + quote(room, safe="") + "/state")
        current = {(e["type"], e["state_key"]): e["content"] for e in room_state}
        if current.get(("m.room.name", ""), {}).get("name") != "bsky":
            raise ValueError("Existing alias points to an unexpected room")
        if ("m.room.encryption", "") in current:
            raise ValueError("Existing room is encrypted")
        if current[("m.room.power_levels", "")].get("users", {}).get(owner, 0) < 100:
            raise ValueError("Existing room is not owned by token user")
    except HTTPError as error:
        if error.code != 404:
            raise
        room = None
    print(f"Plan: {'reuse ' + room if room else 'create private bsky room'}; link to Alucard; invite {invitees}; room admins {args.room_admin}")
    if not args.execute:
        return
    if room is None:
        room = api("/createRoom", "POST", {
            "name": "bsky", "room_alias_name": "bsky", "visibility": "private",
            "preset": "private_chat", "invite": invitees,
            "power_level_content_override": {
                "users": {user: 100 for user in [owner, *args.room_admin]}
            },
            "topic": "Bluesky account and keyword notifications",
        })["room_id"]
    else:
        for user in invitees:
            membership = current.get(("m.room.member", user), {}).get("membership")
            if membership not in ("join", "invite"):
                api("/rooms/" + quote(room, safe="") + "/invite", "POST", {"user_id": user})
        if args.room_admin:
            levels = current[("m.room.power_levels", "")]
            levels.setdefault("users", {}).update({user: 100 for user in args.room_admin})
            api("/rooms/" + quote(room, safe="") + "/state/m.room.power_levels/", "PUT", levels)
    via = ["alucard.dev"]
    api(space + "/state/m.space.child/" + quote(room, safe=""), "PUT",
        {"via": via, "suggested": True})
    api("/rooms/" + quote(room, safe="") + "/state/m.space.parent/" + quote(args.space_id, safe=""),
        "PUT", {"via": via, "canonical": True})
    print(f"Room ready: {room}. Invited users must accept their invitations.")


if __name__ == "__main__":
    main()
