#!/usr/bin/env python3
"""Import stickers from stickers.gg into Matrix as Cinny-compatible sticker packs.

Scrapes a stickers.gg tag page, downloads the images, uploads them to the
Synapse media repo, publishes them as MSC2545 image packs (im.ponies.room_emotes)
in a private room, and enables the packs globally (im.ponies.emote_rooms).

Usage:
  MATRIX_TOKEN=syt_... ./import-stickers.py [--tag anime] [--limit N] [--dry-run]

Resumable: progress (downloads, uploads, room id) is kept in --workdir, so
re-running skips completed work.
"""

import argparse
import json
import os
import re
import struct
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

UA = {"User-Agent": "Mozilla/5.0 (sticker-import script)"}


def http(url, data=None, headers=None, method=None, retries=5):
    hdrs = dict(UA)
    if headers:
        hdrs.update(headers)
    for attempt in range(retries):
        req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            body = e.read()
            if e.code == 429:
                try:
                    wait = json.loads(body).get("retry_after_ms", 3000) / 1000
                except Exception:
                    wait = 3
                time.sleep(wait + 0.5)
                continue
            if e.code >= 500 and attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"HTTP {e.code} for {url}: {body[:300]!r}") from None
        except (urllib.error.URLError, TimeoutError):
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise
    raise RuntimeError(f"giving up on {url}")


def scrape_ids(tag):
    ids, page = [], 1
    seen = set()
    while True:
        try:
            html = http(f"https://stickers.gg/stickers/{tag}&page={page}").decode()
        except RuntimeError as e:
            if "HTTP 404" in str(e):
                break
            raise
        found = re.findall(r'data-id="([^"]+)"', html)
        if not found:
            break
        for f in found:
            if f not in seen:
                seen.add(f)
                ids.append(f)
        print(f"  page {page}: {len(found)} stickers ({len(ids)} total)")
        page += 1
        time.sleep(0.3)
    return ids


def scrape_bufo_ids():
    data = json.loads(http("https://bufo.fun/bufo-data.json"))
    ids = []
    for b in data["bufos"]:
        bid = b["id"]
        # some ids carry literal \uXXXX escapes (e.g. señor-bufo)
        if "\\u" in bid:
            bid = bid.encode().decode("unicode_escape")
        ids.append(f"{bid}.{b['fileType']}")
    return ids


def download_all(ids, img_dir, base_url):
    img_dir.mkdir(parents=True, exist_ok=True)
    todo = [i for i in ids if not (img_dir / i).exists()]
    print(f"  {len(ids) - len(todo)} already downloaded, {len(todo)} to fetch")

    def fetch(sid):
        data = http(base_url + urllib.parse.quote(sid))
        (img_dir / sid).write_bytes(data)

    failed = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(fetch, sid): sid for sid in todo}
        for n, fut in enumerate(as_completed(futs), 1):
            try:
                fut.result()
            except RuntimeError as e:
                if "HTTP 404" not in str(e):
                    raise
                failed.append(futs[fut])
                print(f"  WARNING: 404, skipping {futs[fut]}")
            if n % 50 == 0 or n == len(todo):
                print(f"  downloaded {n}/{len(todo)}")
    return failed


def sniff(data):
    """Return (mimetype, (w, h) or None) from the file's magic bytes.

    stickers.gg serves WebP files with .png names, so the extension lies.
    """
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png", struct.unpack(">II", data[16:24])
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif", struct.unpack("<HH", data[6:10])
    if data[:2] == b"\xff\xd8":
        return "image/jpeg", None
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        cc = data[12:16]
        if cc == b"VP8X":
            w = int.from_bytes(data[24:27], "little") + 1
            h = int.from_bytes(data[27:30], "little") + 1
            return "image/webp", (w, h)
        if cc == b"VP8 ":
            w, h = struct.unpack("<HH", data[26:30])
            return "image/webp", (w & 0x3FFF, h & 0x3FFF)
        if cc == b"VP8L":
            b = data[21:25]
            w = 1 + (((b[1] & 0x3F) << 8) | b[0])
            h = 1 + (((b[3] & 0xF) << 10) | (b[2] << 2) | ((b[1] & 0xC0) >> 6))
            return "image/webp", (w, h)
        return "image/webp", None
    return "application/octet-stream", None


class Matrix:
    def __init__(self, homeserver, token):
        self.hs = homeserver.rstrip("/")
        self.auth = {"Authorization": f"Bearer {token}"}

    def api(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        hdrs = dict(self.auth)
        if data:
            hdrs["Content-Type"] = "application/json"
        raw = http(f"{self.hs}{path}", data=data, headers=hdrs, method=method)
        return json.loads(raw) if raw else {}

    def whoami(self):
        return self.api("GET", "/_matrix/client/v3/account/whoami")["user_id"]

    def upload(self, name, data):
        url = f"{self.hs}/_matrix/media/v3/upload?filename={urllib.parse.quote(name)}"
        hdrs = dict(self.auth)
        hdrs["Content-Type"] = sniff(data)[0]
        return json.loads(http(url, data=data, headers=hdrs, method="POST"))["content_uri"]


def shortcode(sid, source):
    stem = sid.rsplit(".", 1)[0]
    if source == "stickersgg":
        # "9959-2b.png" -> "2b-9959"
        m = re.match(r"(\d+)-(.+)", stem)
        if m:
            stem = f"{m.group(2)}-{m.group(1)}"
    return re.sub(r"[^a-z0-9_-]", "-", stem.lower())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["stickersgg", "bufo"], default="stickersgg")
    ap.add_argument("--tag", default="anime",
                    help="stickers.gg tag (ignored for --source bufo)")
    ap.add_argument("--usage", choices=["sticker", "emoticon", "both"], default="sticker")
    ap.add_argument("--homeserver", default="https://matrix.alucard.dev")
    ap.add_argument("--workdir", default="./sticker-import-work")
    ap.add_argument("--pack-size", type=int, default=200)
    ap.add_argument("--limit", type=int, help="only import the first N stickers")
    ap.add_argument("--room", help="reuse an existing room id instead of creating one")
    ap.add_argument("--dry-run", action="store_true",
                    help="scrape + download only, no Matrix calls")
    args = ap.parse_args()

    if args.source == "bufo":
        label = "bufo"
        base_url = "https://bufo.fun/bufos/"
    else:
        label = args.tag
        base_url = "https://cdn.stickers.gg/stickers/"

    work = Path(args.workdir)
    work.mkdir(parents=True, exist_ok=True)
    img_dir = work / f"images-{label}" if args.source == "bufo" else work / "images"
    ids_file = work / f"ids-{label}.json"
    uploads_file = work / "uploads.json"
    state_file = work / "state.json"

    print(f"[1/4] scraping ids for '{label}'")
    if ids_file.exists():
        ids = json.loads(ids_file.read_text())
        print(f"  using cached list: {len(ids)} images ({ids_file})")
    else:
        ids = scrape_bufo_ids() if args.source == "bufo" else scrape_ids(args.tag)
        ids_file.write_text(json.dumps(ids, indent=1))
        print(f"  found {len(ids)} images")
    if args.limit:
        ids = ids[:args.limit]
        print(f"  limited to first {len(ids)}")

    print("[2/4] downloading images")
    failed = download_all(ids, img_dir, base_url)
    if failed:
        ids = [i for i in ids if i not in set(failed)]
        print(f"  continuing without {len(failed)} unavailable image(s)")

    if args.dry_run:
        print("dry run: stopping before Matrix upload")
        return

    token = os.environ.get("MATRIX_TOKEN")
    if not token:
        sys.exit("set MATRIX_TOKEN to your Matrix access token")
    mx = Matrix(args.homeserver, token)
    user_id = mx.whoami()
    print(f"[3/4] uploading media as {user_id}")

    uploads = json.loads(uploads_file.read_text()) if uploads_file.exists() else {}
    todo = [i for i in ids if i not in uploads]
    print(f"  {len(ids) - len(todo)} already uploaded, {len(todo)} to upload")
    for n, sid in enumerate(todo, 1):
        uploads[sid] = mx.upload(sid, (img_dir / sid).read_bytes())
        if n % 20 == 0 or n == len(todo):
            uploads_file.write_text(json.dumps(uploads, indent=1))
            print(f"  uploaded {n}/{len(todo)}")
    uploads_file.write_text(json.dumps(uploads, indent=1))

    print("[4/4] publishing image packs")
    state = json.loads(state_file.read_text()) if state_file.exists() else {}
    room_id = args.room or state.get("room_id")
    if not room_id:
        room_id = mx.api("POST", "/_matrix/client/v3/createRoom", {
            "name": "Sticker Packs",
            "topic": f"MSC2545 image packs imported from stickers.gg ({args.tag})",
            "preset": "private_chat",
        })["room_id"]
        state["room_id"] = room_id
        state_file.write_text(json.dumps(state))
        print(f"  created room {room_id}")
    else:
        print(f"  using room {room_id}")

    usage = ["emoticon", "sticker"] if args.usage == "both" else [args.usage]
    pack_keys = []
    chunks = [ids[i:i + args.pack_size] for i in range(0, len(ids), args.pack_size)]
    for n, chunk in enumerate(chunks, 1):
        images = {}
        for sid in chunk:
            data = (img_dir / sid).read_bytes()
            mime, dims = sniff(data)
            info = {"size": len(data), "mimetype": mime}
            if dims:
                info["w"], info["h"] = int(dims[0]), int(dims[1])
            images[shortcode(sid, args.source)] = {"url": uploads[sid], "info": info}
        key = f"{label}-{n}"
        content = {
            "pack": {
                "display_name": f"{label.title()} {n}/{len(chunks)}",
                "usage": usage,
            },
            "images": images,
        }
        mx.api("PUT",
               f"/_matrix/client/v3/rooms/{urllib.parse.quote(room_id)}"
               f"/state/im.ponies.room_emotes/{urllib.parse.quote(key)}",
               content)
        pack_keys.append(key)
        print(f"  published pack '{key}' ({len(images)} stickers)")

    # enable the packs globally for this account
    try:
        emote_rooms = mx.api(
            "GET", f"/_matrix/client/v3/user/{urllib.parse.quote(user_id)}"
                   "/account_data/im.ponies.emote_rooms")
    except RuntimeError:
        emote_rooms = {}
    rooms = emote_rooms.setdefault("rooms", {})
    rooms.setdefault(room_id, {}).update({k: {} for k in pack_keys})
    mx.api("PUT", f"/_matrix/client/v3/user/{urllib.parse.quote(user_id)}"
                  "/account_data/im.ponies.emote_rooms", emote_rooms)
    print(f"  enabled {len(pack_keys)} packs globally")
    print("done — open Cinny's sticker picker (may need a reload)")


if __name__ == "__main__":
    main()
