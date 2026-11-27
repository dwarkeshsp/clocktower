# Gemini 4 Neon: rating plan (pilot done; stages 1-2 not run)

Status, Nov 27: the pilot has run (one pair vs GPT-6.1 Sol, 1-1). The adapter works against the live API with no
changes: schema honoured, thought parts and `thoughtSignature`s carried across turns, no errors. Model id
`gemini-4-neon`. Neon does not accept `thinkingLevel: minimal`, so the ceiling retry stays at `low`. **Stages 1-2
are not run: waiting for the go-ahead.**

## Pilot: what a Neon game costs

| Game | Neon plays | Result | Neon | GPT-6.1 Sol | Total | Time |
|---|---|---|---|---|---|---|
| game-01 | good (8 seats) | good, day 4 | $19.64 | $0.99 | $20.64 | 62 min |
| game-01-swap | evil (3 seats) | evil, day 5 | $7.94 | $3.44 | $11.38 | 60 min |
| **Pair** | | | **$27.58** | **$4.43** | **$32.02** | **~1 h (parallel)** |

- Caching works: 87-92% of Neon's input was read from Gemini's implicit cache, so explicit caching isn't needed.
- Passes: 3 of 586 Neon turns hit the 8,000-token ceiling, and all 3 recovered on the low-effort retry. **No turn
  passed** (Carbon passed 2.4% of its turns in Google's games).
- Time: about an hour a game, like the other frontier models, not the 3-7 hours of Google's Carbon games.

## Target

Match the other ratings rather than beat them. On the current fit, 90% intervals are ±50 to ±110, with the recent
additions at ±70 (Fable 5.2, 88 games) and ±72 (GPT-6.2 Astra, 96 games). **Target: about ±70 (90%), roughly 90-100
Neon games.** ±50 would need about twice the games and is not worth it for one model.

## Stages

| Stage | Plan | Games | What |
|---|---|---|---|
| 0 | `g1-neon-pilot.json` | 2 | One side-swapped pair vs GPT-6.1 Sol: adapter end to end, real cost and time per game |
| 1 | `g1b-neon.json` | 24 | Four pairs each vs GPT-6.1 Sol (1745), Opus 5.5 (1540), GPT-6.2 Astra (1945) |
| — | refit | | `python -m clocktower ratings`, then `allocate --only gemini-4-neon --target 70` |
| 2 | `g1c-neon.json` (from `allocate`) | ~60-70 | By information per dollar, at most 10 pairs per opponent, until ±70 |

Stop after stage 0 to check the cost, time and pass rate (see Risks) before launching stage 1.

## Cost (from the pilot)

Neon is about $14 a game (average of the two sides). The opponents' seats are estimated from whole-game totals in
f6/f7: about $2 a game for GPT-6.1 Sol (as measured), about $5 for Opus 5.5 or GPT-6.2 Astra. Stage 2's split
across opponents is set by `allocate`, so its OpenAI/Anthropic share is assumed to be similar to stage 1's.

| | Games | Gemini | OpenAI | Anthropic |
|---|---|---|---|---|
| Pilot (done) | 2 | $28 | $4 | — |
| Stage 1 | 24 | ~$330 | ~$60 | ~$40 |
| Stage 2 | ~70 | ~$970 | ~$170 | ~$110 |
| **Total for ±70** | **~96** | **~$1,350** | **~$230** | **~$150** |

With room for longer games (the pilot's two games ran 4-5 days; some games go to 8+), budget **up to ~$2,000
Gemini, ~$350 OpenAI, ~$250 Anthropic**. For ±50 instead (~190 games), roughly double all of it: ~$2,700 Gemini
(up to ~$4,000), still under the $7,500 cap.

## Risks to check in the pilot

1. **Passes on the ceiling.** (Pilot: 0 passes.) Carbon's low-effort retry often still spent all 8,000 tokens thinking: 2.4% of its
   turns (6.3% in one game) passed with no action. The adapter does the same (high, then low, then pass). If Neon
   passes on more than ~1% of turns, consider a lower retry level (if Neon accepts `minimal`) before stage 1, since
   passes cost Neon Elo for an API reason.
2. **Schema.** If Neon rejects `responseJsonSchema`, the adapter falls back to stating the schema in the prompt.
   Check which path the pilot took.
3. **Pricing.** Check the $3/$15 list price and the cached rate against Google's pricing page and against the
   AI Studio bill after the pilot.
