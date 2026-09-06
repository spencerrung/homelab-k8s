# Bluesky → Matrix bsky

One-minute CronJob in the `matrix` namespace, sending authored Bluesky posts
to a private, **unencrypted** `bsky` room within the **Alucard** space.
Messages contain the account handle, post text, and a link to the original.
The Python standard library implementation needs no Bluesky credentials.
The image is the same pinned Python image used by the media anime guard.

## Initial setup

The job watches `thsottiaux-bot.eurosky.social` for the case-insensitive substring
`reset`, excluding replies and reposts. It resolves `#bsky:alucard.dev` each run.
It reuses `@alertmanager:alucard.dev` and the existing Vault credential at
`secret/monitoring/matrix`, property `access-token`. ESO creates the Kubernetes
Secret through the committed manifest; no manual Kubernetes writes are needed.
Do not log out or rotate the shared bot session without updating Vault, since
Homelab Alerts also uses it.

These files alone do not create the room. Complete the room setup before merging
the enabled CronJob. Room creation is Matrix application data; workload deployment
is exclusively Git → merge → Flux. Do not commit credentials.

1. Invite `@alertmanager:alucard.dev` to **Alucard** and give it permission to
   add child rooms (usually Moderator). Accept the invitation as the bot.
2. Copy the Alucard space's room ID from its settings. Load the existing bot
   access token securely into `MATRIX_ACCESS_TOKEN`, without printing it or
   putting it in command arguments, shell history, Git, or chat.

   ```sh
   # MATRIX_ACCESS_TOKEN: existing alert bot token, loaded securely
   export MATRIX_HOMESERVER=https://matrix.alucard.dev
   python3 -B apps/matrix/bsky/bootstrap_room.py \
     --space-id '!YOUR_SPACE_ID:alucard.dev' \
     --bot-user '@alertmanager:alucard.dev' --room-admin '@spencer:alucard.dev'
   # After reviewing the plan, repeat with --execute.
   ```

   The helper verifies the space is named Alucard and the token can add children.
   It creates `#bsky:alucard.dev`, invites Spencer with room-admin power, and
   writes both space links. The bot is already joined as the room's creator.
   A retry reuses the alias only if the room has the expected name, is
   unencrypted, and the token owner has room-admin power. It sends no chat message.
   Alternatively, create an unencrypted private room named `bsky` inside Alucard
   in your client, set its alias to `#bsky:alucard.dev`, invite the alert bot,
   and accept that invitation as the bot.
3. Clear the token from the shell when finished. Validate below, open and review
   the PR, merge, then reconcile `apps-stateful` through Flux. The checked-in
   CronJob is enabled. Its first scheduled run baselines the account.
4. Join the room as yourself and set its client notification preference to
   **All messages**. Phone/desktop push also requires notifications enabled in
   the client and operating system. The bot sends ordinary `m.text` messages.

## Configure accounts and keywords

Edit `rules.json` and ship through GitOps. A new Job reads the generated
ConfigMap; there is no image rebuild. See [rules.example.json](rules.example.json)
for three independent examples. All rules send to the same `bsky` room.

| Field | Meaning |
| --- | --- |
| `id` | Unique, stable rule identifier; controls polling history |
| `actor` | Full handle without `@`, or a DID; no profile URL |
| `keywords` | Case-insensitive literal substrings; `[]` or omitted means all posts |
| `match` | `any` (default) or `all` keywords must occur in the post text |
| `include_replies` | `false` by default; `true` includes authored replies |

Multiple rules for the same account are allowed. A post matching multiple rules
is delivered once per destination room. Reposts are excluded. Quote posts match
only the watched author's own text. Image alt text, linked pages, quoted text,
and attachments are not searched or mirrored. A keyword such as `cat` also
matches `catalog`; keyword phrases match literally, including spaces.

A new rule baselines its first feed page without sending old posts. Future
polls page back to known posts, up to 100 pages, and ignore posts indexed before
the rule was initialized. Posts arriving during the initial baseline can be
absorbed into that baseline. Handles resolve once to a stable DID: a handle
rename keeps tracking the same person. **To change the account, use a new rule
ID**. Editing keywords or reply settings with the same ID affects future unseen
posts; it does not replay history. Removing a rule stops polling it; re-adding
the same ID resumes its saved history and can deliver posts from the pause.

## Reliability and operation

SQLite history is on the 1Gi `bsky-notifier-data` PVC, protected from Flux prune.
The Matrix namespace is included in the existing nightly Velero backup schedule.
Local-path storage is tied to a node; a node outage can delay polling until it
returns or storage is restored. History grows with scanned posts; monitor PVC
capacity over time. Do not delete the database to fix temporary HTTP failures.
If state is lost, rules baseline again rather than replaying all history.

The job forbids concurrent runs, has a five-minute deadline, and one retry.
Completed deliveries persist even if a later send fails. Stable Matrix
transaction IDs also reduce duplicates if a request succeeds but its response
is lost; server deduplication is scoped to the bot's access token. Rotating
that token during an ambiguous delivery can produce a duplicate.

Feed failures and Matrix failures leave the rule checkpoint intact and fail
the Job, allowing the next run to retry. Other rules still run when one fails.
HTTP 429 uses the same next-run retry rather than immediate retry loops.
The 100-page cap fails without advancing the checkpoint. If an outage creates
a larger backlog, increase the cap and Job deadline together after inspection.
No live/readiness probes are needed for a finite CronJob; completion and exit
status are its health signal. Existing monitoring must cover failed Jobs if
you want an operational alert when this notifier stops working.

Polling is best-effort: deleted posts between polls, non-public accounts, and
feed indexing/reordering can cause omissions. It is not a Bluesky event archive.
Normal delivery latency is about one minute plus Bluesky indexing and scheduling.
Encrypted rooms fail closed because this lightweight sender has no E2EE support.

```sh
kubectl -n matrix get cronjob bsky-notifier
kubectl -n matrix get jobs --sort-by=.metadata.creationTimestamp
kubectl -n matrix get externalsecret bsky-notifier
kubectl -n matrix logs job/<bsky-notifier-job-name>
```

Logs contain rule IDs, counts and error classes/status codes, not tokens or post
bodies. `401`: check the bot token; `403`: check membership and send permission;
`429`: upstream throttling. Pending pods: check PVC/node placement or ESO secret
sync. To stop forwarding, set `suspend: true` through GitOps; an already-running
Job may finish. Keep the PVC to preserve history.

## Local validation

From the repository root:

```sh
python3 -B -m unittest discover -s apps/matrix/bsky -v
BSKY_CONFIG=apps/matrix/bsky/rules.json python3 -B apps/matrix/bsky/watcher.py --validate
BSKY_CONFIG=apps/matrix/bsky/rules.example.json python3 -B apps/matrix/bsky/watcher.py --validate
kubectl kustomize apps/matrix
```

Tests use fake feeds and Matrix sends; no live message is sent. After deployment,
verify a successful baseline Job and an actual matching future post. An explicit
test message can separately verify Matrix delivery once authorized.

API references: [Bluesky author-feed lexicon](https://github.com/bluesky-social/atproto/blob/main/lexicons/app/bsky/feed/getAuthorFeed.json),
[Matrix client-server API](https://spec.matrix.org/v1.13/client-server-api/).
