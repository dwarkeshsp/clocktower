# Gemini 4 Neon: rating plan (not run yet)

Status, Nov 27: the adapter and plans are in place, but **no Neon game has been played**. The project behind
`GEMINI_API_KEY` answers every model (Neon and Flash alike) with `402 Your prepayment credits are depleted`, so the
$10K grant is not on that project yet. The model id is `gemini-4-neon` (from `python -m clocktower gemini-models`;
1M input, 65K output). OpenAI and Anthropic keys both answer (`MY_ANTHROPIC_API_KEY` needs the
`anthropic-workspace-id` header, which `make_client` already sends).

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

## Cost (estimates until the pilot replaces them)

No Neon game exists, so these come from Google's 8 Gemini 4 Carbon games, re-priced at Neon's list price ($3 in,
$15 out, cached input assumed $0.30) and split by seat share. That split is crude.

- **Neon as good** (7-9 of 10-12 seats): about $17-98 a game, mean ~$50.
- **Neon as evil** (3 seats): about $5-9 a game.
- **A pair is about $60 of Gemini**, plus about $10-20 for the opponent's seats (from the f6/f7 games).
- Time: the Carbon games took **3-7 hours each** (Fable and Astra games take 0.3-1.5 h). They run in parallel, so
  stage 1 should finish within a day if Gemini's rate limits allow ~24 concurrent games.

| | Games | Gemini | OpenAI | Anthropic |
|---|---|---|---|---|
| Stage 0+1 | 26 | ~$800 | ~$150 | ~$50 |
| Stage 2 | ~70 | ~$2,100 | ~$350 | ~$150 |
| **Total** | **~96** | **~$2,900** (tail ~$4,500) | **~$500** | **~$200** |

The tail is for implicit caching: in one Carbon game 34M of 57M input tokens missed the cache. If the pilot shows
the same, explicit context caching in the adapter would roughly halve Neon's cost and is worth adding before stage 1.
Everything stays well under the $7,500 Gemini cap.

## Risks to check in the pilot

1. **Passes on the ceiling.** Carbon's low-effort retry often still spent all 8,000 tokens thinking: 2.4% of its
   turns (6.3% in one game) passed with no action. The adapter does the same (high, then low, then pass). If Neon
   passes on more than ~1% of turns, consider a lower retry level (if Neon accepts `minimal`) before stage 1, since
   passes cost Neon Elo for an API reason.
2. **Schema.** If Neon rejects `responseJsonSchema`, the adapter falls back to stating the schema in the prompt.
   Check which path the pilot took.
3. **Pricing.** Check the $3/$15 list price and the cached rate against Google's pricing page and against the
   AI Studio bill after the pilot.
