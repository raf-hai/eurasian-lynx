# eurasian-lynx

LLM-driven project-manager agent. Reads tasks from Asana, decides what to
assign and nudge using a prompt you control, and posts to the `#summa`
Slack channel. Runs on a cron locally now; portable to EC2 later with
zero code changes.

## How it works

Every tick (cron-driven, currently 09:00 / 13:00 / 17:00 local):

1. Pull open tasks from configured Asana projects.
2. Diff against local state (`state/state.json`) to compute deltas since
   the last run.
3. Hand the snapshot to Claude with `config/prompt.md` as the system prompt
   and a fixed tool set: `assign_task`, `post_to_summa`, `snooze_task`,
   `note`.
4. Execute the tool calls (with idempotency checks against state).
5. Persist updated state.

## Setup

```bash
cd ~/code/eurasian-lynx
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
```

Fill `.env`:

- `ASANA_PAT` — Asana personal access token. Generate at
  https://app.asana.com/0/my-apps.
- `SLACK_BOT_TOKEN` — `xoxb-...` token for a bot user with `chat:write`
  and `users:read` scopes, invited to `#summa`.
- `ANTHROPIC_API_KEY` — from https://console.anthropic.com/.
- `SLACK_SUMMA_CHANNEL_ID` — right-click the channel → View details → ID.

Fill `config/projects.yaml` with the Asana project gid(s) to watch
(the number after `/0/` in the project URL).

Fill `config/roster.yaml` with one entry per teammate (name, Asana user
gid, Slack member ID).

Optionally tune `config/prompt.md` — this is the agent's operating
instructions, edit freely.

## Run

Dry-run first (no Asana writes, no Slack posts):

```bash
.venv/bin/python -m eurasian_lynx --once --dry-run --verbose
```

Live single tick:

```bash
.venv/bin/python -m eurasian_lynx --once
```

## Schedule (cron)

```cron
0 9,13,17 * * * cd $HOME/code/eurasian-lynx && ./scripts/run-once.sh >> state/run.log 2>&1
```

Edit with `crontab -e`. On macOS, give `cron` Full Disk Access in
System Settings → Privacy & Security if you see permission errors.

## Layout

```
config/        prompt.md, projects.yaml, roster.yaml
state/         state.json (per-task seen/pinged/snoozed; gitignored)
src/eurasian_lynx/
  __main__.py    entrypoint
  config.py      env + yaml loader
  asana_client.py
  slack_client.py
  pm_agent.py    Claude tool-use loop
  tools.py       tool schemas + executor
  state.py       atomic JSON state
scripts/run-once.sh
```

## Porting to EC2 (later)

No code changes required. Move the repo, recreate `.venv`, put `.env`
into SSM/Secrets Manager and sync to disk on boot, install the same
crontab. Ship `state/run.log` to CloudWatch if you want logs centralized;
back up `state/state.json` to S3 nightly.
