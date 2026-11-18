# Deploying from GitHub Actions

`.github/workflows/tests.yml` runs lint and unit tests on Python 3.11 and 3.13 for pushes and pull requests.
After both pass, pushes to `main` in `dwarkeshsp/clocktower` deploy the affected production targets:

- **Site:** Cloudflare Pages project `clocktowerbench` (`clocktowerbench.com`). Site assets, game manifests,
  ratings/charts, exporter code and shared Python code trigger a rebuild.
- **Play:** Fly app `clocktower-play`. Server code, table assets, dependencies, Dockerfile and Fly configuration
  trigger a deployment. Changes confined to the static site or its build helper do not restart Fly.
- Workflow or dependency changes deploy both. Tests-only and unrelated documentation changes do not deploy.

Deployments for `main` are serialized without cancelling an in-progress deploy. Older commits are skipped when
a run starts after `main` has advanced. Pull requests and other branches run tests only and receive no deploy tokens.
The two deploy jobs are independent: one can succeed even if the other fails.

## One-time repository settings

In GitHub → Settings → Secrets and variables → Actions, add:

| Kind | Name | Value |
|---|---|---|
| Secret | `CLOUDFLARE_API_TOKEN` | Account token with **Pages Write** for the account hosting `clocktowerbench` |
| Secret | `FLY_API_TOKEN` | Deploy token scoped to the existing `clocktower-play` app |
| Variable | `CLOUDFLARE_ACCOUNT_ID` | The account ID from Cloudflare |

The Cloudflare token can have no expiration if desired. DNS permissions are unnecessary for deploying to the
existing project. Fly's runtime model API keys remain in Fly secrets; they are not needed in GitHub.

**Never paste credential values into workflow YAML, scripts, committed files or command arguments.** The workflow
injects each deploy token only into its deployment step. Actions are pinned by commit; Wrangler and flyctl have
explicit versions. Set secrets using GitHub's form or `gh secret set NAME --repo dwarkeshsp/clocktower` (interactive
input). No Hugging Face token is needed: the game dataset is public and all downloads are explicitly anonymous.

## Game logs and complete builds

`python -m clocktower.site_build` is the production build command. It derives the finished-game list from the
committed `games/**/config.json` and `result.json`, using the exporter's rated and mixed batches. New f6/f7-style
batches therefore need no separate deployment download list or hardcoded count.

The helper resolves the Hugging Face dataset to one immutable commit and downloads only `events.jsonl` and
`probes.jsonl`, one batch at a time. GitHub caches those public logs by dataset revision and manifest hash. Configs
and results come from the checked-out commit. A temporary games directory isolates the build from stale cache
entries. Missing logs, invalid manifests or a mismatch in the exported game IDs fail before deployment; an empty
or partial replay library is never silently published. The normal development exporter remains unchanged.

To build locally without deploying:

```sh
pip install -e '.[dev]'
HF_HUB_DISABLE_XET=1 python -m clocktower.site_build
```

`--revision DATASET_COMMIT` reproduces a specific log snapshot; `--out DIRECTORY` changes the output location.
Publish new experiment logs to Hugging Face before merging their manifests into `main`.

## Manual reruns and live games

Open Actions → **CI and deploy** → Run workflow, select `main`, then choose `all`, `site` or `play`.
Tests still run first. Use this after adding/replacing credentials or when only the external dataset changed.

Fly uses its own remote builder (`--depot=false`) and `--ha=false` to avoid provisioning a second machine for this
single-process app. The existing persistent volume and runtime secrets stay on Fly. A successful deploy is followed
by a retrying health check which fails on HTTP errors or a response without `ok: true`.

A Fly deploy briefly restarts the server. Active games resume from their last dusk, replaying the current day;
games using players' own API keys pause until the host re-enters the keys. The site job does not restart games.


## Hourly play check

`.github/workflows/play-check.yml` runs at minute 17 of every hour (UTC), and can also be run manually
from Actions → **Hourly play check** → Run workflow → `main`. It uses the public
`https://play.clocktowerbench.com` API to create a table, join as host, explicitly select practice bots
for both teams, and verify that configuration before starting. It waits up to 60 seconds for a seated
human player with game events and an actionable turn, then ends the game and verifies it has stopped.
Failures also attempt cleanup, including when the start request times out after reaching the server.
The job fails if startup or cleanup fails. It uses only Python's standard library and needs no secrets.

Run the same check locally:

```sh
python -m clocktower.check_play --base-url https://play.clocktowerbench.com
```

The check spends no model credits. It covers table creation, joining, configuration, game startup and
state polling; it does not verify paid model providers or browser rendering. Finished check games use
the server's normal 14-day retention; a table that never starts expires under the idle-lobby policy.

For failure alerts, open [GitHub notification settings](https://github.com/settings/notifications),
under **System → Actions** enable email notifications and **Send notifications for failed workflows only**.
Scheduled-run notifications go to the user who last changed the cron schedule (or re-enabled it).
GitHub schedules can be delayed or dropped under load, and public-repository schedules are disabled after
60 days without repository activity. This is an hourly availability check, not a guaranteed paging service.
See [GitHub's schedule documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
and [Actions notifications](https://docs.github.com/en/subscriptions-and-notifications/how-tos/managing-github-actions-notifications).
