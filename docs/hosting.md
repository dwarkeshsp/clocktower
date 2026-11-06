# Hosting the play server (play.clocktowerbench.com)

`python -m clocktower play` is one Python process (stdlib HTTP server, no other dependencies beyond the
package) that hosts many tables at once. People open the home page, open a table, share its link, and play
10–12-player Trouble Brewing games with friends and AI seats. Code: `clocktower/web.py` (API, limits, storage),
`clocktower/table/` (the page). Tests: `tests/test_web.py`.

## What it keeps, and where

Everything lives under `PLAY_DATA_DIR` (mount a persistent volume there):

| Path | What |
|---|---|
| `play.db` | SQLite: every table (people, their tokens, settings, seats, the reveal of finished games) and every AI call's cost (`spend`) |
| `games/<time>-<table>-<game>/` | each game's logs, as in the eval (`events.jsonl`, `transcript.md`, `calls.jsonl`, `probes.jsonl`, `conversations/`) and its `checkpoint.pkl` |

- **Restarts and redeploys:** tables, people and links survive. A running game continues from its last dusk
  (the engine checkpoints there), so the current day replays: AI seats re-answer (a little extra spend) and
  people answer that day's turns again. Pages reconnect by themselves.
- **Own-key games** pause at a restart (the key was only in memory). The host sees "paste your key again" and a
  Resume button.
- **Storage layer:** `web.Store` has five methods (`save_table`, `load_tables`, `delete_table`, `add_spend`,
  `spent`). A Postgres version is the same class with `psycopg` and `%s` placeholders.
- **Disk:** a game's logs are 1–5 MB. Finished tables and their logs are deleted after `PLAY_KEEP_DAYS`.
- **One instance only:** games run inside the process. Never scale to two machines or instances.

## Who pays for AI seats

- **Free games:** only the models in `PLAY_FREE_MODELS` (default GPT-6.1 Sol, about $0.11 per seat per game, so
  roughly $1–1.50 a game), on the server's key. Each free game stops at `PLAY_GAME_BUDGET`. A new free game
  starts only if today's spend + the unspent caps of free games already running + one more cap fit within
  `PLAY_DAILY_BUDGET`. Before each API attempt (including probes and retries), the server counts input tokens
  and atomically reserves the maximum input/cache-write and output cost in SQLite, then replaces that reserve
  with reported usage. This also enforces the daily limit on games continuing across midnight. Verified house
  pricing currently supports GPT-6.1 Sol only, using Standard service tier; other models require own keys.
  With the defaults ($30, $5) at most 6 free games
  run at once. When the day is used up, the page says so and offers practice bots or the player's own key.
  The day resets at midnight in `PLAY_BUDGET_TIMEZONE` (UTC by default; Asia/Singapore in `fly.toml`).
  An uncertain network outcome or crash keeps its maximum-cost reservation, including on later days, until
  an operator reconciles it with provider usage. This can stop games early but cannot silently free money
  that may already have been spent. Keep the dedicated house key server-side and use it only in this app:
  calls made directly with the same key bypass this app's cap. Review prices before changing model or tier.
- **Own-key games:** the host pastes an Anthropic and/or OpenAI key at the table (lobby → "Use your own API key").
  Every AI seat in that game then runs on the host's keys (any model in the list, including GPT-6.1 Sol), up to
  `PLAY_BYO_GAME_BUDGET` per game. The key is checked once against the provider's free model-list endpoint,
  held in the process's memory for that table only, never written to the database, logs or stdout, never
  returned by the API, and forgotten when the table closes or the server restarts. Provider error messages
  that echo a masked key are scrubbed from the game's logs. A game is either free or on own keys, never a mix.
- **Practice bots** (`random`) are always free.
- Spend: `SELECT date(time, 'unixepoch'), paid_by, round(sum(cost), 2) FROM spend GROUP BY 1, 2;` on `play.db`.

## Limits

| Limit | Default | Env |
|---|---|---|
| Games at once | 20 | `PLAY_MAX_GAMES` |
| Open tables (lobbies + games) | 300 | `PLAY_MAX_TABLES` |
| New tables per IP per hour | 6 | `PLAY_TABLES_PER_HOUR` |
| API requests per IP | 40/s reads (burst 80), 15/s writes (burst 30) | code (`Hub.gets`, `Hub.posts`) |
| Request body | 32 KB | code (`BODY_LEN`) |
| Names / messages | 24 chars / 2000 chars, then the game's word limits | code |
| Table size | 10–12 seats; 1–12 people, the rest AI | code (`SIZES`) |
| Idle | a lobby nobody opens for 30 min closes; a game nobody watches for 30 min ends (stops spending); an absent player's turns pass after 2 min | `PLAY_IDLE_MINUTES` |

Tokens (per person) are 144-bit random, table ids 72-bit; there is no host password (the first to join hosts,
anyone can take the chair). Nobody's token is ever sent to anyone else. All user text is escaped in the page,
and pages are served with a strict Content-Security-Policy (scripts from the server only).

## Environment variables

| Variable | Needed | Meaning |
|---|---|---|
| `OPENAI_API_KEY` | for free games | the house key that pays for free GPT-6.1 Sol seats |
| `ANTHROPIC_API_KEY` (+ `ANTHROPIC_WORKSPACE_ID`) | no | used by local benchmark runs; hosted Claude seats require the player's own key |
| `PLAY_DATA_DIR` | yes | persistent directory (Docker image: `/data`) |
| `PLAY_PUBLIC_URL` | yes | `https://play.clocktowerbench.com`: invite links, and the origin allowed to post |
| `PLAY_PROXY_HOPS` | yes behind a proxy | `1` on Render and Fly (client IP = last `X-Forwarded-For` hop); `0` = socket address |
| `PLAY_IP_HEADER` | yes on Fly | `Fly-Client-IP`: read the client IP from this header the proxy sets, ahead of `X-Forwarded-For` (Fly's edge can add its own address there, so every visitor behind one edge would share a rate limit) |
| `PLAY_ALLOWED_ORIGINS` | no | extra origins allowed to post (comma-separated) |
| `PLAY_FREE_MODELS` | no | default `gpt-6.1-sol`; only models with verified request cost bounds can use the house key (currently GPT-6.1 Sol) |
| `PLAY_DAILY_BUDGET` | no | USD per budget day for free games, default 30 |
| `PLAY_BUDGET_TIMEZONE` | no | IANA timezone for midnight reset, default UTC; Fly uses Asia/Singapore |
| `PLAY_GAME_BUDGET` | no | USD per free game, default 5 |
| `PLAY_BYO_GAME_BUDGET` | no | USD per own-key game, default 50 |
| `PLAY_MAX_GAMES`, `PLAY_MAX_TABLES`, `PLAY_TABLES_PER_HOUR`, `PLAY_IDLE_MINUTES` | no | limits above |
| `PLAY_KEEP_DAYS` | no | days to keep finished tables and their logs, default 14 (0 = forever) |
| `PLAY_PROBES` | no | `1` (default): AI seats answer the eval's belief survey each day (about +15% calls), shown at the reveal as "what the AIs believed about you"; `0` to save the spend |
| `PORT` | set by the host | port to listen on |

## Deploy on Fly.io (recommended: cheap, volumes, one machine)

```sh
fly auth login
fly launch --no-deploy --copy-config --name clocktower-play   # uses fly.toml and the Dockerfile
fly volumes create clocktower_data --size 5 --region iad
fly secrets set OPENAI_API_KEY=sk-...                          # the house key for free games
fly deploy
fly certs add play.clocktowerbench.com                         # then add the DNS records it prints:
#   CNAME play -> clocktower-play.fly.dev   (or the A/AAAA records)
curl https://play.clocktowerbench.com/healthz                  # {"ok": true, "games": 0, "tables": 0}
```

Keep one machine (`fly scale count 1`) and auto-stop off (fly.toml does both). A deploy stops the machine for
a few seconds; running games resume from their last dusk.

## Deploy on Render

`render.yaml` is a Blueprint (Docker runtime, a 5 GB disk at `/data`, one instance, health check `/healthz`,
the custom domain). A disk needs a paid instance (Starter, ~$7/month); the free plan has none and sleeps.

1. Render → New → Blueprint → this repo (branch `main`). Enter `OPENAI_API_KEY` when asked (leave
   `ANTHROPIC_API_KEY` empty unless a Claude model is free).
2. Settings → Custom Domains: `play.clocktowerbench.com`; add the CNAME it shows at your DNS provider.
3. Check `https://play.clocktowerbench.com/healthz`.

The old free-tier service (`clocktower-ogul.onrender.com`) can be deleted once this one runs.

## Run it anywhere else

```sh
docker build -t clocktower-play .
docker run -d --restart unless-stopped -p 8080:8080 -v clocktower-data:/data \
  -e OPENAI_API_KEY=sk-... -e PLAY_PUBLIC_URL=https://play.clocktowerbench.com -e PLAY_PROXY_HOPS=1 clocktower-play
```

Put a TLS proxy (Caddy, nginx, Cloudflare) in front. The server sends `Cache-Control: no-store` on everything;
polling is about one request per second per open page.

## At home

`python -m clocktower play` (no `PLAY_PUBLIC_URL`) opens one table and prints a host link and a LAN link
for friends; data goes to `games/play/`. `PLAY_FREE_MODELS=all` offers every model your keys cover.

## Watching it

- `GET /healthz`: games running and open tables.
- `GET /api/info`: today's free budget left.
- stdout: game summaries and tracebacks (keys redacted).
- Spend by day: the SQL above.
