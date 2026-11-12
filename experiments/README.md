# Experiments

One JSON plan per experiment, run with `python -m clocktower tournament experiments/NAME.json`. Every plan whose
games are in the published dataset is kept here, so each result can be traced to the exact matchups, seeds,
Minions and flags that produced it. Each game's `config.json` and `result.json` are in `games/<protocol>/`;
the full logs (transcripts, events, every API call, probes) are in the Hugging Face dataset
[`dwarkesh/clocktower-games`](https://huggingface.co/datasets/dwarkesh/clocktower-games)
(`python -m clocktower fetch v17/f3-*`).

The protocol is frozen per batch (see [`docs/PROTOCOL.md`](../docs/PROTOCOL.md) and
[`docs/protocol-history.md`](../docs/protocol-history.md)): the current code plays v17 only. Plans for earlier
versions record what was run; replaying them exactly needs the code as it was at that version.

## Plans

| Plan | Date (2026) | Games | Protocol | Purpose | Cost (USD) |
|---|---|---|---|---|---|
| [`w1-whispers.json`](w1-whispers.json) | Oct 1 | 50 | v14 | One whisper per private turn: does it tilt balance? 4 vs 6 private beats | — |
| [`c3-whisperlog.json`](c3-whisperlog.json) | Oct 2 | 40 | v15 | A public who-whispered-to-whom log, at 6 and 8 private beats (dropped afterwards) | — |
| [`c3h-loghint.json`](c3h-loghint.json) | Oct 2 | 10 | v15 | c3 plus a prompt hint that the whisper log is evidence | — |
| [`f2-2026.json`](f2-2026.json) | Oct 1 | 110 | v16 | Round robin of the 11 models released in 2026, one side-swapped pair per matchup | 4,369 |
| [`f3-2026-topup.json`](f3-2026-topup.json) | Oct 1–2 | 184 | v17 | Top-up of the 2026 round robin (bounded retries, balanced Minions) | 4,909 |
| [`f3b-2026-topup.json`](f3b-2026-topup.json) | Oct 2 | 78 | v17 | Second top-up, by information per dollar; replaces Opus 4.8's v16 games | 2,268 |
| [`f4-floor.json`](f4-floor.json) | Oct 7 | 16 | v17 | Floor: every model plays every other at least one pair (Opus 4.8's missing opponents) | 986 |
| [`f5-precision.json`](f5-precision.json) | Oct 7 | 18 | v17 | Precision top-up chosen by `allocate` to bring every rating within about ±100 | 649 |
| [`b1-mixed-pilot.json`](b1-mixed-pilot.json) | Oct 7 | 16 | v17 | Pilot: a team split between Opus 5.5 and GPT-5.6 Sol vs pure GPT-6.1 Sol | 118 |
| [`b2-mixed-rating.json`](b2-mixed-rating.json) | Oct 28 | 116 | v17 | Rate the mixed team on the 2026 scale and measure the mixing effect | 1,736 |
| [`f6-fable52-pilot.json`](f6-fable52-pilot.json) | Nov 9 | 12 | v17 | Fable 5.2, the day it came out: one pair against each of six rated models | 408 |
| [`f6b-fable52.json`](f6b-fable52.json) | Nov 9 | 36 | v17 | Fable 5.2: three more pairs per matchup, launched alongside the pilot | 1,061 |
| [`f6c-fable52.json`](f6c-fable52.json) | Nov 9 | 30 | v17 | Fable 5.2: two more pairs per matchup, and one pair each against Opus 4.6, Opus 4.7 and GPT-5.4 | 838 |
| [`ext1-carbon.json`](ext1-carbon.json) | Nov 10 | 8 | v17 | **External**, run and paid for by Google on its own copy of the repo: Gemini 4 Carbon vs GPT-6.1 Sol (2 pairs), GPT-5.6 Sol and GPT-6 Astra (1 pair each) | — |

The ext1 games came as full logs. Checked here: every config is the standard v17 one (high effort, 8,000-token
ceiling, reasoning carried over, scripted Storyteller, 6/3 beats, probes, the v17 prompt hashes); re-dealing each
seed with this engine gives the same characters, bluffs, red herring and Drunk; the OpenAI seats ran normally; and
Carbon's saved conversations keep its thought parts and `thoughtSignature`s. One difference from other models:
Gemini's low-effort retry still often spent all 8,000 tokens thinking, so 62 of Carbon's 2,589 turns (2.4%; up to
6.3% in one game, mostly as good) passed with no action. If that matters, it costs Carbon. They are rated
separately (`--models models-2026-external.json` → [`docs/plans/ext1-ratings.json`](../docs/plans/ext1-ratings.json));
the default fit leaves them out.

Costs are summed from each game's `calls.jsonl` (resumed games replay from their last dusk, so these slightly
undercount). The 2026 ratings use f2 (minus Opus 4.8's 20 v16 games), f3, f3b, f4, f5 (386 games, the original
11-model study) and f6 (78 games, Claude Fable 5.2): 464 games. The f6 batches
were interrupted (the machine was suspended once and every game replayed from its last dusk; the last three games
were cut off by a time limit and resumed), so the amount billed for them was about $2,580.

Model lists, used by `plan`, `ratings` and `allocate`:

- [`models-2026.json`](models-2026.json): the models released in 2026, with lab and release date. The rating
  scale is centred so the 11 of the original study average 1500; a model added later (Claude Fable 5.2, Nov 9) is
  marked `"centre": false`, so the scale stays where that study put it and later models show how far play has risen.
- [`timeline-models.json`](timeline-models.json): 21 models from GPT-4o (May 2024) on, for a timeline experiment
  that has not been run (see [`docs/experiments.md`](../docs/experiments.md)).

## Earlier batches (no plan file)

These ran with `python -m clocktower run` during protocol development. Their configs and results are in
`games/`, their logs in the dataset; [`docs/protocol-history.md`](../docs/protocol-history.md) describes each.

| Batch | Protocol | Games | What it was |
|---|---|---|---|
| `v1/batch-*`, `v1/full-*` | v1 | 14 | Development; LLM Storyteller |
| `v2/opus-20`, `v2/astra-20` | v2 | 40 | Baseline (good won 40 of 40) |
| `v3/phased-10` | v3 | 10 | Private time, then town square; scripted Storyteller |
| `v5/x1-*` | v5 | 65 | Seven model pairings; first belief probes |
| `v6/g1-*` | v6 | 100 | 5×5 grid of model pairings |
| `v7/c1-*` | v7 | 40 | Calibration at 9 and 12 players |
| `v8/t1-*`, `v8/t2-*` | v8 | partial | Timeline attempts, aborted (not usable for ratings) |
| `v9/e1-*` | v9 | 60 | Old and new models plus an effort sweep |
| `v12/c2-*` | v12 | 12 | Calibration of the v12 Storyteller rules |
| `v13/f1-*` | v13 | partial | First timeline launch, stopped for the v14 redesign |
