"""Bad Moon Rising (experimental): rule tests on forced setups, and random games as an engine check."""
import asyncio
import hashlib
import random
import unittest

from clocktower.agents import RandomSeat, ScriptedStoryteller
from clocktower.bmr import BMRGame, random_setup, setup_error
from clocktower.characters import BMR
from clocktower.game import ALL_NAMES
from clocktower.llm import Reply
from clocktower.prompts import player_system
from clocktower.schema import player_schema

A, B, C, D, E, F, G, H = ALL_NAMES[:8]
BLANK = {'say': '', 'whispers': [], 'nominate': None, 'vote': None, 'targets': [], 'character': None}
FILL = ['Courtier', 'Professor', 'Minstrel', 'Grandmother']  # Townsfolk that do nothing unless told to
GRANDCHILD = {'Grandmother:Ellis': {'players': [D], 'character': 'Minstrel'}}


class Seat:
    def __init__(self, name, policy, log):
        self.name, self.policy, self.log = name, policy, log

    async def act(self, text, request):
        self.log.append((self.name, request, text))
        return Reply({**BLANK, **(self.policy(self.name, request) or {})})


class Storyteller:
    def __init__(self, decisions=None):
        self.decisions = decisions or {}
        self.rng = random.Random(0)

    def choose(self, choice):
        return {**choice.options(self.rng), **self.decisions.get(choice.id, {})}


def table(characters, nights=None, decisions=None, claims=None):
    """A game with these characters in seating order. `nights` is {night: {name: action}}; `claims` is
    {name: target} for the Moonchild's public choice. Everything else passes."""
    names = ALL_NAMES[:len(characters)]

    def policy(name, req):
        if req.kind == 'night':
            return (nights or {}).get(req.day, {}).get(name)
        if req.kind == 'death' and name in (claims or {}):
            return {'targets': [claims[name]]}

    log = []
    g = BMRGame({n: Seat(n, policy, log) for n in names}, Storyteller({**GRANDCHILD, **(decisions or {})}),
                names=names, characters=characters, seed=7, probes=False)
    g.log = log
    return g


def run(coro):
    return asyncio.run(coro)


def play(g, *steps):
    """Setup, then each step: an int n plays night n; a name executes that player (and asks for the
    Moonchild's choice)."""
    async def go():
        await g.setup()
        for s in steps:
            if isinstance(s, int):
                await g.night(s)
            else:
                g.claims = []
                g.execute(s)
                await g.death_claims(g.claims)
    run(go())
    return g


def kills(*targets):
    return {'targets': list(targets)}


def alive(g):
    return {p.name for p in g.g.players if p.seems_alive}


def asked(g, name, night):
    return [r for n, r, _ in g.log if n == name and r.kind == 'night' and r.day == night]


def heard(g, name):
    return '\n'.join(t for n, _, t in g.log if n == name) + '\n'.join(g.buf[name])


def seven(first, minion, demon):
    return [first, *FILL, minion, demon]  # A, then B Courtier, C Professor, D Minstrel, E Grandmother, F, G


class SetupTests(unittest.TestCase):
    def test_setup_legality(self):
        self.assertIsNone(setup_error(seven('Fool', 'Assassin', 'Po')))
        self.assertIn('Outsiders', setup_error(seven('Fool', 'Godfather', 'Po')))  # the Godfather adds or removes one
        self.assertIsNone(setup_error(['Tinker', *FILL, 'Godfather', 'Po']))
        self.assertIn('not on the script', setup_error(seven('Gossip', 'Assassin', 'Po')))
        self.assertIn('one Demon', setup_error(['Fool', *FILL, 'Po', 'Pukka']))
        for seed in range(200):
            r = random.Random(seed)
            n = r.randint(5, 15)
            self.assertIsNone(setup_error(random_setup(r, players=n)), (seed, n))

    def test_prompt_and_schema(self):
        text = player_system(10, script='bmr')
        for c in BMR.all:
            self.assertIn(f'- {c}:', text)
        self.assertNotIn('Imp', text)
        self.assertNotIn('Slayer', text)
        self.assertNotIn('Gossip:', text)
        props = player_schema([A, B], 'bmr')['properties']
        self.assertIn('character', props)
        self.assertNotIn('slayer_shot', props)
        # the rated game's prompt and schema are untouched
        self.assertEqual(hashlib.sha256(player_system(9).encode()).hexdigest()[:12], 'd31975739121')
        self.assertIn('slayer_shot', player_schema([A, B])['properties'])

    def test_lunatic_thinks_they_are_the_demon_and_the_demon_hears_their_choices(self):
        chars = ['Lunatic', 'Courtier', 'Professor', 'Minstrel', 'Pacifist', 'Fool', 'Assassin', 'Shabaloth']
        g = play(table(chars, {2: {A: kills(B, C), H: kills(D, E)}},
                       {'lunatic_as': {'character': 'Shabaloth'}, 'Shabaloth:regurgitate': {'players': []}}), 1, 2)
        self.assertIn('Your character: Shabaloth (Demon, evil team)', heard(g, A))
        self.assertIn('Your Minion:', heard(g, A))
        self.assertIn(f'The Lunatic is {A}', heard(g, H))
        self.assertIn(f'the Lunatic ({A}) chose {B} and {C}', heard(g, H))
        self.assertEqual(alive(g), {A, B, C, F, G, H})  # only the real Demon's choices died
        self.assertFalse(g.g[A].evil)


class DemonTests(unittest.TestCase):
    def test_shabaloth_kills_two_and_may_regurgitate(self):
        g = play(table(seven('Pacifist', 'Assassin', 'Shabaloth'), {2: {G: kills(A, B)}, 3: {G: kills(C, D)}},
                       {'Shabaloth:regurgitate': {'players': [B]}}), 1, 2, 3)
        self.assertEqual(alive(g), {B, F, G})  # the Grandmother (Ellis) died with her grandchild, Drew
        dawn = [e for e in g.events if e['kind'] == 'dawn'][-1]['data']
        self.assertEqual((sorted(dawn['deaths']), dawn['risen']), ([C, D, E], [B]))

    def test_po_kills_three_after_choosing_no_one(self):
        g = play(table(seven('Pacifist', 'Assassin', 'Po'), {2: {G: kills()}, 3: {G: kills(A, B, C)}}), 1, 2, 3)
        self.assertEqual(asked(g, G, 1), [])
        self.assertTrue(asked(g, G, 2)[0].optional)
        self.assertEqual(asked(g, G, 3)[0].n_targets, 3)
        self.assertEqual(alive(g), {D, E, F, G})

    def test_zombuul_sleeps_after_a_death_and_dies_twice(self):
        g = play(table(seven('Pacifist', 'Assassin', 'Zombuul'), {2: {G: kills(A)}, 5: {G: kills(C)}}),
                 1, 2, B, 3, G, 4, 5)
        self.assertEqual(len(asked(g, G, 2)), 1)
        self.assertEqual(asked(g, G, 3), [])   # Blair died by execution that day
        self.assertEqual(asked(g, G, 4), [])   # the Zombuul "died" that day
        self.assertEqual(len(asked(g, G, 5)), 1)  # looks dead, still kills
        z = g.g[G]
        self.assertTrue(z.alive and z.looks_dead)
        self.assertIsNone(g.g.winner)
        self.assertEqual(alive(g), {D, E, F})
        self.assertIn(G, [e for e in g.events if e['kind'] == 'dawn'][-1]['dead'])  # the town sees them dead
        g.execute(G)
        self.assertEqual(g.g.winner, 'good')

    def test_pukka_poisons_then_kills_even_a_sailor(self):
        g = play(table(seven('Sailor', 'Assassin', 'Pukka'),
                       {1: {A: kills(B), G: kills(A)}, 2: {A: kills(B), G: kills(C)}},
                       {'Sailor:Alex': {'players': [B]}}), 1, 2)
        self.assertEqual(alive(g), {B, C, D, E, F, G})  # the poisoned Sailor can die
        self.assertTrue(g.g.is_poisoned(g.g[C]))

    def test_exorcised_pukka_still_loses_its_victim_but_poisons_no_one(self):
        g = play(table(seven('Exorcist', 'Assassin', 'Pukka'),
                       {1: {G: kills(B)}, 2: {A: kills(G)}, 3: {A: kills(C), G: kills(D)}}), 1, 2)
        self.assertEqual(asked(g, G, 2), [])
        self.assertIn(f'The Exorcist is {A}', heard(g, G))
        self.assertEqual(alive(g), {A, C, D, E, F, G})
        self.assertIsNone(g.g.pukka_poisoned)


class ProtectionTests(unittest.TestCase):
    def test_sailor_cannot_die_at_night_or_by_execution(self):
        g = play(table(seven('Sailor', 'Assassin', 'Shabaloth'),
                       {1: {A: kills(B)}, 2: {A: kills(B), G: kills(A, C)}}, {'Sailor:Alex': {'players': [B]}}), 1, 2, A)
        self.assertEqual(alive(g), {A, B, D, E, F, G})
        ex = [e for e in g.events if e['kind'] == 'execution'][-1]['data']
        self.assertEqual((ex['died'], ex['survived']), (False, True))

    def test_innkeeper_protects_two_but_not_from_the_assassin(self):
        nights = {2: {A: kills(B, C), G: kills(B, C), F: kills(B)}}
        g = play(table(seven('Innkeeper', 'Assassin', 'Shabaloth'), nights, {'Innkeeper:Alex': {'players': [C]}}), 1, 2)
        self.assertEqual(alive(g), {A, C, D, E, F, G})  # only the Assassin's kill landed
        self.assertTrue(g.g.is_poisoned(g.g[C]))
        self.assertEqual(asked(g, F, 3), [])

    def test_tea_lady_protects_good_neighbours_while_she_lives(self):
        chars = ['Courtier', 'Tea Lady', 'Professor', 'Minstrel', 'Grandmother', 'Assassin', 'Shabaloth']
        g = play(table(chars, {2: {G: kills(A, C)}},
                       {'Shabaloth:regurgitate': {'players': []}}), 1, 2)
        self.assertEqual(len(alive(g)), 7)
        play_more = table(chars, {2: {G: kills(B, D)}, 3: {G: kills(A, C)}}, {'Shabaloth:regurgitate': {'players': []}})
        g = play(play_more, 1, 2, 3)
        self.assertEqual(alive(g), {F, G})  # Drew's Grandmother went with them

    def test_a_professor_killed_by_the_assassin_does_not_act(self):
        g = play(table(seven('Pacifist', 'Assassin', 'Po'),
                       {2: {G: kills()}, 3: {G: kills(A, B, D)}, 4: {F: kills(C), C: kills(A), G: kills()}}), 1, 2, 3, 4)
        self.assertEqual(alive(g), {F, G})
        self.assertNotIn(C, g.g.woke)

    def test_fool_survives_once(self):
        g = play(table(seven('Fool', 'Assassin', 'Shabaloth'), {2: {G: kills(A, B)}, 3: {G: kills(A, C)}},
                       {'Shabaloth:regurgitate': {'players': []}}), 1, 2)
        self.assertIn(A, alive(g))
        g = play(table(seven('Fool', 'Assassin', 'Shabaloth'), {2: {G: kills(A, B)}, 3: {G: kills(A, C)}},
                       {'Shabaloth:regurgitate': {'players': []}}), 1, 2, 3)
        self.assertEqual(alive(g), {D, E, F, G})

    def test_devils_advocate_and_pacifist_stop_executions(self):
        g = play(table(seven('Fool', "Devil's Advocate", 'Po'), {1: {F: kills(G)}}), 1, G)
        self.assertIsNone(g.g.winner)
        self.assertIn(G, alive(g))
        g = play(table(seven('Pacifist', 'Assassin', 'Po'), decisions={'Pacifist:Blair': {'yes': True}}), 1, B, F)
        self.assertEqual(alive(g), {A, B, C, D, E, G})  # the good player was spared, the Minion was not


class TownsfolkTests(unittest.TestCase):
    def test_exorcist_cannot_choose_the_same_player_twice_running(self):
        g = play(table(seven('Exorcist', 'Assassin', 'Shabaloth'), {2: {A: kills(G)}, 3: {A: kills(B), G: kills(B, C)}},
                       {'Shabaloth:regurgitate': {'players': []}}), 1, 2, 3)
        self.assertNotIn(G, asked(g, A, 3)[0].options)
        self.assertEqual(asked(g, G, 2), [])
        self.assertEqual(alive(g), {A, D, E, F, G})

    def test_gambler_dies_on_a_wrong_guess(self):
        for guess, lives in (('Po', False), ('Shabaloth', True)):
            g = play(table(seven('Gambler', 'Assassin', 'Shabaloth'),
                           {2: {A: {'targets': [G], 'character': guess}, G: kills(B, C)}}), 1, 2)
            self.assertEqual(A in alive(g), lives, guess)

    def test_courtier_makes_a_character_drunk_for_three_nights(self):
        nights = {1: {B: {'character': 'Shabaloth'}}, 2: {G: kills(A, C)}, 3: {G: kills(A, C)}, 4: {G: kills(A, C)}}
        g = play(table(seven('Pacifist', 'Assassin', 'Shabaloth'), nights, {'Shabaloth:regurgitate': {'players': []}}), 1, 2, 3)
        self.assertEqual(len(alive(g)), 7)
        self.assertEqual(asked(g, B, 2), [])  # once per game
        g = play(table(seven('Pacifist', 'Assassin', 'Shabaloth'), nights, {'Shabaloth:regurgitate': {'players': []}}), 1, 2, 3, 4)
        self.assertEqual(alive(g), {B, D, E, F, G})

    def test_professor_resurrects_a_townsfolk(self):
        g = play(table(seven('Pacifist', 'Assassin', 'Po'), {2: {G: kills()}, 3: {G: kills(A, B, D)}, 4: {C: kills(A), G: kills()}}), 1, 2, 3, 4)
        self.assertEqual(alive(g), {A, C, F, G})
        self.assertEqual([e for e in g.events if e['kind'] == 'dawn'][-1]['data']['risen'], [A])

    def test_grandmother_dies_with_her_grandchild(self):
        g = play(table(seven('Grandmother', 'Assassin', 'Shabaloth')[:4] + ['Pacifist', 'Assassin', 'Shabaloth'],
                       {2: {G: kills(B, C)}}, {'Grandmother:Alex': {'players': [B], 'character': 'Courtier'}}), 1, 2)
        self.assertIn(f'your grandchild is {B}, who is the Courtier', heard(g, A))
        self.assertEqual(alive(g), {D, E, F, G})

    def test_minstrel_makes_everyone_drunk_after_a_minion_is_executed(self):
        g = play(table(seven('Pacifist', 'Assassin', 'Shabaloth'), {2: {G: kills(A, B)}, 3: {G: kills(A, B)}},
                       {'Shabaloth:regurgitate': {'players': []}}), 1, F, 2)
        self.assertEqual(alive(g), {A, B, C, D, E, G})
        g = play(table(seven('Pacifist', 'Assassin', 'Shabaloth'), {2: {G: kills(A, B)}, 3: {G: kills(A, B)}},
                       {'Shabaloth:regurgitate': {'players': []}}), 1, F, 2, 3)
        self.assertEqual(alive(g), {C, D, E, G})

    def test_chambermaid_counts_who_woke(self):
        g = play(table(seven('Chambermaid', 'Assassin', 'Pukka'), {1: {A: kills(B, G), G: kills(C)}, 2: {A: kills(D, F), G: kills(C)}}), 1, 2)
        self.assertIn(f'of {B} and {G}, 2 woke', heard(g, A))   # the Courtier (unused) and the Pukka
        self.assertIn(f'of {D} and {F}, 1 woke', heard(g, A))   # the Minstrel never wakes; the Assassin does


class OutsiderAndMinionTests(unittest.TestCase):
    def test_goon_makes_the_demon_drunk_and_turns_evil(self):
        chars = ['Goon', 'Courtier', 'Professor', 'Minstrel', 'Pacifist', 'Fool', 'Assassin', 'Zombuul']
        g = play(table(chars, {2: {H: kills(A)}}), 1, 2)
        self.assertEqual(len(alive(g)), 8)
        self.assertTrue(g.g[A].evil)
        self.assertIn('You are now EVIL', heard(g, A))

    def test_tinker_can_die(self):
        chars = ['Tinker', 'Courtier', 'Professor', 'Minstrel', 'Pacifist', 'Fool', 'Assassin', 'Po']
        g = play(table(chars, decisions={'Tinker:Alex': {'yes': True}}), 1)
        self.assertNotIn(A, alive(g))

    def test_moonchild_and_godfather(self):
        chars = ['Moonchild', 'Courtier', 'Professor', 'Minstrel', 'Fool', 'Godfather', 'Po']
        g = play(table(chars, {2: {F: kills(C), G: kills()}}, claims={A: B}), 1, A, 2)
        self.assertIn('the Outsiders in play are: Moonchild', heard(g, F))
        self.assertEqual(len(asked(g, F, 2)), 1)        # an Outsider died today
        self.assertEqual(alive(g), {D, E, F, G})        # the Moonchild's good choice and the Godfather's kill
        self.assertTrue([e for e in g.events if e['kind'] == 'moonchild'])

    def test_a_false_moonchild_claim_does_nothing(self):
        g = play(table(seven('Pacifist', 'Assassin', 'Po'), {2: {G: kills()}}, {'Pacifist:Blair': {'yes': False}},
                       claims={B: C}), 1, B, 2)
        self.assertEqual(alive(g), {A, C, D, E, F, G})
        self.assertEqual(asked(g, F, 2)[0].optional, True)

    def test_mastermind_plays_one_more_day(self):
        for executed, winner in ((A, 'evil'), (F, 'good')):
            g = play(table(seven('Fool', 'Mastermind', 'Po')), 1, G)
            self.assertIsNone(g.g.winner)

            async def extra_day(g=g, executed=executed):
                await g.night(2)
                g.execute(executed)
            run(extra_day())
            self.assertEqual(g.g.winner, winner, executed)

    def test_mastermind_day_without_an_execution_is_a_good_win(self):
        g = play(table(seven('Fool', 'Mastermind', 'Po')), 1, G)

        async def extra_day():
            await g.night(2)
            await g.daytime(2)
        run(extra_day())
        self.assertEqual(g.g.winner, 'good')


class EngineTests(unittest.TestCase):
    def test_random_games_finish_at_every_table_size(self):
        done = 0
        for seed in range(66):
            names = ALL_NAMES[:5 + seed % 11]
            rng = random.Random(seed)
            g = BMRGame({n: RandomSeat(n, random.Random(rng.random()), names) for n in names},
                        ScriptedStoryteller(random.Random(seed)), names=names, seed=seed, max_days=15, probes=False,
                        demon=BMR.demons[seed % 4])
            result = run(g.run())
            self.assertFalse(result['errors'], result['errors'])
            self.assertEqual(result['script'], 'bmr')
            done += result['winner'] is not None
        self.assertGreater(done, 40)


if __name__ == '__main__':
    unittest.main()
