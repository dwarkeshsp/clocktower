# Why OpenAI beats Anthropic: lab-level metrics

Probe metrics reprocessed 18 November 2026 for issues #3/#4. The corrected machine-readable values are in
`metrics.json`; `byday-output.txt` and the survey-derived rows of `analyze-output.txt` were regenerated.
Game outcomes and non-survey measures are unchanged. The chart on the website uses living good players and
equal game weights; this report pools all available good-seat answers, so its percentages differ.

All 386 rated games; no API calls (scripts in `scripts/`, outputs beside this file). "Adj." = value minus what the
same opponent conceded to every other model; brackets are 90% bootstrap intervals over the 193 side-swapped pairs. The like-with-like comparison is the summer/autumn generation:
**Claude** (Fable 5, Fable 5.1, Opus 5.5; 106 good games) against **OpenAI** (GPT-5.6 Sol, GPT-6 Astra, GPT-6.1 Sol;
121 good games). To check that the GPT-6 family is not doing all the work, I repeat each comparison against
**GPT-5.6 Sol alone** (57 games, July).

## The answer

**Claude towns start near OpenAI towns, but improve less on several later-game measures.** On day 1 the two labs are level.
Claude's day-1 executions actually hit evil slightly more often (44% vs 39%). From day 2, OpenAI towns turn the
evidence that piles up (deaths, execution results, night information, contradictions) into a correct consensus:
- Their top suspect is evil 52% of the time on day 1, 70% on day 2 and 81% on day 3 and later.
- Claude towns go 44%, 45%, 53%. Their Brier score on who is evil stays flat from day to day; OpenAI's falls by a third.

So Claude towns keep executing their own players after day 1, mostly players whose claims nobody can check
(Soldier, Butler, Mayor, Ravenkeeper). In every group, a good team that executes at most one good player wins
essentially every game. Claude towns executed two or more in 61% of games; OpenAI towns did in 31%.
- **It is not just GPT-6.** GPT-5.6 Sol shows the same learning curve (36%, 62%, 75%), and most of the gaps hold
  against it alone.
- **Not "Anthropic was always behind":** early-2026 models of both labs (Opus 4.6–4.8, GPT-5.4/5.5) were level
  and mostly flat after day 1. OpenAI's July+ models learned to accumulate evidence; Fable 5.1 and Opus 5.5
  (September) still play like GPT-5.5 (April).
- **Not the harness:** settings are symmetric and Claude seats do keep their earlier reasoning.

## The metrics that separate the labs (good side)

| Metric | Claude new | OpenAI new | Adj. gap | Adj. gap vs 5.6 Sol only |
|---|---|---|---|---|
| Good wins | 65% | 89% | −23 pts [−32, −14] | −16 [−26, −5] |
| Day-1 executions that hit evil | 44% | 39% | +12 [0, +23] | +20 [+6, +35] |
| **Day-2+ executions that hit evil** | **46%** | **72%** | **−27 [−33, −20]** | **−19 [−27, −12]** |
| Town's top suspect* is evil, day 2 | 45% | 70% | −26 [−36, −16] | −20 [−31, −8] |
| Town's top suspect is evil, day 3+ | 53% | 81% | −30 [−37, −22] | −24 [−33, −15] |
| Town P(Demon) on the living Imp, day 3 | 0.23 | 0.42 | −0.20 [−0.27, −0.15] | −0.18 [−0.26, −0.11] |
| Rise in a seat's P(evil) on a real evil player after a teammate names them to it | +0.09 | +0.16 | −0.06 [−0.08, −0.05] | −0.06 [−0.08, −0.04] |
| Games with 2+ good players executed | 61% | 31% | +29 [+19, +39] | +14 [+2, +27] |
| Good players executed per game | 2.02 | 1.19 | +0.80 [+0.52, +1.06] | +0.36 [+0.04, +0.70] |
| … of them, unverifiable roles (Soldier, Mayor, Ravenkeeper, Outsiders, …) | 1.35 | 0.65 | +0.66 [+0.44, +0.87] | +0.28 [+0.01, +0.56] |
| Good voters' yes on good nominees | 34% | 23% | +10 [+7, +14] | +8 [+4, +12] |
| Wins when 2+ good players were executed | 43% | 66% | (raw) | 62% for 5.6 Sol |

*Top suspect: the living player with the highest mean P(evil) across the living good seats, from the probe
taken before nominations.

Learning curve by model (top suspect is evil, day 1 / 2 / 3+):

| Model | d1 | d2 | d3+ |
|---|---|---|---|
| Fable 5 | 25% | 25% | 51% |
| Fable 5.1 | 54% | 43% | 56% |
| Opus 5.5 | 45% | 54% | 52% |
| Opus 4.6 / 4.7 / 4.8 | 52 / 29 / 45% | 39 / 35 / 28% | 46 / 51 / 33% |
| GPT-5.4 / 5.5 | 36 / 47% | 42 / 47% | 61 / 67% |
| **GPT-5.6 Sol** | 36% | **62%** | **75%** |
| **GPT-6.1 Sol** | 53% | **77%** | **86%** |
| **GPT-6 Astra** | **88%** | **84%** | **96%** |

The newer Claude models improve less on this measure; OpenAI models from July climb steeply. Only Astra is also sharp on day 1 (a GPT-6 trait
on top of the shared curve).

Older generation (Opus 4.6–4.8 vs GPT-5.4/5.5): good wins −8 points [−21, +4], good players executed +0.04 per
game (no difference). The one large old-generation gap is the Saint: 0.15 executions per game for old Claude
towns against 0.01 for OpenAI. Of 20 games lost to a Saint execution, 18 had a Claude good team.

## What the Claude towns do instead

- **They suspect players whose claims can't be checked.** When the town's top suspect is good, it is usually a
  Soldier, Ravenkeeper, Mayor, Butler or Saint. Claude towns execute such players at twice the OpenAI rate.
  Example: `f2-opus55-v-sol61/game-01` day 1, "let's test it and I'll read it tomorrow"; the real Soldier died 10–1.
- **The mistakes are their own.** 68% of the good players Claude towns executed were nominated by good players
  (OpenAI towns: 77%). Evil does not have to lead these executions.
- **They update slowly in both directions.** When a teammate names a real evil player to a Claude seat, its P(evil)
  on that player rises 0.09; an OpenAI seat's rises 0.16. Claude seats also clear good players more slowly
  (+0.02 to +0.03 adj.). Beliefs stay muddy, so votes follow whoever is nominated.
- **They follow consensus more (78% vs 61% of executions), but that isn't the error.** Following the top suspect
  helps both labs (hit evil 48% / 75%, vs 33% / 40% otherwise). Claude's consensus is simply wrong more often.

## What does NOT explain it

- **Credulity toward evil role claims.** I measured how often a good seat's best guess of an evil player's
  character is a good role. Claude seats do this *less* than OpenAI seats on day 1 (63% vs 67%; vs 5.6 Sol 63% vs
  75%). By day 3 they do it about equally against 5.6 Sol (36% vs 31%, gap not significant). Only against GPT-6 do
  they trail (36% vs 26%). Claude seats do give evil "claimants" 3–5 points less P(evil). That is real but small.
- **Being swayed by evil whispers.** A good player named to a Claude seat only by evil players moves that seat's
  P(evil) by about the same amount as one named only by good players, or by nobody. The gap is general inertia,
  not a weakness for evil pressure.
- **Vote herding, given the tally.** On good nominees after a mostly-yes tally: Claude yes 51%, OpenAI 46% (mostly
  no: 14% vs 7%). Claude's extra yes votes come from nominating good players more (2.3 vs 1.5 per game).
- **Verbosity and over-sharing.** Claude writes about 40% more words per message. But Opus 5.5 is as terse as the
  GPT models (38 words per public message) and detects no better than Fable 5.1. Claude claims publicly on day 1
  more often (64% vs 53%), but so does Sol 6.1 (66%). The Demon's kills hit an information role 52% vs 53% of the
  time, so over-sharing does not feed the Demon. Claude seats also *ask for claims first* more often (30% vs 19% of
  day-1 good whispers).
- **Thinking effort.** New Claude models think *more* per call than new OpenAI models (326 vs 219 tokens); GPT-5.4
  thinks the most of any model and is near the bottom.

## Harness and validity checks

- **Settings are the same for every model:** "high" effort on both sides of all 406 game configs, and the same 8K
  per-turn ceiling.
- **Memory works for Claude.** In every Claude model, the billed context of each turn grew by at least the
  previous turn's full output, thinking included, in 99.7–100% of turns (`memory_check.py`). So the earlier
  reasoning stays in context. The only memory asymmetry is GPT-5.4, which keeps replies only (93% of turns). That
  handicaps OpenAI, not Anthropic.
- **Lost turns: a real handicap, but only for Fable 5.** Fable 5's good seats lost 1.35 turns per game: 27 turns
  in 20 games where both the first try and the low-effort retry hit the 8K ceiling. Every other Claude model lost
  ≤0.1 per game; OpenAI lost none. That hurts Fable 5's rating slightly. It cannot explain Fable 5.1 or Opus 5.5.
- **Open question: Claude skips thinking on votes.** At "high", Claude's adaptive thinking skips thinking on 74% of
  good vote turns. GPT-5.6 Sol skips 5%, the GPT-6 pair about 60%. Votes cast without thinking follow the tally
  more in *both* labs: for a good nominee with a yes-leaning tally, Claude votes yes 56% of the time without
  thinking and 39% with it; OpenAI 60% vs 43%. That is a correlation; the thinking may switch on exactly when a
  vote looks hard. Astra and Sol 6.1 also skip most vote thinking and are the best detectives, so skipping is not
  enough to explain the gap.
  - A forced-thinking run (Claude at "max", or a fixed thinking budget on votes) against GPT-5.6 Sol would settle
    it; the e1 effort sweep was too small to read.

## Evil side (secondary)

- **Pooled, Anthropic evil wins 12 points less** (adj., [−20, −5]). In the new generation the gap is −5 [−15, +5],
  and against 5.6 Sol alone it is +10 [−3, +22]. So the evil gap comes from old Claude and from the GPT-6 pair,
  not from the labs as such.
- **Claude evil teams are louder, not more in charge:** public words 1.09× their seat share vs 0.87× (GPT-6
  ~0.6×, Opus 5.5 0.82×), yet fewer of the nominations (27% vs 34%), and the town puts more P(Demon) on their Imp
  by day 2 (+0.09 adj. [+0.06, +0.12]).

## Caveats

- **Survivorship:** day-2+ metrics count only games still running; OpenAI's are then the harder games, so the
  learning gap is if anything understated.
- The probe is a mean over seats (it mixes accuracy with agreement); believed characters are parsed by keyword and
  claims by an "I'm the X" regex (an undercount, same for every model).
- **Opponent adjustment** uses pooled rates against each opponent. It removes who-played-whom, but not which seed
  (setup) each game had.
- About 100 games per lab per generation (Fable 5: 20); single-model rows are indicative.
- **This is correlational.** "Doesn't accumulate evidence" describes what Claude towns fail to do; it does not say
  which reasoning step breaks. A transcript reader comparing same-seed pairs from day 2 on (for example the
  `f3-gpt56sol-v-opus55` and `f3-fable51-v-sol61` pairs) is the next step.
