# Game logs by protocol version

Each game directory holds `events.jsonl` (every event, with who could see it), `transcript.md`
(omniscient replay with summarized thinking), `conversations/` (each seat's full API conversation),
`calls.jsonl` (per-call usage and cost), `config.json` (settings, including `protocol`),
`result.json` and, from v5 on, `probes.jsonl` (belief probes; see below). The current version is `PROTOCOL` in `clocktower/cli.py`; bump it (and add a section
here) whenever a change affects how games play.

## v1 — development (Sept 25–26, 2026)
Beats where a turn could both speak publicly and whisper; everyone saw who whispered whom (not the
words). LLM Storyteller (Opus 5.5). `batch-001` let the Storyteller choose setups (it chose the same
information-heavy one every game); from `batch-002` setups are uniformly random. Good won 11 of 12.

## v2 — baseline 40 (Sept 26–27)
v1 plus even-handed strategy tips in the player prompt. `opus-20` (Opus 5.5) and `astra-20`
(GPT-6 Astra), same seeds. Good won 40 of 40. Diagnosis: public whisper metadata let good find the
evil pair; everyone claimed truthfully on day 1; the LLM Storyteller undid evil's misinformation
and mode-collapsed (Drunk as Empath 25 of 34 times); the engine announced voided Butler votes.

## v3 — private time, then town square; scripted Storyteller (Sept 27)
Each day: 3 private beats (whispers only, invisible to others, up to 2 per turn), then 3
town-square beats (public only), then nominations. Scripted Storyteller policy (consistent false
picture for impaired players). Butler leak fixed. `phased-10`: good 6, evil 4.

## v4
v3 plus: up to 3 whispers per turn; players named in the town square answer first in the next
beat; batches rotate the Minion; the scripted Storyteller no longer excludes any legal option (the
Saint or Drunk can be the red herring, the Drunk's apparent role can be a bluff, a Mayor kill can
bounce to anyone); a drunk Fortune Teller's false picture has two "evil" players.

## v5
v4 plus a fixed day: 3 private beats, 3 town-square beats, then nominations, every day. No
early end (v4 ended the town square when most living players called for nominations or a beat
was silent, which cut 20 of 34 v3 days short); `call_nominations` is gone, and day 1 no longer
has its own private-beat setting. Nominations gain a comment turn for everyone between the defense
and the vote; remarks during the call for nominations are gone (only accusations are heard). The
Slayer can shoot on any public turn, not just the town square. The scripted Storyteller rules
nothing legal out: 10% of each decision is uniform over all legal values, and the style is
weights only (20% of Drunks get true information all game; the Spy can register as an in-play
character; the Recluse can register as the Imp; a misinformed Washerwoman sometimes shows only
good players; a misinformed Librarian is sometimes told zero Outsiders). The LLM Storyteller
option is removed.

Telemetry (does not change play, so no version bump): from Sept 27, v5 games also record belief
probes. At dawn of day 1 and just before each day's nominations, every seat answers an
out-of-game question on a fork of its conversation (same model, effort, thinking and schema, so it
reads from cache); the question and answer never enter the seat's conversation, and its pending
events stay pending. Good seats give P(evil), P(Demon) and a character guess for every other
player; evil seats predict what the good players believe; everyone states their claim and a
one-line plan. `tests/` checks that probes leave every seat's turns identical. Scores:
`python -m clocktower analyze`.

Batch x1 (Sept 27): seven model pairings on seeds 6000–6009 (Opus 5.5, Sonnet 5, GPT-6 Astra;
see `python -m clocktower analyze games/v5/x1-*/game-*`). Astra vs Astra was stopped after 5 games
(its first run was throttled by an 8-thread limit on OpenAI requests and discarded).

## v6 (Sept 27)
Changes from v5, after reading 61 v5 games (seven model pairings) and auditing the rules and the
Storyteller against 2,750 simulated games:
- Night order: the Poisoner, Monk and Imp choose first; the Fortune Teller and Butler are woken
  after the kill, so a player killed that night is never asked to choose (v5 asked everyone at
  once, and a Fortune Teller killed that night "chose" and heard nothing, which read as a lie).
- Starpass: a Monk-protected Imp cannot starpass; poison ends when the Poisoner becomes the Imp.
- Interface: whispers to more than two players (or beyond three a turn) tell the sender what was
  dropped; a blocked Butler's vote remark is not shown; a vote with neither yes nor no is asked
  again; speech caps rise (turn 150 words, defense 200) and a cut line ends "[cut off]"; the
  nomination notice says the pick among simultaneous nominations was random.
- Player prompt: the night order, and that nothing is revealed when a player dies.
- Storyteller: misinformation is false (when the style misleads an impaired player, a value a
  working ability could show is moved to the nearest plausible one it could not; in v5 about half
  of drunk/poisoned Chef, Empath, Fortune Teller and Undertaker results were true). A misinformed
  Undertaker is never shown "Imp", and impaired players are never shown their own character.
  The uniform floor drops from 10% to 3% (still over every legal value). The Drunk's apparent
  character is among the Demon bluffs 5% of the time (v5: 32% of Drunk games), the Drunk 5%. An
  Investigator's second player is good 90% of the time; a Mayor bounce lands on the Minion 5%;
  the red herring is a Townsfolk other than the Fortune Teller 85%. A Spy registering to a
  Washerwoman or Librarian as a good character uses the bluff / in-play / other weights.
- Budget: the per-turn output ceiling is 8K tokens (v5: 16K), identical for every model. It cuts
  runaway thinking loops (0.2% of Sonnet 5 turns went past 8K) and no Opus or Astra turn.
- Runs: no request cap (every game and seat at once); every game in an experiment has its own
  seed; teams can have their own effort (`--good-effort`, `--evil-effort`). OpenAI reasoning
  summaries use `concise`, the only setting that reliably returns text (logging only).

Grid g1 (Sept 27–28): Opus 5.5 high, Opus 5.5 low, Sonnet 5, GPT-6 Astra, GPT-6 Sol; all 20
good-vs-evil pairings, 5 games each, seeds 20000–20099. The Anthropic account ran out of credit
twice mid-run: the first time, seats silently passed and 84 games were discarded and rerun; after
that a failed seat stopped its game (then waited for credit) and stopped games were rerun.

## v7 (Sept 28)
Changes from v6, after 8 readers went through the 100 g1 games and a second rules/Storyteller audit
(6,000 simulated games):
- Private time: up to 2 whispers per turn (v6: 3). With 3, every claim reached nearly every seat on
  day 1, which made role-count solving easy and good won 69% (Astra 20/20 and Sol 18/20 as good).
- No uniform floor (v6: 3% of every decision uniform over all legal values). The style is itself
  random and can produce every answer a working ability could give in some legal game (a test
  checks this per information role); the floor only added impossible answers (a drunk Chef told
  "4 pairs"), which gave impaired players away.
- Misinformation comes from one coherent false world: a framed good player is the Demon, one other
  player the Minion, the real Demon looks good, and the Recluse registers as usual. Results are
  what a working ability would show there (so they look like real results, and some are true
  where the false world agrees with the real one). v6 moved every misinformed value off the
  truth, which made it near-inverted: a misinformed Fortune Teller's answers were the opposite of
  the truth, and a known Drunk's numbers could be read backwards. A misinformed Undertaker is shown
  "Imp" only when a Scarlet Woman could have taken over (5+ alive at the execution).
- A misinformed Librarian is never told "zero Outsiders"; a misinformed Investigator is shown the
  Baron only in a Baron game; a Spy registering as a good character is never shown as the
  recipient's own character.
- Registration is weighted a little more toward evil: the Spy registers evil 10% (v6: 25%), the
  Recluse 50% (40%), information roles are shown a misregistering Spy/Recluse 50% of the time (30%),
  and an evil player shown as a good character is a Demon bluff 70% (50%), in play 10% (20%).
- Butler: may vote yes only if their master has already voted yes; otherwise the vote is a no and
  only the Butler is told why. (v6 accepted a yes before the master voted and then dropped it,
  so the public roll and the total disagreed, which confirmed Butlers.)
- The Spy sees the Grimoire but not the verbatim information given that night. A red herring is
  set whenever anyone believes they are the Fortune Teller (the Drunk too). Vote remarks may be
  60 words. Turn prompts no longer say "group w of N" (players used it as a timestamp).
- Per-turn output ceiling 4K tokens, thinking included (v6: 8K). No frontier model's turn went past
  4K in v6/v7 games; older models (GPT-5.1, 5.4) think longer per turn, so a lower cap would cut them.
- Models that don't see their own earlier reasoning (see the memory check below) are told so in one
  prompt line instead of being told their thinking carries over; the prompt is otherwise identical.
- Table size: `--players 5-15` deals the official Trouble Brewing setup for that count (e.g. 12
  players: 7 Townsfolk, 2 Outsiders, 2 Minions, the Imp). Minions learn each other as well as the
  Demon; the Imp learns all its Minions; a starpass goes to a Scarlet Woman who can take over, else
  the Storyteller picks a living Minion. The default is still nine. The day cap is 15.
- Runs: `--swap` plays every seed a second time with the models' sides swapped; `analyze` reports
  Saint-execution wins per pairing.

### Model memory check (Sept 28)
Does a model see its own earlier reasoning on the next turn? Turn 1: "think of a secret number and
animal, reply only ok"; turn 2: "reveal them, or say NO ACCESS". Each model ran 3 trials with its
reasoning carried back (as the engine does) and 3 with it stripped (control).
- Sees its earlier reasoning: GPT-5.5, GPT-5.6 Sol, GPT-6 Astra, GPT-6 Sol, Claude Opus 4.5 (and,
  per Anthropic's docs, every later Claude; Opus 5.5's reveal turn is blocked by its
  reasoning-extraction classifier).
- Replies only (NO ACCESS even when carried): o3, GPT-5.1, GPT-5.2, GPT-5.4, Claude Sonnet 4.5.
- Not testable: GPT-5 (requires a verified OpenAI organization).
- Nov 28: Gemini 4 Neon is replies only: NO ACCESS 3/3 carried and 3/3 stripped. Its thought parts and
  thoughtSignatures are still sent back, as Google's API asks, but the model cannot read them. Its effort ladder
  (low, medium, high, xhigh, max) matches the other labs', so it plays at high like everyone else; it rejects
  `minimal`, so its ceiling retry runs at low. The two g1 pilot games ran before this check, with the
  "reasoning" prompt line, and are left out of the ratings.
The engine records each team's memory mode in config.json (`good_memory`, `evil_memory`).

Calibration c1 (Sept 28): Opus 5.5 vs Opus 5.5 and GPT-6 Sol vs Sol, at 9 and 12 players, 10 games
each (seeds 30000–30309). Evil won 2, 3, 2, 2 of 10. Four readers found good's edge is mostly skill
and the claim meta (near-universal day-1 claims make role counts solvable), plus three engine
issues, fixed in v8. Twelve players add real two-Minion play (busing, starpasses, Scarlet Woman
catches, joint framing); Opus games ran a day longer at 12, Sol games did not.

## v8 (Sept 28)
v7 plus three fixes from the c1 calibration:
- The false world behind misinformation has as many Minions as the real game (v7 always had one,
  which biased false Chef/Empath numbers low at 12 players).
- Misinformation about a good player follows the false world: a misinformed Undertaker or
  Ravenkeeper sees an unframed good player as their real character (the Recluse registering as
  usual), and no good player is ever shown as one of the Demon's bluffs (none can be one in any
  world). v7 showed them a random other character, which exposed the Drunk and collided with evil's
  bluff claims.
- Butler: when the Butler's turn comes before their master's, the master is asked first (their vote
  is still shown at their own seat), so the Butler sees whether their master's hand is up and may
  vote with them. v7's strict rule locked Butlers out whenever the master sat later (13 of 21 and
  17 of 35 Butler votes in two batches).
- The per-turn ceiling is 4K and replies-only models are told so (see v7 notes).

Timeline t1 (Sept 28, aborted after ~30 minutes, $1,107): 14 models, 21 matchups, 12 players. Stopped
because (1) the OpenAI organization hit its configured spend limit, which stopped 133 games, and
(2) the 4K per-turn ceiling cut real turns far more than in the smoke tests: GPT-5.1 33% of game
calls truncated (135 turns lost), o3 6%, Opus 4.8 4%, GPT-5.4 3%, Fable 5 2%. The partial games in
games/v8/t1-* are not usable for ratings.

v8 from Sept 28 (after t1): the per-turn output ceiling is 16K tokens, a guard against runaway loops
rather than a thinking budget (a 4K ceiling cut 33% of GPT-5.1's turns and lost 135 of them;
replies-only models re-derive the game every turn). Each model's thinking tokens and cost per game
are reported next to its rating. Runs are supervised: `python -m clocktower supervise` pauses a run
on stopped games, lost turns, >1% capped turns, refusals, stalls or overspend.

t2 (Sept 29, paused with 33 of 210 games finished): the supervisor killed every batch twice on
transient API errors (one HTTP 520, then three Opus 4.6 overloads), losing the games in progress. Since
then every 5xx is retried, overloads wait, the supervisor kills only on overspend, and `run` resumes a
batch (finished games are kept).

## v9 (Sept 30)
v8 game rules, unchanged. Two setup changes:
- The table size can vary: `--players 10-12` gives each game 10 + seed % 3 players, so every
  table has two Minions (Trouble Brewing's 10–12 band) and 0, 1 or 2 Outsiders. A side-swapped
  pair shares its seed and so its table size.
- The Minion guaranteed to be in play is picked by seed (MINIONS[seed % 4]), not by the game's
  number within its batch, so batches of one pair still rotate Minions. (`--games 1 --swap` now
  plays both games of the pair; before it silently played one.)
New models: GPT-6.1 Sol (`gpt-6.1-sol`, $2/$10, carries its reasoning: memory check 3/3 carried,
3/3 NO ACCESS stripped) and Sonnet 5.5 (`claude-sonnet-5-5`, $2/$10; the memory check is refused as
reasoning extraction, so its memory is assumed like other adaptive-thinking Claude models and is
checked in transcripts). Effort "max" is accepted by both labs: on a smoke turn Opus 5.5 thought
~5,000 tokens at max against ~300 at high, GPT-6 Sol ~1,900 against ~600.

e1 (Sept 30, 60 games, 30 side-swapped pairs, seeds 60000–60029, 10–12 players): a spread of old
and new models plus an effort sweep (Opus 5.5 and GPT-6.1 Sol at low, medium and max against the
other at high). Opus 5.5 at max effort thought 3–10K tokens a turn and hit the 16K ceiling (one evil
turn lost), so that pair was restarted on the same seed with a 64K ceiling
(`e1-opus55max64k-v-gpt61sol`); the sweep measures what effort buys, not truncation. All other
games use the 16K ceiling.

## v10 (Sept 30)
v9 plus fixes from the e1 engine audit (no rule violations and no impossible information were found
in e1 or in 1,500 simulated games; these are Storyteller judgment calls and wording):
- Librarian with no Outsider in play: v9 always pointed them at the Spy (78 of 78 in simulation),
  never "zero", a tell and a legal answer the style could not give. Now the Spy is used with
  probability `misregister_pair`, as for every other pair ability; otherwise "zero".
- A Ravenkeeper who picks themselves learns the character they think they are (a Drunk Ravenkeeper
  was shown "Drunk").
- A sober Undertaker or Ravenkeeper shown an executed Spy as a good character is never shown their own.
- Wording: the Imp's prompt says "one of your Minions" becomes the Imp; a self-nomination says "you
  have nominated yourself"; the notice about a whisper to 3+ players keeps names' capitals.

## v11 (Oct 1)
v10 plus, from the second e1 read:
- Every seat's text reaches the others in one typography (straight quotes, " - " for dashes, "..."
  for an ellipsis, no markdown `*`, backtick or `#`). In e1 the GPT models wrote curly apostrophes in
  96–100% of messages and Claude models never did, so in a cross-lab game the evil team could be
  picked out by punctuation alone (a surface-feature test put 2.1 of 3 evil players in its top 3,
  chance 0.82). No player noticed, but a stronger one could. Raw replies stay in conversations/.
- Prompt wording: "up to 2 whispers this turn" (o3 and Sonnet 4.5 read it as per private time), and
  the comment turn asks players not just to announce their vote (the vote prompt already did).

## v12 (Oct 1)
v11 plus the Storyteller changes from the e1 Storyteller read, stated as three principles:
- **Misinformation is false.** A poisoned player's result comes from a false world that is redrawn
  until the result is not one a working ability could give (when one exists). In e1 only 39% of
  poisoned results were false, because the false world often agreed with the truth. The Drunk keeps
  one false world all game, so their story holds.
- **Nothing the setup's counts rule out.** Demon bluffs include an Outsider only when the Drunk is in
  play (then the town sees one Outsider fewer than the setup has, so one evil Outsider claim fits;
  otherwise it breaks the count: 3 of 4 such claimers were executed by day 2 in e1). "Baron" is shown
  (for a Recluse, a framed player, or a misinformed Investigator or Undertaker) only when the Baron is
  in play; "Imp" for an executed player only when a Scarlet Woman could have taken over (5+ alive);
  a misinformed Librarian at a table with no Outsiders learns "zero", as it would in its false world.
- **The Spy sees the whole Grimoire**, including what the Washerwoman, Librarian and Investigator
  were shown (the official reminder tokens, dropped in v7).
Also: turn order in every beat is plain random (the "players named in the last beat go first" rule
did almost nothing: 80% of the table is named each beat); the per-turn output ceiling is 32K for
every model (GPT-5.1 re-derives the game each turn and lost 6 turns at 16K in e1; no model at high
comes near 16K otherwise); OpenAI requests time out after 15 minutes.

c2 calibration (Oct 1, 12 games, seeds 70000–70005, `games/v12/c2-*`): the v12 rules worked (6 of 8
poisoned results false, against 39% in e1; Outsider bluffs only with the Drunk; the Spy's reminders
used for a Saint bluff; no capped turns at 32K). One gap, fixed before the freeze: the false world
kept the real red herring, so a poisoned Fortune Teller pointing at it always heard a true YES (it
decided one game). Final v12: a poisoned Fortune Teller's false world has no red herring (simulated
false rate 60% -> ~80%, like the other roles). The c2 games ran before that fix.

c2 outcome: 10 of 12 games finished, good 9 and evil 1 (the long games that usually go to evil were
the two lost). One game stopped on day 6 when OpenAI closed the connection before replying, 10 times
in a row, at high effort; OpenAI requests are now streamed (server-sent events), which keeps bytes
flowing during long thinking (max gap 6 s in a max-effort test). One GPT-5.1 game was killed at day 3
by a container restart. Fable 5 as good cost $88 in one 6-day 12-player game (~$10 per seat-game),
far above e1's short-game average: budget the flagship with care.

## v13 (Oct 2)
v12 plus a bounded thinking rule, for the older models in the flagship timeline: the per-turn ceiling
is 8K tokens (was 32K), and a turn that hits it is retried once at low effort (older Claude models: the
minimum 1,024-token thinking budget) rather than at the same ceiling. OpenAI's reasoning models take no
thinking budget, only a total-output limit that leaves a turn with no answer, so a low-effort retry is
the clean way to bound thinking without losing turns. Share of e1/c2 turns over 8K: GPT-5.1 28%, o3,
GPT-5.2/5.4 and Opus 4.8 about 3%, Opus 4.6 0.7%, newer models ~0%; at 2K or 4K the fallback would
become the normal setting for older models (o3 and GPT-5.4 40% at 2K), an uneven budget, so 8K.
GPT-5 (verified Oct 2) thinks ~3K tokens even on trivial turns and sees only its replies (checked).
Calls record the effort each attempt used. The GPT-5 family's 400K window is registered so an
oversized game is trimmed, not failed.

## v14 (Oct 2): one conversation at a time
v13 with private time restructured, at the maintainer's suggestion: 4 private beats (was 3) and one whisper
per turn (was up to 2), still to one or two players. In a real game a player is in one private
conversation at a time; two whispers a turn let a player run two secret conversations at once and
blast a claim to four people per turn (in e1, 85–100% of good seats whispered their role on day 1,
and the good team read as one mind). More beats with one whisper each gives more back-and-forth and
makes whom you talk to a visible choice. Cost: private time was ~34% of spend with 3 beats; 4 beats of
one whisper is roughly +10% cost and wall-clock. A 6-beat variant (`--private-beats 6`) is tested
alongside. The w1 experiment (50 games) checks whether it tilts balance toward either side.

w1 (Oct 1, 50 games, seeds 90000+, `games/v14/w1-*`; reader reports in docs/findings/protocol-design/w1/): evil won 12/38
at 4 private beats (32%) and 5/12 at 6 (42%), against 19/58 (33%) under the old 3x2 rule for the same
model pairings: no detectable shift (adjusted odds ratios 1.06 and 1.38, wide intervals). The "hive mind"
comes from public day-1 claims, not whispers: good players named their role to ~2 people in private
under both rules, and two-thirds claim publicly on day 1. Private talk reads more like a real table;
6 beats raises real back-and-forth threads (3+ messages, 2+ turn changes) from 24% to 36% (old rule
33%) for ~30% more private-time spend. Evil still briefs both Minions in beat 1 (39/40, one whisper to
both). The harness read found model tells (GPT-5.1 non-breaking hyphens, o3 bullets/emoji, o3-only
"[cut off]") and silent passes on repeated non-answers; both fixed. Three container restarts during w1
killed games in progress, which led to checkpoints at every dusk and Hugging Face snapshots.

## v15 (Oct 2): a public whisper log, 6 beats
v14 with three changes, all the maintainer's. (1) After each private beat everyone, the dead too, sees who
whispered to whom (not the words), as at a real table where you see who steps aside together. The w1
realism read found "swarms" (many players whispering the same popular player) and evil briefing both
Minions in beat 1 unseen; at a real table both would be visible. Expected to cost evil something. (2)
6 private beats by default (w1: more real back-and-forth than 4). (3) The prompt states the number of
beats ("6 beats ... choose carefully whom to spend them on"), each private turn says how many whispers
are left today, and both say the log is public. Also from the w1 harness read: one typography filter for
hyphen variants, bullets, arrows and emoji; cut text ends "..." for every model; a seat with no usable
reply after 4 attempts fails the game instead of passing silently; a notice when someone speaks aloud in
private time. c3 calibrates it: the same 10 side-swapped pairs at 6 beats (arm A) and 8 beats (arm C).

c3 (Oct 2, 40 games, seeds 110000+, `games/v15/c3-*`): evil won 4/19 at 6 private beats and 4/20 at 8,
against about a third without the log (w1). Evil did not adapt to the public log: 97% of evil seats sent
their first whisper to a teammate, and 43–46% of evil's day-1 whispers went to teammates (about 20% by
chance). 6 and 8 beats did not differ. c3h (10 games on arm A's seeds) added one neutral line to the
prompt ("The whisper log is evidence ... players who huddle early and often get read as a team"): evil's
first whisper still went to a teammate 83% of the time, and evil won 1 of 9. The maintainer dropped the log.

## v16 (Oct 2): private whispers again, 6 beats
v15 without the public whisper log (and without the c3h hint): whispers are invisible again, as in v14.
Kept from v15: 6 private beats, the prompt's statement of the number of beats ("choose carefully whom to
spend them on") and the whispers left on each private turn, and the harness fixes.

f2 (Oct 1, 109 of 110 games, `games/v16/f2-*`, readers in docs/findings/round-robin-2026/): the 11 models released in 2026,
full round robin, one side-swapped pair each, $4.4k. Engine sound; two clear tiers (Fable 5 onward
+360 Elo); 25% duds, mostly older-model blunders and deal luck. Two defects: (1) the low-effort retry
did not bound adaptive-thinking Claude models: Opus 4.8 re-hit the 8K ceiling on 40% of retries and
lost 76 turns; (2) plan seeds stepped by 100 (= 0 mod 4), so every game's guaranteed Minion was the
Poisoner.

## v17 — current (Oct 1): bounded retries, chosen Minions
v16 with: a ceiling retry uses the least thinking the model allows (thinking off for adaptive Claude
models); the guaranteed Minion is set per game by the plan so a batch balances them; OpenAI and
OpenRouter calls wait for credit (auto-reload) like Claude calls. Opus 4.8's 20 f2 games are dropped from
the fit; f3 adds 184 games (~$3.8k); f3b 78 more (~$1.2k) replacing Opus 4.8's 20 f2 games with fresh balanced ones by an information-per-dollar allocation (at most 4 extra pairs
per matchup, mostly near neighbours), with guaranteed Minions chosen to balance the totals.

Result (Oct 2): 352 games (f2 minus Opus 4.8's 20 + f3 + f3b; 262 v17 games, ~$7.2k). Evil wins 32%. The 2026
releases gain ~645 Elo a year (90% CI 530 to 820); detection +634, deception +692, not separable. Top:
GPT-6 Astra 1858, GPT-6.1 Sol 1729; Anthropic's best Fable 5.1 1595; lowest Opus 4.8 1194. Setup effects
(Elo toward good vs Poisoner): Spy +67, Scarlet Woman -67, Baron +80; 12 players +68. Ratings: `python -m clocktower ratings`
(docs/plans/f2-ratings.json; the current fit, 386 games with f4 and f5, is in the README).
