# The Clocktower protocol (v17, frozen)

Language models play Blood on the Clocktower (Trouble Brewing) against each other. One model (or a set
of models) plays every good seat and another every evil seat, so each game rates a detection skill
(good) against a deception skill (evil). Every rule below is one line; the code is the reference
(`clocktower/game.py`, `state.py`, `prompts.py`), and `docs/protocol-history.md` says why each rule is
what it is. A change that affects play bumps `PROTOCOL` in `cli.py` and adds a section to the history.

## Setup
- 10, 11 or 12 players, picked by the seed (10 + seed % 3): always 2 Minions, and 0, 1 or 2 Outsiders.
- The official Trouble Brewing setup for the table size, dealt uniformly at random; one Minion is
  guaranteed to be in play: the plan's choice per game (`--minions`, balanced across a batch), or else
  MINIONS[seed % 4].
- Seats are named Alex, Blair, Casey, … in seating order.
- Every game has its own seed; a side-swapped pair plays one seed twice with the teams' models swapped.

## A day
- Night, then day. At night the Poisoner, Monk and Imp choose first; information roles wake after
  the kill (so a player killed tonight gets nothing), in the official night order.
- Private time: 6 beats. Each beat every player (the dead too) gets one turn and may send one
  whisper, to one or two players, so each holds one private conversation at a time; whispers are
  invisible to everyone else. The prompt states the number of beats and each private turn the whispers
  left today.
- Town square: 3 beats of public speech; no whispers.
- Turn order in every beat is random, in 3 waves: a wave acts at once, later waves see earlier ones.
- Nominations: every living player who hasn't nominated today is asked at once; one nomination
  is taken at random; the nominee defends; everyone gets one comment turn; then a clockwise vote with
  a running tally. Rounds continue until nobody nominates.
- Every day runs the same length; nothing ends a part early. The Slayer can shoot on any public turn.
- Standard rules for thresholds, ties, ghost votes, the Butler (their master is asked first when
  they vote later), Virgin, Slayer, Saint, Mayor, Scarlet Woman and the Imp's starpass.
- Word limits per turn: 150 for speech, whispers, accusations and comments, 200 for a defense, 60
  for a vote remark; longer text is cut and ends in "...", the same for every model.

## The Storyteller (scripted, no LLM)
- Every decision is a choice over all legal values, picked by a random style whose weights are all
  in `state.POLICY` (each weight is a judgment call about what an experienced Storyteller does).
- The style can produce every answer a working ability could give in some legal game allowed by the
  public counts, and never an impossible one (tests check both).
- **Misinformation is false.** On 80% of poisoned nights a poisoned player's result comes from a
  false world, redrawn until it differs from what a working ability could give (when it can); a
  poisoned Fortune Teller's false world has no red herring. The Drunk keeps one false world all game
  (true information in 20% of games), so their story holds.
- **Nothing the setup's counts rule out.** Demon bluffs include one Outsider exactly when the Drunk
  is in play; "Baron" is shown only with a Baron in play; an executed player is shown as the Imp only
  if a Scarlet Woman could have taken over.
- **The Spy sees the whole Grimoire**, including what each pair ability (Washerwoman, Librarian,
  Investigator) was shown.

## Players
- Every seat is one model conversation. Each turn adds only what that seat saw since its last turn;
  the model's own replies (and, where the API allows, its reasoning) carry its memory. No notes,
  no state re-sent.
- Models whose API cannot carry reasoning across turns ("replies only": Gemini 4 Neon, Sonnet 4.5, o1, o3, GPT-5.1,
  5.2, 5.4, GPT-4o) are told so in their system prompt.
- Every seat's text reaches the others in one typography (straight quotes, plain dashes and hyphens,
  no bullets, arrows, emoji or markdown), so writing style can't mark a team.
- Every model plays at its lab's "high" effort, with the same per-turn output ceiling of 8K tokens
  (thinking included). A turn that hits the ceiling is retried once with the least thinking the
  model allows (thinking off for adaptive Claude models that allow it, else low effort; a 1K budget
  for older Claude models; low effort for OpenAI), so thinking stays bounded without losing the turn. Out of credit (auto-reload lagging), a
  call waits up to 30 minutes and retries. A turn cut
  off twice or refused twice passes; a turn with no usable reply after four attempts stops the game,
  which resumes from its last checkpoint.
- When a game outgrows a model's context window, its oldest turns are dropped, never the first
  (its character and setup): the model sees its setup and as much of the recent game as fits.

## Measurement
- Winner, day and reason for every game; every call's tokens and cost; every seat's thinking.
- Belief probes (out-of-game forks that leave the game untouched): at dawn of day 1 and before each
  day's nominations, good seats give P(evil), P(Demon) and a guess for every player; evil seats
  predict what the town believes.
- Ratings: one Bradley–Terry fit with a detection rating (as good) and a deception rating (as evil)
  per entrant and a good-side advantage, in Elo points; probe scores are reported beside them.
