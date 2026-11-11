"""Bad Moon Rising (experimental): a second script on the Trouble Brewing table.

The day (beats, nominations, votes), the seats, the logs and the checkpoints are game.py's. This
module replaces what the script changes: setup, the night, how players die (and don't), and how
the game ends. The Gossip is left off the script (characters.py says why).

What the script needs that Trouble Brewing did not:
- Drunkenness and poison come from many abilities, each with its own source and end. They are
  kept as a list of effects; an effect lapses when its source dies or is itself drunk or poisoned.
- Death goes through one gate (`BMRGame.kill`), which knows every reason a player can't die.
- A player's team can change (Goon), and a player can look dead while alive (Zombuul); state.Player
  carries both.
- The night is resolved in the official order, in four rounds of questions, so that a player
  killed or exorcised earlier in the night is never woken.
"""
from __future__ import annotations
from itertools import combinations

from .agents import Request
from .characters import BMR, SETUPS, card, kind
from .game import Game
from .prompts import dawn_narration
from .state import Choice, Grimoire, yes_choice

DEMONS, MINIONS, TOWNSFOLK, OUTSIDERS = BMR.demons, BMR.minions, BMR.townsfolk, BMR.outsiders

# How the scripted Storyteller uses its discretion on this script (state.POLICY is Trouble Brewing's).
# First guesses at what an experienced Storyteller does; none has been tuned on games yet.
POLICY = {
    'lunatic_same_demon': 0.7,   # the Lunatic believes they are the Demon that is in play (else another)
    'lunatic_minion_good': 0.8,  # each of the Lunatic's false Minions is a good player (else anyone but the Demon)
    'grandchild_townsfolk': 0.8,  # the Grandmother's grandchild is a Townsfolk (else any good player)
    'sailor_drunk_if_good': 0.5,  # the Sailor chose a good player: the Sailor is the drunk one (else the target)
    'sailor_drunk_if_evil': 0.25,  # the Sailor chose an evil player: the Sailor is the drunk one
    'innkeeper_drunk_evil': 0.7,  # the Innkeeper chose one evil and one good player: the evil one is drunk
    'pacifist_saves': 0.4,       # an executed good player is saved by the Pacifist
    'tinker_dies': 0.1,          # per night: the Tinker dies
    'regurgitate': 0.3,          # the Shabaloth brings back a player it killed last night
    'impaired_false': 0.8,       # a drunk or poisoned player's information is false (else true)
}


def team_sizes(n, outsiders=0):
    """(Townsfolk, Outsiders, Minions) for n players, with the Godfather's -1 or +1 Outsider."""
    tf, os_, mn = SETUPS[n]
    return tf - outsiders, os_ + outsiders, mn


def setup_error(characters):
    """Why a list of characters is not a legal Bad Moon Rising setup, or None."""
    n = len(characters)
    if n not in SETUPS: return f'Bad Moon Rising is for {min(SETUPS)}-{max(SETUPS)} players'
    if len(set(characters)) != n: return 'characters must be distinct'
    bad = [c for c in characters if c not in BMR.all]
    if bad: return f'not on the script: {bad}'
    counts = {k: sum(1 for c in characters if kind(c) == k) for k in ('Townsfolk', 'Outsider', 'Minion', 'Demon')}
    if counts['Demon'] != 1: return 'need exactly one Demon'
    tf, os_, mn = team_sizes(n)
    if counts['Minion'] != mn: return f'need exactly {mn} Minion(s)'
    legal = [os_ - 1, os_ + 1] if 'Godfather' in characters else [os_]
    if counts['Outsider'] not in [x for x in legal if x >= 0]:
        return (f'need {" or ".join(str(x) for x in legal if x >= 0)} Outsiders'
                + (' (Godfather in play)' if 'Godfather' in characters else ''))
    return None


def random_setup(rng, minion=None, players=10, demon=None):
    """A random legal setup; `minion` and `demon` force a character (batches rotate them)."""
    tf, os_, mn = team_sizes(players)
    minions = ([minion] if minion else []) + rng.sample([m for m in MINIONS if m != minion], mn - (1 if minion else 0))
    if 'Godfather' in minions:
        os_ += rng.choice([d for d in (-1, 1) if os_ + d >= 0])
    tf = players - 1 - mn - os_
    return rng.sample(TOWNSFOLK, tf) + rng.sample(OUTSIDERS, os_) + minions + [demon or rng.choice(DEMONS)]


class BMRGrimoire(Grimoire):
    def __init__(self, names, characters):
        super().__init__(names, characters)
        self.tick = 1               # night n is tick 2n-1, day n is tick 2n
        self.effects = []           # drunkenness and poison: {target, source, kind, end}
        self.used = set()           # players who have spent a once-per-game ability
        self.fool_used = set()
        self.last = {}              # player -> (night, targets) of their last night choice
        self.da_protected = None    # the Devil's Advocate's choice: safe from execution tomorrow
        self.safe_tonight = set()   # the Innkeeper's two
        self.innkeeper = None
        self.pukka_poisoned = None  # who dies when the Pukka next acts
        self.moonchild_target = None
        self.grandchild = None
        self.died_today = False     # anyone died during the day (the Zombuul sleeps)
        self.outsider_died_today = False  # the Godfather wakes
        self.mastermind_day = None  # the extra day after the Demon was executed with a Mastermind alive
        self.woke = set()           # who woke tonight to use their own ability (Chambermaid)
        self.goon_hit = False       # the Goon has already been chosen tonight
        self.lunatic_minions, self.lunatic_bluffs = [], []

    # ---- drunk and poisoned ----------------------------------------------------------------
    def add_effect(self, target, source, kind_, end):
        """`source` is the player whose ability causes it (None when a player makes themself drunk: that
        lasts whatever becomes of them). `end` is the first tick at which it is over (None: until removed)."""
        self.effects.append({'target': target, 'source': None if source == target else source, 'kind': kind_, 'end': end})

    def dusk(self):
        """The tick at which 'until dusk' ends: the coming night."""
        return self.tick + (2 if self.tick % 2 else 1)

    def impaired_names(self):
        live = [e for e in self.effects if e['end'] is None or self.tick < e['end']]
        able = lambda e: e['source'] is None or self[e['source']].alive
        active = [e for e in live if able(e)]
        for _ in range(6):  # an effect lapses while its source is itself drunk or poisoned
            down = {e['target'] for e in active}
            nxt = [e for e in live if able(e) and e['source'] not in down]
            if nxt == active:
                return down
            active = nxt
        down = set()  # two players each making the other drunk: the earlier effect stands
        for e in live:
            if able(e) and e['source'] not in down:
                down.add(e['target'])
        return down

    def is_poisoned(self, p):
        """Drunk or poisoned: either way the player has no ability and is not told."""
        return p.name in self.impaired_names()

    def impaired(self, p):
        return self.is_poisoned(p)

    # ---- queries ---------------------------------------------------------------------------
    def demon(self):
        return next((p for p in self.players if p.alive and p.character in DEMONS), None)

    def protector(self, p, cause):
        """The ability that stops p dying now, or None. (The Fool, who is used up by it, comes last.)"""
        inn = self[self.innkeeper] if self.innkeeper else None
        if cause != 'execution' and p.name in self.safe_tonight and inn and self.works(inn, 'Innkeeper'):
            return 'Innkeeper'
        if self.works(p, 'Sailor'):
            return 'Sailor'
        for lady in self.players:
            if self.works(lady, 'Tea Lady') and lady.seems_alive:
                nb = self.neighbours(lady)
                if p in nb and len(nb) == 2 and not any(q.evil for q in nb):
                    return 'Tea Lady'
        if cause == 'execution':
            da = self.with_character("Devil's Advocate")
            if da and self.da_protected == p.name and self.works(da, "Devil's Advocate"):
                return "Devil's Advocate"
        return None

    def check_victory(self):
        if self.winner: return self.winner
        if self.mastermind_day:  # the Demon is dead; that day's execution decides (BMRGame.execute)
            mm = self.with_character('Mastermind')
            if mm and self.works(mm, 'Mastermind'):
                return None
        if not self.demon():
            self.winner, self.reason = 'good', 'The Demon is dead.'
        elif self.alive_count() <= 2:
            self.winner, self.reason = 'evil', 'Only two players remain alive.'
        return self.winner


# ---- Storyteller choices ---------------------------------------------------------------------

def lunatic_as_choice(demon):
    """The Demon the Lunatic believes they are: usually the one in play."""
    others = [d for d in DEMONS if d != demon]
    return Choice('lunatic_as', [{'character': d} for d in DEMONS],
                  lambda r: {'character': demon if r.random() < POLICY['lunatic_same_demon'] else r.choice(others)})


def bluffs_choice(options):
    """Three good characters not in play, shown to the Demon: at most one Outsider (the Godfather makes
    the Outsider count uncertain, so one evil Outsider claim fits)."""
    def style(r):
        tf = [c for c in options if c in TOWNSFOLK]
        os_ = [c for c in options if c in OUTSIDERS and c != 'Lunatic']
        picks = [r.choice(os_)] if os_ and r.random() < 0.5 else []
        if len(tf) < 3 - len(picks):
            return {'characters': r.sample(options, 3)}
        return {'characters': picks + r.sample(tf, 3 - len(picks))}
    return Choice('bluffs', [{'characters': list(c)} for c in combinations(options, 3)], style)


def lunatic_minions_choice(g, lunatic, k):
    """The players shown to the Lunatic as their Minions: any k players, mostly good ones."""
    others = [p for p in g.players if p is not lunatic]
    good = [p.name for p in others if not p.evil]
    fair = [p.name for p in others if p.character not in DEMONS]

    def style(r):
        picks = []
        while len(picks) < k:
            pool = [x for x in (good if r.random() < POLICY['lunatic_minion_good'] else fair) if x not in picks]
            picks.append(r.choice(pool or [x for x in fair if x not in picks]))
        return {'players': picks}
    return Choice('lunatic_minions', [{'players': list(c)} for c in combinations([p.name for p in others], k)], style)


def lunatic_bluffs_choice(lunatic):
    """Three good characters shown to the Lunatic as bluffs (they may be in play)."""
    return Choice('lunatic_bluffs', [{'characters': list(c)} for c in combinations(BMR.good, 3)],
                  lambda r: {'characters': r.sample([c for c in BMR.good if c != 'Lunatic'], 3)})


def grandmother_choice(g, p):
    """A good player and their character; anything when the Grandmother is drunk or poisoned."""
    good = [q for q in g.players if q is not p and not q.evil]
    if g.impaired(p):
        values = [{'players': [q.name], 'character': c} for q in g.players if q is not p for c in BMR.good]
    else:
        values = [{'players': [q.name], 'character': q.character} for q in good]

    def style(r):
        if g.impaired(p) and r.random() < POLICY['impaired_false']:
            q = r.choice([q for q in g.players if q is not p])
            return {'players': [q.name], 'character': r.choice([c for c in TOWNSFOLK if c not in (q.character, p.shown)])}
        tf = [q for q in good if q.character in TOWNSFOLK]
        q = r.choice(tf if tf and r.random() < POLICY['grandchild_townsfolk'] else good)
        return {'players': [q.name], 'character': q.character}
    return Choice(f'Grandmother:{p.name}', values, style)


def godfather_choice(g, p):
    """Which Outsiders are in play; any set when the Godfather is drunk or poisoned."""
    true = sorted(q.character for q in g.players if q.character in OUTSIDERS)
    if not g.impaired(p):
        return Choice(f'Godfather:{p.name}', [{'characters': true}], lambda r: {'characters': true})
    values = [{'characters': list(c)} for k in range(len(OUTSIDERS) + 1) for c in combinations(OUTSIDERS, k)]

    def style(r):
        if r.random() < POLICY['impaired_false']:
            return {'characters': r.sample(OUTSIDERS, len(true))}
        return {'characters': true}
    return Choice(f'Godfather:{p.name}', values, style)


def drunk_one_choice(g, p, pair, self_chance=None):
    """Who is drunk: one of `pair` (the Sailor and their choice, or the Innkeeper's two)."""
    a, b = pair

    def style(r):
        if self_chance is not None:  # the Sailor (a) and the player they chose (b)
            return {'players': [a if r.random() < self_chance else b]}
        evil = [x for x in pair if g[x].evil]
        if len(evil) == 1 and r.random() < POLICY['innkeeper_drunk_evil']:
            return {'players': evil}
        return {'players': [r.choice(pair)]}
    return Choice(f'{p.character}:{p.name}', [{'players': [a]}, {'players': [b]}], style)


def chambermaid_choice(g, p, targets):
    true = sum(1 for t in targets if t in g.woke)
    if not g.impaired(p):
        return Choice(f'Chambermaid:{p.name}', [{'number': true}], lambda r: {'number': true})
    numbers = list(range(len(targets) + 1))

    def style(r):
        false = [x for x in numbers if x != true]
        return {'number': r.choice(false) if false and r.random() < POLICY['impaired_false'] else true}
    return Choice(f'Chambermaid:{p.name}', [{'number': x} for x in numbers], style)


def regurgitate_choice(dead):
    """Whether the Shabaloth brings back one of the dead players it chose last night."""
    values = [{'players': []}] + [{'players': [x]} for x in dead]
    return Choice('Shabaloth:regurgitate', values,
                  lambda r: {'players': [r.choice(dead)] if r.random() < POLICY['regurgitate'] else []})


# ---- the game ----------------------------------------------------------------------------------

def _names(xs):
    xs = list(xs)
    return xs[0] if len(xs) == 1 else ', '.join(xs[:-1]) + ' and ' + xs[-1]


# The rounds of night questions, in the official order. Within a round the answers are resolved in
# this order; a later round's players are only asked if they are still alive (and, for the Demon,
# not exorcised).
EARLY = ['Sailor', 'Innkeeper', 'Courtier', 'Gambler', "Devil's Advocate", 'Exorcist']
LATE = ['Assassin', 'Godfather', 'Professor']


class BMRGame(Game):
    SCRIPT = 'bmr'

    def __init__(self, *args, demon=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.forced_demon = demon
        self.claims = []  # players whose death the town has just learned of (the Moonchild's choice)

    def note(self, text):
        self.emit('st_note', {'text': f'[storyteller] {text}'}, 'audit')

    # ---- setup -------------------------------------------------------------------------------
    async def setup(self):
        names, seating = self.names, ', '.join(self.names)
        if self.forced:
            chars = list(self.forced)
        else:
            chars = random_setup(self.rng, self.minion, len(names), self.forced_demon)
            self.rng.shuffle(chars)
        err = setup_error(chars)
        if err:
            raise ValueError(err)
        self.g = g = BMRGrimoire(names, chars)
        demon, lunatic = g.demon(), g.with_character('Lunatic')
        minions = [p.name for p in g.players if p.character in MINIONS]
        if lunatic:
            lunatic.shown = self.decide(lunatic_as_choice(demon.character))['character']
        g.bluffs = self.decide(bluffs_choice([c for c in BMR.good if c not in chars]))['characters']
        if lunatic:
            g.lunatic_minions = self.decide(lunatic_minions_choice(g, lunatic, len(minions)))['players']
            g.lunatic_bluffs = self.decide(lunatic_bluffs_choice(lunatic))['characters']
        self.starting = {p.name: p.character for p in g.players}
        if self.seat_factory:
            self.seats = {p.name: self.seat_factory(p.name, 'evil' if p.evil else 'good') for p in g.players}
        self.emit('setup', {'seats': [{'name': p.name, 'character': p.character, 'shown': p.shown} for p in g.players],
                            'red_herring': None, 'bluffs': g.bluffs, 'script': 'bmr',
                            'lunatic': {'minions': g.lunatic_minions, 'bluffs': g.lunatic_bluffs} if lunatic else None},
                  'audit')
        if lunatic:
            self.note(f'{lunatic.name} (Lunatic) is shown false Minions {_names(g.lunatic_minions)} and bluffs '
                      f'{", ".join(g.lunatic_bluffs)}.')

        def demon_info(mins, bluffs):
            return (f'Your Minion{"" if len(mins) == 1 else "s"}: {", ".join(mins)} (you do not know which Minion '
                    f'characters). Three good characters not in play, for evil to bluff: {", ".join(bluffs)}.')

        for p in g.players:
            left, right = names[(p.seat - 1) % len(names)], names[(p.seat + 1) % len(names)]
            lines = [f'You are {p.name}. The players, clockwise: {seating} (and back to {names[0]}). '
                     f'You sit between {left} and {right}.',
                     f'Your character: {card(p.shown)}']
            if p is demon:
                lines.append(demon_info(minions, g.bluffs))
                if lunatic:
                    lines.append(f'The Lunatic is {lunatic.name}: they believe they are the Demon. Each night you '
                                 'will be told whom they chose.')
            elif p is lunatic:
                lines.append(demon_info(g.lunatic_minions, g.lunatic_bluffs))
            elif p.character in MINIONS:
                others = [m for m in minions if m != p.name]
                lines.append(f'The Demon is {demon.name}.'
                             + (f' Your fellow Minion{"" if len(others) == 1 else "s"}: {", ".join(others)} (you do not '
                                'know which Minion characters).' if others else ''))
            self.emit('intro', {'text': '\n'.join(lines)}, [p.name])

    # ---- death -------------------------------------------------------------------------------
    def kill(self, p, cause, force=False):
        """p would die. Returns True if the town will see them dead (the Zombuul's first death included).
        `force` is the Assassin: nothing protects."""
        g = self.g
        if not p.alive:
            return False
        if not force:
            saved = g.protector(p, cause)
            if not saved and cause == 'execution' and not p.evil:
                pacifist = g.with_character('Pacifist')
                if pacifist and g.works(pacifist, 'Pacifist') and self.decide(
                        yes_choice(f'Pacifist:{p.name}', POLICY['pacifist_saves']))['yes']:
                    saved = 'Pacifist'
            if not saved and g.works(p, 'Fool') and p.name not in g.fool_used:
                g.fool_used.add(p.name)
                saved = 'Fool'
            if saved:
                self.note(f'{p.name} does not die ({cause}): {saved}.')
                return False
        day = self.phase != 'night'
        if day:
            g.died_today = True
        if p.character == 'Zombuul' and not p.looks_dead and not g.is_poisoned(p):
            p.looks_dead = True
            self.emit('death', {'player': p.name, 'cause': f'{cause}; the Zombuul lives on, registering as dead'}, 'audit')
            self.emit('notice', {'text': 'You have died for the first time: as the Zombuul you are still alive, but '
                                         'you register as dead. The town will see you as dead (you have one ghost '
                                         'vote and cannot nominate), and you still kill at night. If you die again, '
                                         'you die for real.'}, [p.name])
            return True
        seen = p.seems_alive
        g.die(p)
        self.emit('death', {'player': p.name, 'cause': cause}, 'audit')
        if day and p.character in OUTSIDERS:
            g.outsider_died_today = True
        if cause == 'execution' and p.character in MINIONS:
            minstrel = g.with_character('Minstrel')
            if minstrel and g.works(minstrel, 'Minstrel'):
                for q in g.players:
                    if q is not minstrel:
                        g.add_effect(q.name, minstrel.name, 'drunk', g.tick + 3)  # until dusk tomorrow
                self.note(f'A Minion was executed: the Minstrel ({minstrel.name}) makes everyone else drunk until '
                          'dusk tomorrow.')
        if cause == 'execution' and p.character in DEMONS:
            mm = g.with_character('Mastermind')
            if mm and g.works(mm, 'Mastermind'):
                g.mastermind_day = self.day + 1
                self.note(f'The Demon was executed, but the Mastermind ({mm.name}) lives: one more day.')
        if cause == 'demon' and p.name == g.grandchild:
            gm = g.with_character('Grandmother')
            if gm and g.works(gm, 'Grandmother'):
                self.kill(gm, 'grandmother')
        return seen

    def resurrect(self, p, by):
        p.alive = True
        self.g.used.discard(p.name)       # a resurrected player has their ability again, once-per-game ones too
        self.g.fool_used.discard(p.name)
        self.emit('becomes', {'player': p.name, 'character': f'{p.character}, alive again ({by})'}, 'audit')

    def execute(self, name):
        g, p = self.g, self.g[name]
        self.executed_today = True
        seemed = p.seems_alive
        died = self.kill(p, 'execution') if p.alive else False
        self.emit('execution', {'player': name, 'died': seemed and died, 'survived': seemed and not died})
        if seemed and died:
            self.claims.append(name)
        if g.mastermind_day == self.day and not g.winner:
            loser = 'evil' if p.evil else 'good'
            g.winner = 'good' if loser == 'evil' else 'evil'
            g.reason = (f'The Demon had already been executed with the Mastermind alive; {name}, '
                        f'{"an evil" if loser == "evil" else "a good"} player, was executed on the extra day.')
        g.check_victory()

    async def death_claims(self, names):
        """Everyone whose death was just announced may publicly make the Moonchild's choice; it only does
        anything for the real Moonchild (who must not be drunk or poisoned)."""
        g = self.g
        options = [p.name for p in g.seeming_alive()]
        names = [n for n in names if not g[n].seems_alive]
        if not names or not options or g.winner:
            return
        prompt = ('The town has just learned of your death. If you are the Moonchild (or want the town to think '
                  'so), you may now publicly choose one living player: put their name in `targets`. Otherwise '
                  'leave `targets` empty. Nothing else you write here is heard.')
        requests = {n: Request('death', prompt, self.day, n_targets=1, options=options, alive=False, optional=True)
                    for n in names}
        acts = await self.ask_many(requests)
        for n in names:
            chosen = self.targets(n, acts[n], requests[n])
            if not chosen:
                continue
            self.emit('moonchild', {'player': n, 'target': chosen[0]})
            p = g[n]
            if p.character == 'Moonchild' and not p.alive and not g.is_poisoned(p):
                g.moonchild_target = chosen[0]

    # ---- night -------------------------------------------------------------------------------
    def night_request(self, p, n):
        """The question p's (apparent) character is woken for tonight, or None."""
        g, names, role, first = self.g, self.names, p.shown, n == 1
        alive = [q.name for q in g.seeming_alive()]
        last_night = g.last.get(p.name, (-1, []))
        prev = last_night[1] if last_night[0] == n - 1 else []
        k, optional, options, characters = 1, False, names, []
        if role == 'Sailor':
            text, options = 'Choose a living player: either you or they will be drunk until dusk.', alive
        elif role == 'Innkeeper' and not first:
            k, text = 2, "Choose two players: they can't die tonight, but one of them will be drunk until dusk."
        elif role == 'Courtier' and p.name not in g.used:
            k, optional, options, characters = 0, True, [], BMR.all
            text = ('Once per game you may choose a character: if it is in play, that player is drunk for three '
                    'nights and three days starting now. Put the character in `character`, or leave it null to wait.')
        elif role == 'Gambler' and not first:
            characters = BMR.all
            text = ('Choose a player (`targets`) and guess their character (`character`): if your guess is wrong, '
                    'you die.')
        elif role == "Devil's Advocate":
            options = [x for x in alive if x not in prev]
            text = "Choose a living player (not last night's): if they are executed tomorrow, they don't die."
        elif role == 'Exorcist' and not first:
            options = [x for x in names if x not in prev]
            text = "Choose a player (not last night's): if they are the Demon, they do not wake tonight."
        elif role == 'Zombuul' and not first and not g.died_today:
            text = 'Nobody died today, so choose a player to kill.'
        elif role == 'Pukka':
            text = ('Choose a player to poison. They die when you next choose (tomorrow night), and are poisoned '
                    'until then.')
        elif role == 'Shabaloth' and not first:
            k, text = 2, 'Choose two players to kill.'
        elif role == 'Po' and not first:
            if p.name in g.last and not g.last[p.name][1]:
                k, text = min(3, len(names)), 'Your last choice was no-one, so choose three players to kill.'
            else:
                optional, text = True, ('You may choose a player to kill, or choose no-one (leave `targets` empty) '
                                        'so that you choose three tomorrow night.')
        elif role == 'Assassin' and not first and p.name not in g.used:
            optional, text = True, ('Once per game you may choose a player: they die, even if something would '
                                    'protect them. Leave `targets` empty to wait.')
        elif role == 'Godfather' and not first and g.outsider_died_today:
            text = 'An Outsider died today. Choose a player: they die.'
        elif role == 'Professor' and not first and p.name not in g.used:
            options = [q.name for q in g.players if not q.seems_alive]
            if not options:
                return None
            optional, text = True, ('Once per game you may choose a dead player: if they are a Townsfolk, they come '
                                    'back to life. Leave `targets` empty to wait.')
        elif role == 'Chambermaid':
            options = [x for x in alive if x != p.name]
            k = min(2, len(options))
            text = ('Choose two living players (not yourself): you learn how many of them woke tonight because of '
                    'their own ability.')
            if not k:
                return None
        else:
            return None
        tail = '' if role == 'Courtier' else ' Put your choice in `targets`.'
        return Request('night', f'Night {n} — {role}: {text}{tail}', n, n_targets=k, options=options,
                       optional=optional, characters=characters)

    async def wake(self, players, n):
        """Ask these players their night question, at once. Returns {name: (targets, character)} for those
        who were woken."""
        g = self.g
        requests = {}
        for p in players:
            req = self.night_request(p, n) if p.alive else None
            if req:
                requests[p.name] = req
        acts = await self.ask_many(requests)
        out = {}
        for name, req in requests.items():
            g.woke.add(name)
            targets = self.targets(name, acts[name], req)
            character = acts[name].get('character') if acts[name].get('character') in req.characters else None
            if req.characters and not req.optional and character is None:
                character = self.rng.choice(req.characters)
                self.emit('notice', {'text': f'(You named no character, so the Storyteller chose for you: {character}.)'},
                          [name])
            out[name] = (targets, character)
            self.emit('night_choice', {'player': name, 'role': g[name].shown,
                                       'targets': targets + ([character] if character else [])}, 'audit')
        return out

    def touch(self, p, targets):
        """p chose these players with their ability: the first to choose a (sober, living) Goon tonight
        becomes drunk until dusk, and the Goon takes their alignment."""
        g = self.g
        for t in targets:
            goon = g[t]
            if goon.character != 'Goon' or goon is p or g.goon_hit or not g.works(goon, 'Goon'):
                continue
            g.goon_hit = True
            g.add_effect(p.name, goon.name, 'drunk', g.dusk())
            team = 'evil' if p.evil else 'good'
            self.note(f'{p.name} chose the Goon ({goon.name}) and is drunk until dusk; the Goon is {team}.')
            if goon.evil != p.evil:
                goon.team = team
                self.emit('becomes', {'player': goon.name, 'character': f'Goon, now {team}'}, 'audit')
                self.emit('notice', {'text': f'Night {self.day} — Goon: a player chose you with their ability. You are now '
                                             f'{team.upper()}: you win if the {team} team wins.'
                                             + (' (You are not told who the evil players are.)' if team == 'evil' else '')},
                          [goon.name])

    def act(self, p, role, targets, character, n):
        """Resolve one night choice. (Whether it worked is never told to the player.)"""
        g = self.g
        if p.character == 'Lunatic':  # the Lunatic's attack is not an ability: it does nothing
            g.last[p.name] = (n, targets)
            return
        works_now = g.works(p, role)  # the Assassin's kill goes through even on the Goon
        self.touch(p, targets)
        works = g.works(p, role)
        if role in ("Devil's Advocate", 'Exorcist', 'Po', 'Shabaloth'):
            g.last[p.name] = (n, targets)
        if role == 'Courtier':
            if not character:
                return
            g.used.add(p.name)
            target = next((q for q in g.players if q.character == character), None)
            if works and target:
                g.add_effect(target.name, p.name, 'drunk', g.tick + 6)  # three nights and three days
                self.note(f'The Courtier makes {target.name} ({character}) drunk for three nights and days.')
            return
        if role in ('Assassin', 'Professor') and targets:
            g.used.add(p.name)
        if role == 'Assassin' and targets and works_now:
            self.kill(g[targets[0]], 'assassin', force=True)
        if not works or not targets:
            return
        if role == 'Sailor':
            t = targets[0]
            chance = POLICY['sailor_drunk_if_evil' if g[t].evil else 'sailor_drunk_if_good']
            drunk = p.name if t == p.name else self.decide(drunk_one_choice(g, p, [p.name, t], chance))['players'][0]
            g.add_effect(drunk, p.name, 'drunk', g.dusk())
        elif role == 'Innkeeper':
            g.safe_tonight, g.innkeeper = set(targets), p.name
            drunk = self.decide(drunk_one_choice(g, p, targets))['players'][0]
            g.add_effect(drunk, p.name, 'drunk', g.dusk())
        elif role == 'Gambler':
            if g[targets[0]].character != character:
                self.kill(p, 'gambler')
        elif role == "Devil's Advocate":
            g.da_protected = targets[0]
        elif role == 'Godfather':
            self.kill(g[targets[0]], 'godfather')
        elif role == 'Professor':
            t = g[targets[0]]
            if not t.alive and t.character in TOWNSFOLK:
                self.resurrect(t, 'Professor')
        elif role in ('Zombuul', 'Shabaloth', 'Po'):
            for t in targets:
                self.kill(g[t], 'demon')
        elif role == 'Pukka':
            self.pukka_death()
            g.add_effect(targets[0], p.name, 'poisoned', None)
            g.pukka_poisoned = targets[0]

    def pukka_death(self):
        """The player the Pukka poisoned last dies, then becomes healthy."""
        g = self.g
        if g.pukka_poisoned:
            self.kill(g[g.pukka_poisoned], 'demon')
            g.effects = [e for e in g.effects if e['kind'] != 'poisoned']
            g.pukka_poisoned = None

    async def night(self, n):
        g, first = self.g, n == 1
        self.day, self.phase = n, 'night'
        g.tick = 2 * n - 1
        g.effects = [e for e in g.effects if e['end'] is None or g.tick < e['end']]
        g.safe_tonight, g.innkeeper, g.da_protected = set(), None, None
        g.woke, g.goon_hit = set(), False
        self.emit('header', {'text': f'Night {n}'})
        seemed = {p.name: p.seems_alive for p in g.players}
        demon, lunatic = g.demon(), g.with_character('Lunatic')

        def resolve(answers, order):
            for role in order:
                for p in g.players:
                    if p.shown == role and p.name in answers and (p.alive or role in DEMONS):
                        self.act(p, role, *answers[p.name], n)

        # 1. everyone before the Demon, and the Lunatic (the Demon is told the Lunatic's choice)
        early = [p for p in g.living() if p.shown in EARLY or p is lunatic]
        if first:  # nobody can stop the Demon waking on the first night: one round
            early.append(demon)
        answers = await self.wake(early, n)
        resolve(answers, EARLY)
        if lunatic and lunatic.name in answers:
            self.act(lunatic, lunatic.shown, *answers[lunatic.name], n)

        # 2. the Demon, unless a working Exorcist chose them
        demon = g.demon()
        exorcist = g.with_character('Exorcist')
        exorcised = bool(demon and exorcist and exorcist.name in answers and g.works(exorcist, 'Exorcist')
                         and answers[exorcist.name][0] == [demon.name])
        if demon and exorcised:
            self.note(f'The Exorcist ({exorcist.name}) chose the Demon: {demon.name} does not wake.')
            self.emit('notice', {'text': f'Night {n}: the Exorcist chose you, so you do not act tonight. The Exorcist '
                                         f'is {exorcist.name}.'}, [demon.name])
            if demon.character == 'Pukka' and g.works(demon, 'Pukka'):
                self.pukka_death()
        elif demon:
            if lunatic and lunatic.name in answers:
                chose = answers[lunatic.name][0]
                self.emit('info', {'text': f'Night {n}: the Lunatic ({lunatic.name}) chose '
                                           f'{_names(chose) if chose else "no-one"}.'}, [demon.name])
            if demon.character == 'Shabaloth' and g.works(demon, 'Shabaloth') and g.last.get(demon.name, (-1, []))[0] == n - 1:
                dead = [x for x in g.last[demon.name][1] if not g[x].alive]
                back = self.decide(regurgitate_choice(dead))['players'] if dead else []
                for x in back:
                    self.resurrect(g[x], 'regurgitated by the Shabaloth')
            if not first:
                answers.update(await self.wake([demon], n))
            resolve(answers, [demon.character])

        # 3. the Assassin, the Godfather and the Professor
        if not first:
            late = await self.wake([p for p in g.living() if p.shown in LATE], n)
            resolve(late, LATE)

        # 4. the Storyteller's deaths, then information
        tinker = g.with_character('Tinker')
        if tinker and g.works(tinker, 'Tinker') and self.decide(
                yes_choice(f'Tinker:{tinker.name}', POLICY['tinker_dies']))['yes']:
            self.kill(tinker, 'tinker')
        if g.moonchild_target:
            t = g[g.moonchild_target]
            if not t.evil:
                self.kill(t, 'moonchild')
            g.moonchild_target = None
        if first:
            for p in g.living():
                if p.shown == 'Grandmother':
                    v = self.decide(grandmother_choice(g, p))
                    if g.works(p, 'Grandmother'):
                        g.grandchild = v['players'][0]
                    g.woke.add(p.name)
                    self.emit('info', {'text': f'Night {n} — Grandmother: your grandchild is {v["players"][0]}, who is the '
                                               f'{v["character"]}.'}, [p.name])
                elif p.shown == 'Godfather':
                    v = self.decide(godfather_choice(g, p))['characters']
                    g.woke.add(p.name)
                    self.emit('info', {'text': f'Night {n} — Godfather: the Outsiders in play are: '
                                               f'{", ".join(v) if v else "none"}.'}, [p.name])
        maids = await self.wake([p for p in g.living() if p.shown == 'Chambermaid'], n)
        for name, (targets, _) in maids.items():
            p = g[name]
            self.touch(p, targets)
            v = self.decide(chambermaid_choice(g, p, targets))['number']
            self.emit('info', {'text': f'Night {n} — Chambermaid: of {_names(targets)}, {v} woke tonight because of '
                                       'their own ability.'}, [name])

        deaths = [p.name for p in g.players if seemed[p.name] and not p.seems_alive]
        risen = [p.name for p in g.players if not seemed[p.name] and p.seems_alive]
        self.phase = 'day'
        g.tick = 2 * n
        g.died_today = g.outsider_died_today = False
        self.emit('header', {'text': f'Day {n}'})
        self.emit('dawn', {'day': n, 'deaths': deaths, 'risen': risen,
                           'narration': dawn_narration(self.rng, deaths)})
        if not g.check_victory():
            await self.death_claims(deaths)
        if first:
            self.probe('dawn')

    # ---- day ---------------------------------------------------------------------------------
    async def daytime(self, n):
        g = self.g
        self.claims = []
        await super().daytime(n)
        if g.winner:
            return
        if g.mastermind_day == n:  # nobody was executed on the Mastermind's extra day
            g.winner, g.reason = 'good', 'The Demon had already been executed, and nobody was executed on the extra day.'
            return
        await self.death_claims(self.claims)
