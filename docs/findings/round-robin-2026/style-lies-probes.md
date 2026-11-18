# Style fingerprinting, good-side lying, and the belief probes (2026 study, 372 games)

Games: every f2/f3/f3b game (v16 + v17). Each game puts one model on all good seats and another on all
evil seats; players are not told this (the prompt says "Every other seat is a different player").

## 1. Did anyone find their team by "this player writes like me"?
No. Four readers searched all thinking, whispers and speeches (style, phrasing, wording, voice, template,
AI, LLM, Claude, GPT, em dash, "like me", …) and read every plausible hit, plus final-day good reasoning in
~50 games.
- 0 cases of "X writes like me, so X is on my team" or any reference to model identity.
- 1 genuine speaking-style read: f3-fable51-v-sol61/game-04, Kit (good) on day 6: "the Imp is probably
  Ellis or Harper, going by their careful, conditional speaking styles". Both were evil, but it was too late
  to matter. A few seats noted others were "AI/LLM players", only to explain odd plays.
- Common instead: "these players used identical wording, so they're coordinating" (~30 cases). When aimed
  at evil players copying a teammate's script, it was usually right and drove executions
  (f2-opus48-v-fable51/game-01-swap: two evil executions, good won). When aimed at good players, it was
  usually wrong: same-model good players converge on the same phrasing, and their own teammates read that
  as an evil bloc. This got good players executed in f2-gpt55-v-opus48/game-01-swap,
  f2-gpt54-v-opus48/game-01-swap and f3b-gpt55-v-opus48/game-03-swap. So the clone effect existed, but the
  models read it backwards.
- Caveat: GPT seats log only summary headings for thinking, so their absence is weaker evidence.

The signal was there to exploit. Crude punctuation and length features of day-1 messages (16 numbers per
player, `scripts/stylo.py` here):
- For a good seat, teammates are closer to it than evil players are (AUC 0.81). By model it ranges from
  0.69 (Opus 5.5) to 0.93 (Opus 4.6).
- A seat's three "least like me" players are evil 47–81% of the time, by model. Chance is about 28%.
- With no hidden information at all, a two-cluster split of the table puts the smaller cluster at 69% evil.
  That cluster contains the Imp in 64% of games.
- Actual day-1 executions hit evil 38% of the time.
- Public speech alone still gives an AUC of 0.69.
- Part of the signal is behaviour, not model: evil also writes differently because of what it is doing.

This is a validity issue for the eval: a model that learned to fingerprint would gain a large edge the
human game doesn't have. Possible fixes are mixed-model teams, or one model per game on both sides plus a
seat-level twist.

## 2. Lying on the good side
Method: one Sonnet 5.5 call per good seat (2,953 of 2,976 parsed). Its input was everything the seat said
or whispered, plus the Storyteller info it received, and it listed every self-claim. A second pass graded
each "info lie" into fabricated own info, invented hearsay, fishing, or not-a-lie. Cost was about $53 of
direct API calls, not in the ledger. Data: `good-lies.json`.

Rows: role = flatly claimed a different good character; info = fabricated own ability result; either =
role or info; 3-for-3 = offered a set of possible characters; hearsay = "X told me…" with no support in
what the seat itself sent or received. The classifier did not see whispers sent *to* the seat, so hearsay
is unreliable and kept out of the headline.

| good model | n | role | info | either | 3-for-3 | hearsay |
|---|---|---|---|---|---|---|
| Opus 4.7 | 224 | 12% | 10% | 17% | 46% | 23% |
| Opus 4.8 | 226 | 3% | 10% | 10% | 44% | 27% |
| Fable 5 | 165 | 5% | 9% | 13% | 68% | 14% |
| GPT-5.6 Sol | 441 | 4% | 6% | 7% | 87% | 3% |
| Opus 5.5 | 352 | 1% | 4% | 4% | 48% | 10% |
| GPT-5.4 | 273 | 1% | 3% | 3% | 72% | 7% |
| GPT-6.1 Sol | 280 | 3% | 2% | 4% | 62% | 0% |
| Opus 4.6 | 219 | 0% | 3% | 4% | 26% | 23% |
| Fable 5.1 | 293 | 1% | 2% | 3% | 59% | 9% |
| GPT-6 Astra | 211 | 1% | 1% | 2% | 64% | 1% |
| GPT-5.5 | 269 | 0% | 1% | 1% | 88% | 2% |

By true character:
- Ravenkeeper bluffs most: 18% claim another role, and 13% fake info. That's the standard real-world play:
  pose as a juicy info role so the Imp kills you and you get your Ravenkeeper reveal.
- Then Saint (6%; hiding the lose-condition) and Virgin (4%).
- Every other character is at or under 3%.
- Fake roles claimed most: Undertaker, Ravenkeeper, Monk, Soldier, Chef. "I'm the Drunk" was a late pivot
  to discredit one's own info.
- Most role liars later came clean (67–100% by model).

Overall: good seats almost never lie outright about their role (2.7%) or their info (4.6%); 5.9% do either. Instead they
hedge with 3-for-3s (62%; GPT models 62–88%, older Claude 26–48%). Games with a good-side role liar: good
won 62% (66 games), versus 69% otherwise.

## 3. Belief probes: detection vs results

Reprocessed 18 November 2026 for issues #3 and #4: raw answers are reparsed and scored against the living
Demon at each survey. The game cohort and win rates are unchanged. The Elo column retains the original
published fit. The corrected website chart uses a different, documented game-weighted six-model average;
see [its data and game list](../../charts/demon-belief.json).
Each seat answers an out-of-game survey before nominations each day, giving P(evil) and P(Demon) for
everyone (`probes.jsonl`).

Columns for good seats, pooled over days:
- P(Imp): probability placed on the true Imp. Chance is ~0.10.
- Imp top: share of probes where the Imp is the seat's top Demon suspect.
- evil AUC: how well the seat's P(evil) ranks evil above good.
- d1/d2/d3: P(Imp) on days 1–3.
- good win: the model's win rate as good.

| model | P(Imp) | Imp top | evil AUC | d1/d2/d3 | good win | detection Elo (original fit) |
|---|---|---|---|---|---|---|
| GPT-6 Astra | .35 | .45 | .88 | .15/.32/.47 | 100% | 1931 |
| GPT-6.1 Sol | .34 | .45 | .82 | .16/.35/.44 | 91% | 1781 |
| GPT-5.6 Sol | .32 | .38 | .78 | .14/.23/.40 | 82% | 1652 |
| Fable 5.1 | .26 | .35 | .71 | .14/.23/.31 | 73% | 1574 |
| Opus 5.5 | .22 | .26 | .73 | .14/.16/.21 | 58% | 1481 |
| GPT-5.5 | .22 | .31 | .77 | .11/.18/.29 | 68% | 1359 |
| Opus 4.6 | .21 | .28 | .65 | .09/.22/.29 | 64% | 1507 |
| Fable 5 | .21 | .26 | .65 | .11/.11/.16 | 65% | 1461 |
| Opus 4.7 | .21 | .22 | .64 | .11/.22/.25 | 50% | 1288 |
| GPT-5.4 | .20 | .26 | .69 | .10/.13/.27 | 47% | 1294 |
| Opus 4.8 | .19 | .16 | .64 | .13/.20/.12 | 34% | 1173 |

- Across models, P(Imp) correlates 0.92 with good win rate and 0.92 with detection Elo from the original fit. "Imp is my top
  suspect" correlates 0.97 with good win rate.
- On day 1 everyone is near chance (.09–.16). The separation comes on days 2–3, and the top GPT models
  double their read.
- As evil, the P(Imp) the opposing town puts on the living Demon correlates −0.82 with evil win rate.
  The lowest town probabilities are for GPT-6.1 Sol, Fable 5 and GPT-5.5 (.19–.20); the highest are for
  Opus 4.6, 4.7 and 4.8 (about .30). These are raw averages, with opponents roughly balanced by the round robin.
- Per game, if the town's day-1 consensus ranks the true Imp in its top 3, good wins 74–80%; otherwise 59%.
