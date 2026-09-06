"""One polling pass. Python standard library only; state survives CronJob pods."""

import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

API = "https://public.api.bsky.app/xrpc/"


def request(url, method="GET", body=None, token=None):
    headers = {"User-Agent": "alucard-bsky-matrix/1.0"}
    if token:
        headers["Authorization"] = "Bearer " + token
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = Request(url, data=None if body is None else json.dumps(body).encode(),
                  headers=headers, method=method)
    with urlopen(req, timeout=30) as response:
        return json.load(response)


def validate(config):
    if set(config) != {"rules"} or not isinstance(config["rules"], list):
        raise ValueError("Expected an object containing a rules list")
    ids = set()
    for rule in config["rules"]:
        if set(rule) - {"id", "actor", "keywords", "match", "include_replies"}:
            raise ValueError("Unknown rule field")
        for key in ("id", "actor"):
            if not isinstance(rule.get(key), str) or not rule[key].strip():
                raise ValueError("Rule requires non-empty id and actor")
        if rule["id"] in ids:
            raise ValueError("Duplicate rule id")
        ids.add(rule["id"])
        keywords = rule.get("keywords", [])
        if not isinstance(keywords, list) or any(
            not isinstance(k, str) or not k.strip() for k in keywords
        ):
            raise ValueError("keywords must be a list of non-empty strings")
        if rule.get("match", "any") not in ("any", "all"):
            raise ValueError("match must be any or all")
        if not isinstance(rule.get("include_replies", False), bool):
            raise ValueError("include_replies must be boolean")
    return config["rules"]


def matches(rule, post):
    record = post["record"]
    if record.get("reply") and not rule.get("include_replies", False):
        return False
    words = rule.get("keywords", [])
    checks = [word.casefold() in record.get("text", "").casefold() for word in words]
    return not words or (all(checks) if rule.get("match", "any") == "all" else any(checks))


def database(path):
    db = sqlite3.connect(path)
    db.executescript("""
        CREATE TABLE IF NOT EXISTS rules (
            id TEXT PRIMARY KEY, did TEXT NOT NULL, started TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS seen (
            rule TEXT, uri TEXT, PRIMARY KEY (rule, uri));
        CREATE TABLE IF NOT EXISTS delivered (
            room TEXT, uri TEXT, PRIMARY KEY (room, uri));
    """)
    return db


def resolve_room(base, room, token, get=request):
    if room.startswith("#"):
        return get(base + "/directory/room/" + quote(room, safe=""), token=token)["room_id"]
    if not room.startswith("!"):
        raise ValueError("MATRIX_ROOM_ID must be a room ID or alias")
    return room


def poll(rule, db, room, send, get=request):
    key = rule["id"]
    previous = db.execute("SELECT did, started FROM rules WHERE id=?", (key,)).fetchone()
    started = previous[1] if previous else datetime.now(timezone.utc).isoformat()
    # Pin a handle to its DID once, so a renamed account stays the same identity.
    did = previous[0] if previous else get(
        API + "app.bsky.actor.getProfile?" + urlencode({"actor": rule["actor"]})
    )["did"]
    posts, cursor = {}, None
    for _ in range(100):
        params = {"actor": did, "limit": 100, "filter": "posts_with_replies",
                  "includePins": "false"}
        if cursor:
            params["cursor"] = cursor
        page = get(API + "app.bsky.feed.getAuthorFeed?" + urlencode(params))
        boundary = False
        for item in page["feed"]:
            post = item["post"]
            # Reposts are not authored posts; quotes are (match the author's text).
            if item.get("reason") or post["author"]["did"] != did:
                continue
            uri = post["uri"]
            if db.execute("SELECT 1 FROM seen WHERE rule=? AND uri=?", (key, uri)).fetchone():
                boundary = True
            else:
                posts[uri] = post
        cursor = page.get("cursor")
        if not previous or boundary or not cursor:
            break
    else:
        raise RuntimeError("Catch-up exceeded 100 pages; checkpoint preserved")

    # Baseline a new rule without sending its existing posts. Commit the whole
    # scan only after all sends succeed; delivered entries survive partial failure.
    for post in reversed(list(posts.values())):
        uri = post["uri"]
        recent = datetime.fromisoformat(post["indexedAt"].replace("Z", "+00:00")) >= datetime.fromisoformat(started)
        if previous and recent and matches(rule, post) and not db.execute(
            "SELECT 1 FROM delivered WHERE room=? AND uri=?", (room, uri)
        ).fetchone():
            txn = hashlib.sha256((room + "\n" + uri).encode()).hexdigest()
            send(post, txn)
            with db:
                db.execute("INSERT OR IGNORE INTO delivered VALUES (?, ?)", (room, uri))
    with db:
        db.executemany("INSERT OR IGNORE INTO seen VALUES (?, ?)",
                       [(key, uri) for uri in posts])
        db.execute("INSERT OR IGNORE INTO rules VALUES (?, ?, ?)", (key, did, started))
    print(f"rule={key} examined={len(posts)} baseline={not bool(previous)}", flush=True)


def main():
    with open(os.environ.get("BSKY_CONFIG", "/config/rules.json")) as source:
        rules = validate(json.load(source))
    if "--validate" in sys.argv:
        print(f"Valid configuration: {len(rules)} rules")
        return
    if not rules:
        print("No rules configured")
        return
    base = os.environ["MATRIX_HOMESERVER"].rstrip("/") + "/_matrix/client/v3"
    token = os.environ["MATRIX_ACCESS_TOKEN"]
    room = resolve_room(base, os.environ["MATRIX_ROOM_ID"], token)
    state = request(base + "/rooms/" + quote(room, safe="") + "/state", token=token)
    if any(event["type"] == "m.room.encryption" for event in state):
        raise ValueError("This notifier requires an unencrypted notification room")

    def send(post, txn):
        author = post["author"]
        link = "https://bsky.app/profile/" + author["did"] + "/post/" + post["uri"].rsplit("/", 1)[1]
        body = f"@{author['handle']} on Bluesky\n\n{post['record'].get('text', '')}\n\n{link}"
        request(base + "/rooms/" + quote(room, safe="") + "/send/m.room.message/" + txn,
                method="PUT", body={"msgtype": "m.text", "body": body,
                                    "m.mentions": {}}, token=token)

    failed = False
    with database(os.environ.get("BSKY_STATE", "/data/state.sqlite3")) as db:
        for rule in rules:
            try:
                poll(rule, db, room, send)
            except Exception as error:
                # Never dump response bodies, headers, tokens or post text into logs.
                code = f" status={error.code}" if isinstance(error, HTTPError) else ""
                print(f"rule={rule['id']} failed={type(error).__name__}{code}", file=sys.stderr)
                failed = True
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        code = f" status={error.code}" if isinstance(error, HTTPError) else ""
        print(f"Notifier failed: {type(error).__name__}{code}", file=sys.stderr)
        raise SystemExit(1)
