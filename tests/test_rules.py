import asyncio
import random
import unittest

from clocktower.agents import RandomSeat, ScriptedStoryteller
from clocktower.game import NAMES, Game
from clocktower.llm import Reply
from clocktower.state import POLICY, Grimoire, chef_choice, info_text, pair_choice, setup_error

A, B, C, D, E, F, G, H, I = NAMES
BLANK = {'say': '', 'whispers': [], 'nominate': None, 'vote': None, 'targets': [], 'slayer_shot': None}


class Seat:
    """Follows a policy(name, request) -> partial action; everything else passes."""

    def __init__(self, name, policy, log):
        self.name, self.policy, self.log = name, policy, log

    async def act(self, text, request):
        self.log.append((self.name, request.kind, text))
        return Reply({**BLANK, **(self.policy(self.name, request) or {})})


class Storyteller:
    def __init__(self, decisions=None):
        self.decisions = decisions or {}
        self.rng = random.Random(0)

    def choose(self, choice):
        return {**choice.options(self.rng), **self.decisions.get(choice.id, {})}


class policy:
    """Temporarily override POLICY numbers."""

    def __init__(self, **kw):
        self.kw, self.old = kw, {}

    def __enter__(self):
        self.old = {k: POLICY[k] for k in self.kw}
        POLICY.update(self.kw)

    def __exit__(self, *exc):
        POLICY.update(self.old)


def game(characters, policy=lambda n, r: None, decisions=None, **kw):
    log = []
    g = Game({n: Seat(n, policy, log) for n in NAMES}, Storyteller(decisions), characters=characters, seed=7, **kw)
    g.texts = log
    return g


def run(coro):
    return asyncio.run(coro)


def night_targets(choices):
    """Policy that answers night prompts from a {name: [targets]} dict."""
    return lambda name, req: {'targets': choices[name]} if req.kind == 'night' and name in choices else None


BASE = ['Imp', 'Poisoner', 'Monk', 'Empath', 'Chef', 'Washerwoman', 'Soldier', 'Butler', 'Saint']


class SetupTests(unittest.TestCase):
    def test_setup_legality(self):
        self.assertIsNone(setup_error(BASE))
        self.assertIn('Outsiders', setup_error(['Imp', 'Baron', 'Monk', 'Empath', 'Chef', 'Washerwoman', 'Soldier', 'Butler', 'Saint']))
        self.assertIsNone(setup_error(['Imp', 'Baron', 'Monk', 'Empath', 'Chef', 'Drunk', 'Recluse', 'Butler', 'Saint']))
        self.assertIn('one Imp', setup_error(['Poisoner', 'Spy', 'Monk', 'Empath', 'Chef', 'Washerwoman', 'Soldier', 'Butler', 'Saint']))

    def test_evil_learns_each_other_and_bluffs(self):
        g = game(BASE)
        run(g.setup())
        imp_intro = next(t for t in g.buf[A] if 'Your Minion' in t)
        self.assertIn(B, imp_intro)
        self.assertEqual(len(g.g.bluffs), 3)
        self.assertTrue(all(b not in BASE for b in g.g.bluffs))
        self.assertTrue(any(f'The Demon is {A}' in t for t in g.buf[B]))
        self.assertFalse(any('Your Minion' in t for t in g.buf[C]))


def play_nights(characters, choices_by_night, decisions=None):
    g = game(characters, decisions=decisions)
    run(g.setup())
    for n, choices in enumerate(choices_by_night, start=1):
        g.seats = {x: Seat(x, night_targets(choices), g.texts) for x in NAMES}
        run(g.night(n))
    return g


class NightTests(unittest.TestCase):
    def play_nights(self, *a, **kw):
        return play_nights(*a, **kw)

    def test_monk_protects_unless_poisoned(self):
        g = self.play_nights(BASE, [{B: [E]}, {A: [D], C: [D], B: [E]}])
        self.assertTrue(g.g[D].alive)
        g = self.play_nights(BASE, [{B: [E]}, {A: [D], C: [D], B: [C]}])
        self.assertFalse(g.g[D].alive)

    def test_soldier_is_safe(self):
        g = self.play_nights(BASE, [{B: [E]}, {A: [G], B: [E]}])
        self.assertTrue(g.g[G].alive)

    def test_starpass_makes_the_minion_the_imp(self):
        g = self.play_nights(BASE, [{B: [E]}, {A: [A], B: [E]}])
        self.assertFalse(g.g[A].alive)
        self.assertEqual(g.g[B].character, 'Imp')
        self.assertIsNone(g.g.check_victory())
        self.assertTrue(any('you are now the Imp' in t for t in g.buf[B]))

    def test_poisoned_empath_is_asked_of_the_storyteller(self):
        g = self.play_nights(BASE, [{B: [D]}], decisions={f'Empath:{D}': {'number': 2}})
        self.assertTrue(any('2 of your living neighbours are evil' in t for t in g.buf[D]))

    def test_sober_empath_is_automatic_and_true(self):
        g = self.play_nights(BASE, [{B: [E]}], decisions={f'Empath:{D}': {'number': 2}})
        self.assertTrue(any('0 of your living neighbours are evil' in t for t in g.buf[D]))

    def test_mayor_bounce(self):
        chars = ['Imp', 'Poisoner', 'Mayor', 'Empath', 'Chef', 'Washerwoman', 'Soldier', 'Butler', 'Saint']
        g = self.play_nights(chars, [{B: [E]}, {A: [C], B: [E]}], decisions={f'Mayor:{C}': {'players': [F]}})
        self.assertTrue(g.g[C].alive)
        self.assertFalse(g.g[F].alive)

    def test_ravenkeeper_learns_a_character(self):
        chars = ['Imp', 'Poisoner', 'Ravenkeeper', 'Empath', 'Chef', 'Washerwoman', 'Soldier', 'Butler', 'Saint']
        g = game(chars)
        run(g.setup())
        run(g.night(1))
        picks = {A: [C], B: [E], C: [A], H: [D]}
        g.seats = {x: Seat(x, lambda n, r: {'targets': picks[n]}, g.texts) for x in NAMES}
        run(g.night(2))
        self.assertTrue(any(f'{A} is the Imp' in t for t in g.buf[C]))


class DayTests(unittest.TestCase):
    def prepared(self, characters, policy, decisions=None):
        g = game(characters, policy=policy, decisions=decisions)
        run(g.setup())
        g.day = 1
        return g

    def nominate(self, nominator, nominee, yes=()):
        def policy(name, req):
            if req.kind == 'nominate' and name == nominator:
                return {'nominate': nominee, 'say': 'I think so.'}
            if req.kind == 'vote':
                return {'vote': name in yes}
        return policy

    def test_execution_needs_half_the_living(self):
        g = self.prepared(BASE, self.nominate(C, D, yes=[A, B, C, E]))
        run(g.nominations())
        self.assertTrue(g.g[D].alive)
        g = self.prepared(BASE, self.nominate(C, D, yes=[A, B, C, E, F]))
        run(g.nominations())
        self.assertFalse(g.g[D].alive)

    def test_saint_execution_loses_for_good(self):
        g = self.prepared(BASE, self.nominate(C, I, yes=NAMES))
        run(g.nominations())
        self.assertEqual(g.g.winner, 'evil')

    def test_executing_the_imp_wins_for_good_or_passes_to_the_scarlet_woman(self):
        g = self.prepared(BASE, self.nominate(C, A, yes=NAMES))
        run(g.nominations())
        self.assertEqual(g.g.winner, 'good')
        sw = ['Imp', 'Scarlet Woman'] + BASE[2:]
        g = self.prepared(sw, self.nominate(C, A, yes=NAMES))
        run(g.nominations())
        self.assertIsNone(g.g.winner)
        self.assertEqual(g.g[B].character, 'Imp')

    def test_scarlet_woman_needs_five_alive(self):
        sw = ['Imp', 'Scarlet Woman'] + BASE[2:]
        g = self.prepared(sw, self.nominate(C, A, yes=NAMES))
        for x in (F, G, H, I, E):
            g.g.die(g.g[x])
        run(g.nominations())
        self.assertEqual(g.g.winner, 'good')

    def test_virgin_executes_a_townsfolk_nominator(self):
        chars = ['Imp', 'Poisoner', 'Virgin', 'Empath', 'Chef', 'Washerwoman', 'Soldier', 'Butler', 'Saint']
        g = self.prepared(chars, self.nominate(D, C))
        run(g.nominations())
        self.assertFalse(g.g[D].alive)
        g = self.prepared(chars, self.nominate(H, C))  # the Butler is not a Townsfolk
        run(g.nominations())
        self.assertTrue(g.g[H].alive)
        self.assertTrue(g.g.virgin_used)

    def test_slayer(self):
        chars = ['Imp', 'Poisoner', 'Slayer', 'Empath', 'Chef', 'Washerwoman', 'Soldier', 'Butler', 'Recluse']
        g = self.prepared(chars, lambda n, r: {'slayer_shot': A} if n == D else None)  # fake Slayer
        run(g.beat(1, 1, private=False))
        self.assertTrue(g.g[A].alive)
        g = self.prepared(chars, lambda n, r: {'slayer_shot': A} if n == C else None)
        run(g.beat(1, 1, private=True))  # no shots in private time
        self.assertIsNone(g.g.winner)
        run(g.beat(1, 1, private=False))
        self.assertEqual(g.g.winner, 'good')
        g = self.prepared(chars, lambda n, r: {'slayer_shot': I} if n == C else None, decisions={f'Slayer:{I}': {'yes': True}})
        run(g.beat(1, 1, private=False))
        self.assertFalse(g.g[I].alive)
        self.assertIsNone(g.g.winner)

    def test_butler_vote_needs_master(self):
        g = self.prepared(BASE, self.nominate(C, D, yes=[A, B, C, E, H]))
        g.g.master = F  # votes before the Butler (H), and votes no
        run(g.nominations())
        self.assertTrue(g.g[D].alive)
        vote = next(e for e in g.events if e['kind'] == 'vote' and e['data']['voter'] == H)
        self.assertFalse(vote['data']['yes'])  # shown as a no: nothing public reveals the Butler
        g = self.prepared(BASE, self.nominate(C, D, yes=[A, B, C, E, H]))
        g.g.master = I  # votes after the Butler, and votes no: their hand is down, so the Butler cannot vote yes
        run(g.nominations())
        vote = next(e for e in g.events if e['kind'] == 'vote' and e['data']['voter'] == H)
        self.assertFalse(vote['data']['yes'])
        result = next(e for e in g.events if e['kind'] == 'vote_result')
        self.assertEqual(result['data']['votes'], 4)  # the public roll and the count always agree
        g = self.prepared(BASE, self.nominate(C, D, yes=[A, B, C, E, H, I]))
        g.g.master = I  # votes after the Butler, and votes yes: asked first, so the Butler sees their hand up
        run(g.nominations())
        votes = [e['data']['voter'] for e in g.events if e['kind'] == 'vote']
        self.assertEqual(votes, g.vote_order(D))  # still shown in seat order
        vote = next(e for e in g.events if e['kind'] == 'vote' and e['data']['voter'] == H)
        self.assertTrue(vote['data']['yes'])
        g = self.prepared(BASE, self.nominate(C, D, yes=[A, B, C, E, F, H]))
        g.g.master = F  # votes before the Butler, and votes yes: the Butler may vote
        run(g.nominations())
        vote = next(e for e in g.events if e['kind'] == 'vote' and e['data']['voter'] == H)
        self.assertTrue(vote['data']['yes'])

    def test_whispers_are_private_and_speech_waits_for_the_town_square(self):
        def policy(name, req):
            if req.kind == 'beat':
                return {'say': 'hello town', 'whispers': [{'to': [B], 'text': 'psst'}] if name == A else []}
        g = self.prepared(BASE, policy)
        run(g.beat(1, 1, private=True))
        self.assertFalse(any(e['kind'] == 'say' for e in g.events))
        w = next(e for e in g.events if e['kind'] == 'whisper')
        self.assertEqual(w['to'], [A, B])
        self.assertEqual(sum('psst' in x for x in g.buf[C]), 0)
        run(g.beat(1, 1, private=False))
        self.assertEqual(sum(e['kind'] == 'say' for e in g.events), 9)
        self.assertEqual(sum(e['kind'] == 'whisper' for e in g.events), 1)

    def test_nobody_else_learns_that_a_whisper_happened(self):
        def policy(name, req):
            if req.kind == 'beat':
                return {'whispers': [{'to': [B], 'text': 'psst'}] if name == A else []}
        g = self.prepared(BASE, policy)
        run(g.beat(1, 1, private=True))
        self.assertFalse(any(A in x and B in x for x in g.buf[C]))

    def test_private_turn_counts_whispers_left(self):
        prompts = {}
        def policy(name, req):
            prompts[name] = req.prompt
            return BLANK
        g = self.prepared(BASE, policy)
        g.private_beats = 6
        run(g.beat(1, 2, private=True))
        self.assertIn('private time 2 of 6 — your turn (4 whispers left today after this one).', prompts[A])

    def test_system_prompt_states_the_beats(self):
        from clocktower.prompts import player_system
        s = player_system(10, private_beats=8)
        self.assertIn('private time: 8 beats', s)
        self.assertIn('you get eight whispers', s)
        self.assertIn('nobody else sees the words, or even that you whispered', s)
        self.assertNotIn('{P', s)

    def test_tie_means_no_execution(self):
        def policy(name, req):
            if req.kind == 'nominate' and name == C and D not in req.prompt:
                return {'nominate': D}
            if req.kind == 'nominate' and name == E:
                return {'nominate': F}
            if req.kind == 'vote':
                return {'vote': name in (A, B, C, E, G)}
        g = self.prepared(BASE, policy)
        g.rng = random.Random(3)
        run(g.nominations())
        results = [e['data'] for e in g.events if e['kind'] == 'vote_result']
        self.assertEqual(len(results), 2)
        self.assertEqual(results[1]['outcome'], 'tie')
        self.assertTrue(g.g[D].alive and g.g[F].alive)

    def test_nomination_has_accusation_defense_comments_then_votes(self):
        def policy(name, req):
            if req.kind == 'nominate' and name == C and req.options and D in req.options:
                return {'nominate': D, 'say': 'Suspicious.'}
            if req.kind == 'comment':
                return {'say': f'{name} comments.'}
        g = self.prepared(BASE, policy)
        run(g.nominations())
        kinds = [e['kind'] for e in g.events if e['kind'] in ('nomination', 'defense', 'say', 'vote')]
        self.assertEqual(kinds[:2], ['nomination', 'defense'])
        self.assertEqual(kinds[2:11], ['say'] * 9)  # everyone, the dead too, comments once
        self.assertEqual(kinds[11:], ['vote'] * 9)

    def test_slayer_can_shoot_during_nominations(self):
        chars = ['Imp', 'Poisoner', 'Slayer', 'Empath', 'Chef', 'Washerwoman', 'Soldier', 'Butler', 'Recluse']
        def policy(name, req):
            if req.kind == 'nominate' and name == D and req.options and E in req.options:
                return {'nominate': E}
            if req.kind == 'comment' and name == C:
                return {'slayer_shot': A}
        g = self.prepared(chars, policy)
        run(g.nominations())
        self.assertEqual(g.g.winner, 'good')
        self.assertFalse(any(e['kind'] == 'vote' for e in g.events))

    def test_every_day_runs_all_beats_even_when_silent(self):
        g = self.prepared(BASE, lambda n, r: None)  # nobody ever says or whispers anything
        run(g.daytime(1))
        beats = [e['data']['text'] for e in g.events if e['kind'] == 'header' and '·' in e['data']['text']]
        self.assertEqual(beats, [f'Day 1 · private time {k}' for k in range(1, 7)]
                         + [f'Day 1 · town square {k}' for k in (1, 2, 3)])

    def test_mayor_wins_with_three_alive_and_no_execution(self):
        chars = ['Imp', 'Poisoner', 'Mayor', 'Empath', 'Chef', 'Washerwoman', 'Soldier', 'Butler', 'Saint']
        g = self.prepared(chars, lambda n, r: None)
        for x in (D, E, F, G, H, I):
            g.g.die(g.g[x])
        g.private_beats, g.public_beats = 1, 1
        run(g.daytime(3))
        self.assertEqual(g.g.winner, 'good')

    def test_two_alive_is_an_evil_win(self):
        g = Grimoire(NAMES, BASE)
        for x in (C, D, E, F, G, H, I):
            g.die(g[x])
        self.assertEqual(g.check_victory(), 'evil')


class InformationTests(unittest.TestCase):
    def test_chef_with_recluse_can_see_extra_pair(self):
        chars = ['Imp', 'Recluse', 'Chef', 'Empath', 'Monk', 'Washerwoman', 'Soldier', 'Poisoner', 'Saint']
        g = Grimoire(NAMES, chars)
        c = chef_choice(g, g[C])
        self.assertTrue(c.legal({'number': 0}) and c.legal({'number': 1}))
        self.assertFalse(c.legal({'number': 2}))
        self.assertFalse(c.auto)

    def test_washerwoman_pair_must_contain_the_townsfolk(self):
        g = Grimoire(NAMES, BASE)
        c = pair_choice(g, g[F], 'Washerwoman')
        self.assertTrue(c.legal({'players': [C, A], 'character': 'Monk'}))
        self.assertFalse(c.legal({'players': [B, A], 'character': 'Monk'}))
        self.assertFalse(c.legal({'players': [F, C], 'character': 'Monk'}))  # never shown themselves
        self.assertTrue(c.legal(c.options(random.Random(0))))

    def test_drunk_washerwoman_can_be_told_anything(self):
        chars = ['Imp', 'Poisoner', 'Monk', 'Empath', 'Chef', 'Drunk', 'Soldier', 'Butler', 'Saint']
        g = Grimoire(NAMES, chars, drunk_as='Washerwoman')
        c = pair_choice(g, g[F], 'Washerwoman')
        self.assertTrue(c.legal({'players': [B, A], 'character': 'Mayor'}))

    def test_spy_can_register_as_townsfolk(self):
        chars = ['Imp', 'Spy', 'Monk', 'Empath', 'Chef', 'Washerwoman', 'Soldier', 'Butler', 'Saint']
        g = Grimoire(NAMES, chars)
        c = pair_choice(g, g[F], 'Washerwoman')
        self.assertTrue(c.legal({'players': [B, A], 'character': 'Mayor'}))

    def test_washerwoman_with_no_other_townsfolk_learns_so(self):
        g = Grimoire(NAMES[:5], ['Imp', 'Baron', 'Washerwoman', 'Saint', 'Butler'])  # 5 players, Baron: 1 Townsfolk
        c = pair_choice(g, g[C], 'Washerwoman')
        v = c.options(random.Random(0))
        self.assertEqual(v['players'], [])
        self.assertTrue(c.legal(v))
        self.assertEqual(info_text('Washerwoman', v), 'You learn that there are no other Townsfolk in play.')
        g = Grimoire(NAMES, BASE)
        self.assertFalse(pair_choice(g, g[F], 'Washerwoman').legal({'players': [], 'character': None}))


class ScriptedStorytellerTests(unittest.TestCase):
    def test_librarian_with_no_outsiders_can_learn_zero_or_see_the_spy(self):
        chars = ['Imp', 'Spy', 'Monk', 'Librarian', 'Chef', 'Washerwoman', 'Soldier', 'Empath', 'Mayor']
        g = Grimoire(NAMES, chars)
        seen = {bool(pair_choice(g, g[D], 'Librarian').options(random.Random(s))['players']) for s in range(200)}
        self.assertEqual(seen, {True, False})  # "zero" is reachable, not only the Spy

    def test_ravenkeeper_who_picks_themselves_sees_what_they_think_they_are(self):
        from clocktower.state import character_choice
        chars = ['Imp', 'Poisoner', 'Drunk', 'Chef', 'Empath', 'Monk', 'Washerwoman', 'Soldier', 'Saint']
        g = Grimoire(NAMES, chars, drunk_as='Ravenkeeper')
        shown = {character_choice(g, g[C], 'Ravenkeeper', C).options(random.Random(s))['character'] for s in range(100)}
        self.assertEqual(shown, {'Ravenkeeper'})

    def test_every_scripted_choice_is_legal(self):
        from clocktower.characters import TOWNSFOLK
        from clocktower.state import (character_choice, empath_choice, fortune_teller_choice, mayor_choice,
                                      random_setup)
        for seed in range(300):
            r = random.Random(seed)
            names = NAMES[:(5, 7, 9)[seed % 3]]
            chars = random_setup(r, players=len(names))
            r.shuffle(chars)
            g = Grimoire(names, chars, drunk_as=r.choice([c for c in TOWNSFOLK if c not in chars]))
            g.bluffs = r.sample([c for c in TOWNSFOLK if c not in chars], 3)
            g.red_herring = r.choice([q.name for q in g.players if not q.evil])
            g.poisoned = r.choice(names + [None])
            choices = []
            for p in (q for q in g.players if not q.evil):
                for ability in ('Washerwoman', 'Librarian', 'Investigator'):
                    choices.append(pair_choice(g, p, ability))
                choices += [chef_choice(g, p), empath_choice(g, p),
                            fortune_teller_choice(g, p, r.sample(names, 2)),
                            character_choice(g, p, 'Undertaker', r.choice(names))]
            mayor = next(q for q in g.players if not q.evil and q.character != 'Soldier')
            choices.append(mayor_choice(g, mayor, g.demon()))
            for c in choices:
                for _ in range(3):
                    v = c.options(r)
                    self.assertTrue(c.legal(v), (seed, c.id, v))

    def test_drunk_information_tells_one_consistent_story(self):
        chars = ['Imp', 'Poisoner', 'Monk', 'Drunk', 'Chef', 'Washerwoman', 'Soldier', 'Butler', 'Saint']
        g = Grimoire(NAMES, chars, drunk_as='Empath')
        r = random.Random(5)
        from clocktower.state import empath_choice
        with policy(drunk_truthful=0):
            answers = {empath_choice(g, g[D]).options(r)['number'] for _ in range(20)}
        self.assertEqual(len(answers), 1)
        framed, evil = g.decoy(g[D], r)
        self.assertFalse(g[framed].evil)
        self.assertNotIn(A, evil)  # the real Imp looks good

    def test_drunk_washerwoman_vouches_for_evil(self):
        chars = ['Imp', 'Poisoner', 'Monk', 'Drunk', 'Chef', 'Empath', 'Soldier', 'Butler', 'Saint']
        g = Grimoire(NAMES, chars, drunk_as='Washerwoman')
        g.bluffs = ['Virgin', 'Slayer', 'Recluse']
        r = random.Random(2)
        with policy(drunk_truthful=0, false_vouch_evil=1, as_bluff=1):
            v = pair_choice(g, g[D], 'Washerwoman').options(r)
        self.assertTrue({A, B} & set(v['players']))
        self.assertIn(v['character'], ('Virgin', 'Slayer'))


    def test_everything_plausible_is_reachable_and_nothing_impossible_appears(self):
        """No random floor: the style alone can give an impaired player every answer a working ability
        could give in some legal game (so no plausible option is ruled out), and never an impossible
        one (which would tell them they are impaired)."""
        from clocktower.state import chef_choice, character_choice, empath_choice, fortune_teller_choice
        chars = ['Imp', 'Spy', 'Monk', 'Drunk', 'Chef', 'Washerwoman', 'Soldier', 'Recluse', 'Saint']
        seen = {k: set() for k in ('chef', 'empath', 'ft', 'raven', 'undertaker')}
        for seed in range(3000):
            r = random.Random(seed)
            g = Grimoire(NAMES, chars, drunk_as=r.choice(['Chef', 'Empath', 'Fortune Teller', 'Ravenkeeper']))
            d = g[D]
            if d.shown == 'Chef':
                seen['chef'].add(chef_choice(g, d).options(r)['number'])
            elif d.shown == 'Empath':
                seen['empath'].add(empath_choice(g, d).options(r)['number'])
            elif d.shown == 'Fortune Teller':
                g.red_herring = F
                seen['ft'].add(fortune_teller_choice(g, d, r.sample([x for x in NAMES if x != D], 2)).options(r)['yes'])
            else:
                seen['raven'].add(character_choice(g, d, 'Ravenkeeper', r.choice([A, B, C, E])).options(r)['character'])
            g.alive_at_execution = r.choice([4, 7])
            seen['undertaker'].add((g.alive_at_execution,
                                    character_choice(g, d, 'Undertaker', r.choice([C, E, F])).options(r)['character']))  # not the real Imp: executing it ends the game
        self.assertEqual(seen['chef'], {0, 1, 2})  # 2 only through the Recluse, as for a working Chef
        self.assertEqual(seen['empath'], {0, 1, 2})
        self.assertEqual(seen['ft'], {True, False})
        self.assertIn('Imp', seen['raven'])
        self.assertIn((7, 'Imp'), seen['undertaker'])  # a Scarlet Woman could have caught the Demon
        self.assertNotIn((4, 'Imp'), seen['undertaker'])  # it could not: the game would have ended

    def test_the_drunk_is_sometimes_told_the_truth_all_game(self):
        from clocktower.state import empath_choice
        chars = ['Imp', 'Poisoner', 'Monk', 'Drunk', 'Chef', 'Washerwoman', 'Soldier', 'Butler', 'Saint']
        truthful = 0
        with policy():
            for seed in range(200):
                g = Grimoire(NAMES, chars, drunk_as='Empath')
                r = random.Random(seed)
                answers = {empath_choice(g, g[D]).options(r)['number'] for _ in range(5)}
                self.assertEqual(len(answers), 1)  # consistent either way
                truthful += answers == {0}  # the Drunk's real neighbours are good
        self.assertTrue(20 < truthful < 120, truthful)


class WholeGameTests(unittest.TestCase):
    def test_random_games_finish(self):
        for seed in range(40):
            rng = random.Random(seed)
            g = Game({n: RandomSeat(n, random.Random(rng.random()), NAMES) for n in NAMES},
                     ScriptedStoryteller(random.Random(seed)), seed=seed)
            result = run(g.run())
            self.assertFalse(result['errors'], result['errors'])
            self.assertIn(result['winner'], ('good', 'evil', None))

    def test_seats_receive_only_new_events_and_short_prompts(self):
        """No re-sent history or state dumps: what a seat receives is exactly the events it
        can see (each once) plus a short prompt per turn."""
        from clocktower.render import render
        seen = {n: [] for n in NAMES}

        class Recording(RandomSeat):
            async def act(self, text, request):
                seen[self.name].append((text, request.prompt))
                return await super().act(text, request)

        g = Game({n: Recording(n, random.Random(i), NAMES) for i, n in enumerate(NAMES)},
                 ScriptedStoryteller(random.Random(1)), seed=11)
        run(g.run())
        for name, turns in seen.items():
            self.assertTrue(all(len(p) < 700 for _, p in turns), 'prompts should be short')
            delivered = sum(len(t) - len(p) for t, p in turns)
            events = sum(len(x) + 1 for x in (render(e, name, set(e['dead'])) for e in g.events) if x is not None)
            pending = sum(len(x) + 1 for x in g.buf[name])
            self.assertLessEqual(delivered, events - pending + 8 * len(turns), f'{name} received repeated content')



class ProbeTests(unittest.TestCase):
    def test_parse(self):
        from clocktower.probe import parse
        text = ('Alex | 80% | 60 | Imp\n`Blair (dead)` | 10% | 0% | Chef\nnoise\nClaim | Empath\nPlan | Push Alex | today')
        out = parse(text, NAMES)
        self.assertEqual(out['players']['Alex'], {'evil': 0.8, 'demon': 0.6, 'character': 'Imp'})
        self.assertEqual(out['players']['Blair']['evil'], 0.1)
        self.assertEqual((out['claim'], out['plan']), ('Empath', 'Push Alex | today'))

    def test_probes_leave_the_game_unchanged(self):
        """Same seed with and without probes: identical events and identical turns for every seat."""
        def play(probes):
            seen, asked = [], []

            class Probed(RandomSeat):
                async def act(self, text, request):
                    seen.append((self.name, text))
                    return await super().act(text, request)

                async def probe(self, text, meta):
                    asked.append((self.name, meta['point'], text))
                    return Reply({**BLANK, 'say': 'Alex | 50 | 20 | Chef\nClaim | none\nPlan | wait'})

            seats = {n: Probed(n, random.Random(i), NAMES) for i, n in enumerate(NAMES)}
            g = Game(seats, ScriptedStoryteller(random.Random(3)), seed=5, probes=probes)
            run(g.run())
            return [(e['kind'], e['data']) for e in g.events], seen, asked, g
        events, seen, _, _ = play(False)
        events2, seen2, asked, g = play(True)
        self.assertEqual(events, events2)
        self.assertEqual(seen, seen2)
        points = [p for _, p, _ in asked]
        self.assertEqual(points.count('dawn'), 9)
        self.assertGreaterEqual(points.count('nominations'), 9)
        self.assertEqual(len(g.probe_log), len(asked))
        self.assertTrue(all(r['players']['Alex']['evil'] == 0.5 for r in g.probe_log))

    def test_claude_fork_does_not_touch_the_conversation(self):
        from types import SimpleNamespace as NS
        from clocktower.llm import ClaudeConversation, Ledger
        sent = []

        class Stream:
            def __init__(self, **kw):
                sent.append(kw['messages'])

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def get_final_message(self):
                usage = NS(model_dump=lambda **k: {'input_tokens': 1, 'output_tokens': 1})
                block = NS(type='text', text='{"say": "hi"}', model_dump=lambda **k: {'type': 'text', 'text': '{"say": "hi"}'})
                return NS(usage=usage, content=[block], stop_reason='end_turn', stop_details=None)

        import tempfile, pathlib
        client = NS(messages=NS(stream=lambda **kw: Stream(**kw)))
        ledger = Ledger(pathlib.Path(tempfile.mkdtemp()) / 'l.jsonl')
        c = ClaudeConversation(client, 'sys', {}, label='Alex', ledger=ledger, semaphore=asyncio.Semaphore(1))
        run(c.send('turn 1'))
        before = [dict(m) for m in c.messages]
        reply = run(c.send('probe?', commit=False))
        self.assertEqual(reply.action, {'say': 'hi'})
        self.assertEqual(c.messages, before)
        self.assertEqual(sent[-1], before + [{'role': 'user', 'content': 'probe?'}])
        run(c.send('turn 2'))
        self.assertEqual(sent[-1][:len(before)], before)
        self.assertEqual(len(c.messages), 4)


class V6Tests(unittest.TestCase):
    """Night order, starpass edge cases, and a Storyteller whose misinformation is really false."""

    def test_a_fortune_teller_killed_tonight_is_not_woken(self):
        chars = ['Imp', 'Poisoner', 'Fortune Teller', 'Empath', 'Chef', 'Washerwoman', 'Soldier', 'Butler', 'Saint']
        g = game(chars)
        run(g.setup())
        run(g.night(1))
        g.seats = {x: Seat(x, night_targets({A: [C], B: [E], C: [A, B], H: [D]}), g.texts) for x in NAMES}
        g.texts.clear()
        run(g.night(2))
        self.assertFalse(g.g[C].alive)
        self.assertFalse([k for n, k, _ in g.texts if n == C and k == 'night'])
        self.assertTrue([k for n, k, _ in g.texts if n == H and k == 'night'])  # the Butler still chooses

    def test_a_monk_protected_imp_cannot_starpass(self):
        chars = ['Imp', 'Poisoner', 'Monk', 'Empath', 'Chef', 'Washerwoman', 'Soldier', 'Butler', 'Saint']
        g = play_nights(chars, [{B: [E]}, {A: [A], B: [E], C: [A]}])
        self.assertTrue(g.g[A].alive)
        self.assertEqual(g.g[A].character, 'Imp')

    def test_poison_ends_when_the_poisoner_becomes_the_imp(self):
        g = play_nights(BASE, [{B: [E]}, {A: [A], B: [D]}])
        self.assertEqual(g.g[B].character, 'Imp')
        self.assertIsNone(g.g.poisoned)

    def test_extra_whisper_recipients_are_reported_to_the_sender(self):
        g = game(BASE)
        run(g.setup())
        out = g.whispers(A, {'whispers': [{'to': [B, C, D], 'text': 'hi'}]})
        self.assertEqual(out, [{'to': [B, C], 'text': 'hi'}])
        self.assertTrue(any('went only to' in t for t in g.buf[A]))

    def test_a_missing_vote_is_asked_again(self):
        asked = []

        def pol(name, req):
            if req.kind == 'vote':
                asked.append(name)
                return {'vote': None} if asked.count(name) == 1 else {'vote': True}
        g = game(BASE, pol)
        run(g.setup())
        g.day = 1
        run(g.vote(C, None, 0))
        self.assertEqual(sum(e['data']['yes'] for e in g.events if e['kind'] == 'vote'), 9)

    def test_misinformation_follows_one_false_world(self):
        """A misinformed player gets what a working ability would show in their false world (a framed
        good player is the Demon): consistent, never simply the opposite of the truth, and never
        self-revealing."""
        from clocktower.state import empath_choice, fortune_teller_choice, character_choice
        chars = ['Imp', 'Poisoner', 'Monk', 'Drunk', 'Chef', 'Washerwoman', 'Soldier', 'Butler', 'Saint']
        yes = 0
        with policy(drunk_truthful=0):
            for seed in range(300):
                r = random.Random(seed)
                g = Grimoire(NAMES, chars, drunk_as='Empath')
                framed, evil = g.decoy(g[D], r)
                want = sum(1 for q in g.neighbours(g[D]) if q.name in evil)
                self.assertEqual(empath_choice(g, g[D]).options(r)['number'], want)
                g = Grimoire(NAMES, chars, drunk_as='Fortune Teller')
                g.red_herring = F
                framed, _ = g.decoy(g[D], r)
                targets = r.sample([x for x in NAMES if x != D], 2)
                got = fortune_teller_choice(g, g[D], targets).options(r)['yes']
                self.assertEqual(got, any(t in (framed, F) for t in targets))
                yes += got
                g = Grimoire(NAMES, chars, drunk_as='Undertaker')
                self.assertNotEqual(character_choice(g, g[D], 'Undertaker', C).options(r)['character'], 'Imp')
                g = Grimoire(NAMES, chars, drunk_as='Washerwoman')
                v = pair_choice(g, g[D], 'Washerwoman').options(r)
                self.assertNotEqual(v['character'], 'Washerwoman')
        self.assertLess(yes, 150)  # random pairs mostly read NO, as for a working Fortune Teller

    def test_bluffs_rarely_include_the_drunks_character(self):
        from clocktower.state import pick_bluffs
        from clocktower.characters import GOOD
        options = [c for c in GOOD if c not in ('Monk', 'Empath', 'Chef', 'Soldier', 'Butler', 'Saint', 'Drunk')]
        options.append('Drunk')
        hits = sum('Fortune Teller' in pick_bluffs(random.Random(i), options, False, 'Fortune Teller')
                   for i in range(2000))
        self.assertLess(hits, 60)

    def test_the_investigator_partner_is_usually_good(self):
        chars = ['Imp', 'Poisoner', 'Investigator', 'Empath', 'Chef', 'Washerwoman', 'Soldier', 'Butler', 'Saint']
        g = Grimoire(NAMES, chars)
        both = 0
        with policy():
            for i in range(1000):
                v = pair_choice(g, g[C], 'Investigator').options(random.Random(i))
                both += set(v['players']) == {A, B}
        self.assertLess(both, 30)


    def test_a_failing_seat_stops_the_game(self):
        class Broken(RandomSeat):
            async def act(self, text, request):
                if request.kind == 'beat':
                    raise RuntimeError('credit balance is too low')
                return await super().act(text, request)
        seats = {n: (Broken if n == C else RandomSeat)(n, random.Random(i), NAMES) for i, n in enumerate(NAMES)}
        result = run(Game(seats, ScriptedStoryteller(random.Random(1)), seed=3).run())
        self.assertIsNone(result['winner'])
        self.assertIn('seat failed', result['stopped'])


class TypographyTests(unittest.TestCase):
    def test_every_seat_speaks_in_one_typography(self):
        from clocktower.game import clip
        self.assertEqual(clip('I\u2019m **sure** \u2014 it\u2019s \u201cKit\u201d\u2026', 60), 'I\'m sure - it\'s "Kit"...')
        self.assertEqual(clip("I'm sure - it's \"Kit\"...", 60), 'I\'m sure - it\'s "Kit"...')


class TableSizeTests(unittest.TestCase):
    def test_a_range_picks_the_size_from_the_seed(self):
        from clocktower.cli import table_size
        self.assertEqual(table_size('12', 7), 12)
        self.assertEqual([table_size('10-12', s) for s in range(60000, 60006)], [10, 11, 12, 10, 11, 12])
        with self.assertRaises(ValueError):
            table_size('4-12', 1)

    def test_every_size_deals_a_legal_setup(self):
        from clocktower.state import random_setup
        from clocktower.characters import SETUPS
        for n in SETUPS:
            for seed in range(50):
                chars = random_setup(random.Random(seed), None, n)
                self.assertIsNone(setup_error(chars), (n, chars))

    def test_minions_know_each_other_and_the_imp_knows_them_all(self):
        from clocktower.game import ALL_NAMES
        names = ALL_NAMES[:12]
        chars = ['Imp', 'Poisoner', 'Spy', 'Monk', 'Empath', 'Chef', 'Washerwoman', 'Soldier', 'Mayor', 'Virgin',
                 'Butler', 'Saint']
        g = Game({n: RandomSeat(n, random.Random(0), names) for n in names}, ScriptedStoryteller(random.Random(0)),
                 names=names, characters=chars, seed=1)
        run(g.setup())
        self.assertTrue(any('Your Minions: Blair, Casey' in t for t in g.buf[names[0]]))
        self.assertTrue(any('Your fellow Minion: Casey' in t for t in g.buf[names[1]]))
        self.assertTrue(any('Your fellow Minion: Blair' in t for t in g.buf[names[2]]))

    def test_starpass_goes_to_the_scarlet_woman_first(self):
        from clocktower.game import ALL_NAMES
        names = ALL_NAMES[:12]
        chars = ['Imp', 'Poisoner', 'Scarlet Woman', 'Monk', 'Empath', 'Chef', 'Washerwoman', 'Soldier', 'Mayor',
                 'Virgin', 'Butler', 'Saint']
        log = []
        g = Game({n: Seat(n, lambda n_, r: None, log) for n in names}, Storyteller(), names=names, characters=chars,
                 seed=2)
        run(g.setup())
        run(g.night(1))
        g.seats = {n: Seat(n, night_targets({names[0]: [names[0]], names[1]: [names[5]]}), log) for n in names}
        run(g.night(2))
        self.assertEqual(g.g[names[2]].character, 'Imp')
        self.assertEqual(g.g[names[1]].character, 'Poisoner')

    def test_twelve_player_random_games_finish(self):
        from clocktower.game import ALL_NAMES
        names = ALL_NAMES[:12]
        done = 0
        for seed in range(20):
            rng = random.Random(seed)
            g = Game({n: RandomSeat(n, random.Random(rng.random()), names) for n in names},
                     ScriptedStoryteller(random.Random(seed)), names=names, seed=seed, max_days=15)
            result = run(g.run())
            self.assertFalse(result['errors'], result['errors'])
            done += result['winner'] is not None
        self.assertGreater(done, 12)


if __name__ == '__main__':
    unittest.main()


class V12Tests(unittest.TestCase):
    """The three Storyteller principles of the frozen protocol."""

    def test_poisoned_results_are_false_whenever_they_can_be(self):
        from clocktower.state import empath_choice
        chars = ['Imp', 'Poisoner', 'Chef', 'Empath', 'Monk', 'Washerwoman', 'Soldier', 'Butler', 'Saint']
        false = n = 0
        for s in range(400):
            g = Grimoire(NAMES, chars)
            g.poisoned = C  # the Chef; the truth is 1 pair (Imp, Poisoner)
            v = chef_choice(g, g[C]).options(random.Random(s))['number']
            false += v != 1
            g.poisoned = D  # the Empath, next to Chef and Monk: the truth is 0
            n += empath_choice(g, g[D]).options(random.Random(s))['number'] != 0
        # misinformed 80% of the time, and then (nearly) always false
        self.assertGreater(false, 0.7 * 400)
        self.assertGreater(n, 0.7 * 400)

    def test_a_poisoned_fortune_teller_pointing_at_the_red_herring_can_hear_no(self):
        from clocktower.state import fortune_teller_choice
        g = Grimoire(NAMES, BASE)
        g.players[3].character = g.players[3].shown = 'Fortune Teller'  # D, poisoned
        g.red_herring, g.poisoned = E, D  # the Chef is the red herring
        answers = {fortune_teller_choice(g, g[D], [E, F]).options(random.Random(s))['yes'] for s in range(200)}
        self.assertIn(False, answers)

    def test_demon_bluffs_include_an_outsider_only_with_the_drunk_in_play(self):
        from clocktower.state import pick_bluffs
        from clocktower.characters import GOOD, OUTSIDERS
        options = [c for c in GOOD if c not in ('Monk', 'Empath', 'Chef', 'Soldier', 'Washerwoman')]
        for s in range(300):
            self.assertFalse(set(pick_bluffs(random.Random(s), options, False)) & set(OUTSIDERS))
        with_drunk = [len(set(pick_bluffs(random.Random(s), options, True)) & set(OUTSIDERS)) for s in range(300)]
        self.assertEqual(set(with_drunk), {1})

    def test_no_baron_is_shown_at_a_table_without_one(self):
        from clocktower.state import character_choice
        chars = ['Imp', 'Poisoner', 'Recluse', 'Investigator', 'Undertaker', 'Monk', 'Washerwoman', 'Soldier', 'Saint']
        g = Grimoire(NAMES, chars)
        g.alive_at_execution = 9
        for s in range(400):
            r = random.Random(s)
            self.assertNotEqual(pair_choice(g, g[D], 'Investigator').options(r)['character'], 'Baron')
            self.assertNotEqual(character_choice(g, g[E], 'Undertaker', C).options(r)['character'], 'Baron')

    def test_an_executed_recluse_is_not_shown_as_the_imp_with_fewer_than_five_alive(self):
        from clocktower.state import character_choice
        chars = ['Imp', 'Poisoner', 'Recluse', 'Investigator', 'Undertaker', 'Monk', 'Washerwoman', 'Soldier', 'Saint']
        g = Grimoire(NAMES, chars)
        g.alive_at_execution = 4
        shown = {character_choice(g, g[E], 'Undertaker', C).options(random.Random(s))['character'] for s in range(300)}
        self.assertNotIn('Imp', shown)
        self.assertIn('Recluse', shown)

    def test_the_spy_sees_what_the_pair_abilities_were_shown(self):
        chars = ['Imp', 'Spy', 'Washerwoman', 'Librarian', 'Investigator', 'Monk', 'Chef', 'Butler', 'Saint']
        g = game(chars)
        run(g.setup())
        run(g.night(1))
        spy = [e['data']['text'] for e in g.events if e['kind'] == 'info' and 'look at the Grimoire' in e['data']['text']]
        self.assertTrue(spy)
        for role in ('Washerwoman', 'Librarian', 'Investigator'):
            self.assertIn(f'({role}) was shown:', spy[-1])


class SeatModelTests(unittest.TestCase):
    def args(self, **kw):
        import argparse
        base = dict(model='m0', good_model='a', evil_model='b', effort='high', good_effort=None, evil_effort=None,
                    seat_model=[])
        return argparse.Namespace(**{**base, **kw})

    def test_teams_mixed_models_and_seat_overrides(self):
        from clocktower.cli import seat_models
        g = Grimoire(NAMES, BASE)  # evil: Alex (Imp), Blair (Poisoner)
        out = seat_models(g, self.args(), 1)
        self.assertEqual({out[A], out[B]}, {('b', 'high')})
        self.assertEqual({out[n] for n in NAMES[2:]}, {('a', 'high')})
        mixed = seat_models(g, self.args(good_model='a,c@low'), 1)
        good = [mixed[n] for n in NAMES[2:]]
        self.assertEqual(sorted(set(good)), [('a', 'high'), ('c', 'low')])
        self.assertLessEqual(abs(good.count(('a', 'high')) - good.count(('c', 'low'))), 1)
        one = seat_models(g, self.args(seat_model=['good:x:1', 'Imp:y@max']), 1)
        self.assertEqual(sum(one[n] == ('x', 'high') for n in NAMES[2:]), 1)
        self.assertEqual(one[A], ('y', 'max'))
        self.assertEqual(seat_models(g, self.args(seat_model=['good:x:1']), 1), one | {A: ('b', 'high')})


class ContextTests(unittest.TestCase):
    def test_oldest_turns_but_never_the_first_are_dropped_to_fit_the_window(self):
        from clocktower.llm import OpenAIConversation, Ledger, NO_LIMIT
        import os, tempfile
        os.environ.setdefault('OPENAI_API_KEY', 'test')
        c = OpenAIConversation('rules', {}, label='x', ledger=Ledger(tempfile.mktemp()), semaphore=NO_LIMIT,
                               model='gpt-4o', flex=False, max_tokens=32_000)
        self.assertEqual(c.max_tokens, 16_384)  # GPT-4o's own output limit
        big = 'word ' * 20_000
        for k in range(12):
            c.messages += [{'role': 'user', 'content': [{'type': 'input_text', 'text': f'turn {k} ' + big}]},
                           {'role': 'assistant', 'content': 'ok'}]
        c.last_input = 125_000
        c.fit('next')
        texts = [m['content'][0]['text'][:7] for m in c.messages if m.get('role') == 'user']
        self.assertEqual(texts[0], 'turn 0 ')  # the first turn (character and setup) stays
        self.assertGreater(c.trimmed, 0)
        self.assertEqual(texts[1], f'turn {c.trimmed + 1} ')  # then the most recent turns


class CeilingTests(unittest.TestCase):
    def test_a_turn_that_hits_the_ceiling_is_retried_once_at_low_effort(self):
        from clocktower.llm import OpenAIConversation, Ledger, NO_LIMIT
        import os, tempfile, json as _json
        os.environ.setdefault('OPENAI_API_KEY', 'test')
        c = OpenAIConversation('rules', {}, label='x', ledger=Ledger(tempfile.mktemp()), semaphore=NO_LIMIT,
                               model='gpt-5.1')
        efforts, replies = [], [
            {'status': 'incomplete', 'incomplete_details': {'reason': 'max_output_tokens'}, 'output': [], 'usage': {}},
            {'status': 'completed', 'output': [{'type': 'message', 'content': [
                {'type': 'output_text', 'text': _json.dumps({'say': 'hi'})}]}], 'usage': {}}]

        async def fake(body):
            efforts.append(body['reasoning']['effort'])
            return replies.pop(0)
        c._request = fake
        self.assertEqual(c.max_tokens, 8000)
        self.assertEqual(run(c.send('go')).action, {'say': 'hi'})
        self.assertEqual(efforts, ['high', 'low'])

    def test_adaptive_claude_retries_without_thinking(self):
        from clocktower.llm import ClaudeConversation, Ledger, NO_LIMIT
        import tempfile
        c = ClaudeConversation(None, 'rules', {}, label='x', ledger=Ledger(tempfile.mktemp()), semaphore=NO_LIMIT,
                               model='claude-opus-4-8')
        self.assertEqual(c._thinking()['thinking']['type'], 'adaptive')
        self.assertEqual(c._thinking(low=True)['thinking'], {'type': 'disabled'})
        f = ClaudeConversation(None, 'rules', {}, label='x', ledger=Ledger(tempfile.mktemp()), semaphore=NO_LIMIT,
                               model='claude-fable-5')  # can't switch thinking off: lowest effort instead
        self.assertEqual(f._thinking(low=True)['thinking']['type'], 'adaptive')
        self.assertEqual(f._thinking(low=True)['output_config']['effort'], 'low')

    def test_a_model_that_rejects_thinking_off_is_marked_and_retried(self):
        from clocktower import llm
        import anthropic, tempfile
        sent = []

        class Stream:
            def __init__(self, kw):
                self.kw = kw

            async def __aenter__(self):
                sent.append(self.kw['thinking']['type'])
                if self.kw['thinking']['type'] == 'disabled':
                    e = anthropic.BadRequestError.__new__(anthropic.BadRequestError)
                    Exception.__init__(e, 'thinking.type.disabled is not supported for this model')
                    raise e
                return self

            async def __aexit__(self, *exc):
                return False

            async def get_final_message(self):
                return 'ok'

        class Client:
            class messages:
                stream = staticmethod(lambda **kw: Stream(kw))

        model = 'claude-test-no-off'
        c = llm.ClaudeConversation(Client(), 'rules', {}, label='x', ledger=llm.Ledger(tempfile.mktemp()),
                                   semaphore=llm.NO_LIMIT, model=model)
        try:
            self.assertEqual(asyncio.run(c._stream([], low=True)), 'ok')
            self.assertEqual(sent, ['disabled', 'adaptive'])
            self.assertFalse(llm.spec(model)['can_disable_thinking'])
        finally:
            llm.MODELS.pop(model, None)

    def test_openai_waits_for_credit_instead_of_failing(self):
        from clocktower import llm
        import os, tempfile, io, urllib.error
        os.environ.setdefault('OPENAI_API_KEY', 'test')
        c = llm.OpenAIConversation('rules', {}, label='x', ledger=llm.Ledger(tempfile.mktemp()),
                                   semaphore=llm.NO_LIMIT, model='gpt-5.4')
        calls = []

        def post(body):
            calls.append(1)
            if len(calls) < 3:
                raise urllib.error.HTTPError('u', 429, 'quota', {}, io.BytesIO(b'{"error": {"code": "insufficient_quota"}}'))
            return {'ok': True}
        c._post = post
        slept = []

        async def nap(t):
            slept.append(t)
        real, llm.asyncio.sleep = llm.asyncio.sleep, nap
        try:
            self.assertEqual(run(c._request({})), {'ok': True})
        finally:
            llm.asyncio.sleep = real
        self.assertEqual(slept, [30, 30])


class WhisperTests(unittest.TestCase):
    def test_one_whisper_a_turn(self):
        def policy(name, req):
            if req.kind == 'beat' and name == A:
                return {'whispers': [{'to': [B], 'text': 'first'}, {'to': [C], 'text': 'second'}]}
        g = game(BASE, policy)
        run(g.setup())
        g.private_beats, g.public_beats = 1, 0
        run(g.daytime(1))
        sent = [e['data'] for e in g.events if e['kind'] == 'whisper']
        self.assertEqual([(w['to'], w['text']) for w in sent], [([B], 'first')])


class CheckpointTests(unittest.TestCase):
    def test_a_stop_file_halts_one_game_which_then_resumes_and_finishes(self):
        import tempfile
        from pathlib import Path
        chars = ['Imp', 'Poisoner', 'Monk', 'Empath', 'Chef', 'Washerwoman', 'Soldier', 'Butler', 'Saint']
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'g'
            first = game(chars, out=out, probes=False)
            first.private_beats = first.public_beats = 1
            night = first.night

            async def halt_on_night_2(n):
                if n == 2:
                    (out / 'STOP').touch()
                return await night(n)
            first.night = halt_on_night_2
            r = run(first.run())
            self.assertTrue(r['reason'].startswith('halted'))
            self.assertTrue((out / 'checkpoint.pkl').exists())
            (out / 'STOP').unlink()
            again = game(chars, out=out, probes=False)
            again.private_beats = again.public_beats = 1
            self.assertIsNotNone(run(again.run())['winner'])

    def test_a_killed_game_resumes_from_its_last_dusk_and_plays_out_the_same(self):
        import tempfile, json as _json
        from pathlib import Path
        chars = ['Imp', 'Poisoner', 'Monk', 'Empath', 'Chef', 'Washerwoman', 'Soldier', 'Butler', 'Saint']
        with tempfile.TemporaryDirectory() as d:
            whole = game(chars, out=Path(d) / 'whole', probes=False)
            whole.private_beats = whole.public_beats = 1
            r1 = run(whole.run())

            first = game(chars, out=Path(d) / 'killed', probes=False)
            first.private_beats = first.public_beats = 1
            night = first.night

            async def crash(n):
                if n == 3:
                    raise KeyboardInterrupt  # the machine restarts during night 3
                return await night(n)
            first.night = crash
            with self.assertRaises(KeyboardInterrupt):
                run(first.run())
            self.assertTrue((Path(d) / 'killed' / 'checkpoint.pkl').exists())

            again = game(chars, out=Path(d) / 'killed', probes=False)
            again.private_beats = again.public_beats = 1
            r2 = run(again.run())
            strip = lambda evs: [(e['day'], e['kind'], _json.dumps(e['data'], sort_keys=True)) for e in evs]
            self.assertEqual(strip(again.events), strip(whole.events))
            self.assertEqual((r1['winner'], r1['days']), (r2['winner'], r2['days']))
            logged = [_json.loads(l) for l in (Path(d) / 'killed' / 'events.jsonl').read_text().splitlines()]
            self.assertEqual(strip(logged), strip(whole.events))  # the log reads as if play never stopped
            self.assertFalse((Path(d) / 'killed' / 'checkpoint.pkl').exists())


class TellTests(unittest.TestCase):
    def test_hyphens_bullets_arrows_emoji_and_cut_marks_look_the_same_for_every_model(self):
        from clocktower.game import clip
        self.assertEqual(clip('non‑breaking • point → next \U0001F600 ok ✅', 60),
                         'non-breaking - point -> next ok')
        self.assertEqual(clip('word ' * 10, 3), 'word word word...')

    def test_speech_in_private_time_is_answered_with_a_notice(self):
        def policy(name, req):
            if req.kind == 'beat' and name == A:
                return {'say': 'Hello everyone'}
        g = game(BASE, policy)
        run(g.setup())
        g.private_beats, g.public_beats = 1, 0
        run(g.daytime(1))
        self.assertFalse([e for e in g.events if e['kind'] == 'say'])
        self.assertTrue([e for e in g.events if e['kind'] == 'notice' and 'private time' in e['data']['text']
                         and e['to'] == [A]])
