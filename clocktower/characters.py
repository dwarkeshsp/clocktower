"""Characters by script: types, ability text and (for Trouble Brewing) night order."""

TOWNSFOLK = ['Washerwoman', 'Librarian', 'Investigator', 'Chef', 'Empath', 'Fortune Teller',
             'Undertaker', 'Monk', 'Ravenkeeper', 'Virgin', 'Slayer', 'Soldier', 'Mayor']
OUTSIDERS = ['Butler', 'Drunk', 'Recluse', 'Saint']
MINIONS = ['Poisoner', 'Spy', 'Scarlet Woman', 'Baron']
DEMONS = ['Imp']
ALL = TOWNSFOLK + OUTSIDERS + MINIONS + DEMONS
GOOD = TOWNSFOLK + OUTSIDERS
# Official Trouble Brewing setup by player count: (Townsfolk, Outsiders, Minions), plus one Demon.
# The Baron turns two Townsfolk into Outsiders.
SETUPS = {5: (3, 0, 1), 6: (3, 1, 1), 7: (5, 0, 1), 8: (5, 1, 1), 9: (5, 2, 1), 10: (7, 0, 2), 11: (7, 1, 2),
          12: (7, 2, 2), 13: (9, 0, 3), 14: (9, 1, 3), 15: (9, 2, 3)}
INFO_ROLES = {'Washerwoman', 'Librarian', 'Investigator', 'Chef', 'Empath', 'Fortune Teller', 'Undertaker', 'Ravenkeeper'}

ABILITY = {
    'Washerwoman': 'You start knowing that 1 of 2 players is a particular Townsfolk.',
    'Librarian': 'You start knowing that 1 of 2 players is a particular Outsider. (Or that zero are in play.)',
    'Investigator': 'You start knowing that 1 of 2 players is a particular Minion.',
    'Chef': 'You start knowing how many pairs of evil players there are (evil players sitting next to each other).',
    'Empath': 'Each night, you learn how many of your 2 alive neighbours are evil.',
    'Fortune Teller': 'Each night, choose 2 players: you learn if either is a Demon. '
                      'There is a good player that registers as a Demon to you.',
    'Undertaker': 'Each night*, you learn which character died by execution today.',
    'Monk': 'Each night*, choose a player (not yourself): they are safe from the Demon tonight.',
    'Ravenkeeper': 'If you die at night, you are woken to choose a player: you learn their character.',
    'Virgin': 'The 1st time you are nominated, if the nominator is a Townsfolk, they are executed immediately.',
    'Slayer': 'Once per game, during the day, publicly choose a player: if they are the Demon, they die.',
    'Soldier': 'You are safe from the Demon.',
    'Mayor': 'If only 3 players live & no execution occurs, your team wins. '
             'If you die at night, another player might die instead.',
    'Butler': 'Each night, choose a player (not yourself): tomorrow, you may only vote if they are voting too.',
    'Drunk': 'You do not know you are the Drunk. You think you are a Townsfolk character, but you are not.',
    'Recluse': 'You might register as evil & as a Minion or Demon, even if dead.',
    'Saint': 'If you die by execution, your team loses.',
    'Poisoner': 'Each night, choose a player: they are poisoned tonight and tomorrow day.',
    'Spy': 'Each night, you see the Grimoire. You might register as good & as a Townsfolk or Outsider, even if dead.',
    'Scarlet Woman': 'If there are 5 or more players alive & the Demon dies, you become the Demon.',
    'Baron': 'There are extra Outsiders in play. [+2 Outsiders]',
    'Imp': 'Each night*, choose a player: they die. If you kill yourself this way, a Minion becomes the Imp.',
}

# Night order. "*" abilities (Monk, Imp, Undertaker) do not act on the first night.
FIRST_NIGHT = ['Poisoner', 'Washerwoman', 'Librarian', 'Investigator', 'Chef', 'Empath',
               'Fortune Teller', 'Butler', 'Spy']
OTHER_NIGHTS = ['Poisoner', 'Monk', 'Scarlet Woman', 'Imp', 'Ravenkeeper', 'Empath',
                'Fortune Teller', 'Undertaker', 'Butler', 'Spy']


class Script:
    """A script: its characters by type. Trouble Brewing is the rated one; Bad Moon Rising is experimental
    (clocktower/bmr.py)."""

    def __init__(self, key, name, townsfolk, outsiders, minions, demons):
        self.key, self.name = key, name
        self.townsfolk, self.outsiders, self.minions, self.demons = townsfolk, outsiders, minions, demons
        self.good = townsfolk + outsiders
        self.all = self.good + minions + demons


# Bad Moon Rising, without the Gossip: its ability turns on whether a free-text public statement is
# true, which a scripted Storyteller cannot judge. Twelve Townsfolk are more than any table size needs.
BMR_TOWNSFOLK = ['Grandmother', 'Sailor', 'Chambermaid', 'Exorcist', 'Innkeeper', 'Gambler', 'Courtier',
                 'Professor', 'Minstrel', 'Tea Lady', 'Pacifist', 'Fool']
BMR_OUTSIDERS = ['Tinker', 'Moonchild', 'Goon', 'Lunatic']
BMR_MINIONS = ['Godfather', "Devil's Advocate", 'Assassin', 'Mastermind']
BMR_DEMONS = ['Zombuul', 'Pukka', 'Shabaloth', 'Po']

ABILITY.update({
    'Grandmother': 'You start knowing a good player & their character. If the Demon kills them, you die too.',
    'Sailor': "Each night, choose an alive player: either you or they are drunk until dusk. You can't die.",
    'Chambermaid': 'Each night, choose 2 alive players (not yourself): you learn how many woke tonight due to '
                   'their ability.',
    'Exorcist': "Each night*, choose a player (different to last night): the Demon, if chosen, learns who you "
                "are then doesn't wake tonight.",
    'Innkeeper': "Each night*, choose 2 players: they can't die tonight, but 1 is drunk until dusk.",
    'Gambler': 'Each night*, choose a player & guess their character: if you guess wrong, you die.',
    'Courtier': 'Once per game, at night, choose a character: they are drunk for 3 nights & 3 days.',
    'Professor': 'Once per game, at night*, choose a dead player: if they are a Townsfolk, they are resurrected.',
    'Minstrel': 'When a Minion dies by execution, all other players are drunk until dusk tomorrow.',
    'Tea Lady': "If both your alive neighbours are good, they can't die.",
    'Pacifist': 'Executed good players might not die.',
    'Fool': "The 1st time you die, you don't.",
    'Tinker': 'You might die at any time.',
    'Moonchild': 'When you learn that you died, publicly choose 1 alive player. Tonight, if it was a good '
                 'player, they die.',
    'Goon': 'Each night, the 1st player to choose you with their ability is drunk until dusk. You become their '
            'alignment.',
    'Lunatic': 'You think you are a Demon, but you are not. The Demon knows who you are & who you choose at night.',
    'Godfather': 'You start knowing which Outsiders are in play. If 1 died today, choose a player tonight: they '
                 'die. [-1 or +1 Outsider]',
    "Devil's Advocate": "Each night, choose a living player (different to last night): if executed tomorrow, "
                        "they don't die.",
    'Assassin': 'Once per game, at night*, choose a player: they die, even if for some reason they could not.',
    'Mastermind': 'If the Demon dies by execution (ending the game), play for 1 more day. If a player is then '
                  'executed, their team loses.',
    'Zombuul': 'Each night*, if no-one died today, choose a player: they die. The 1st time you die, you live '
               'but register as dead.',
    'Pukka': 'Each night, choose a player: they are poisoned. The previously poisoned player dies then becomes '
             'healthy.',
    'Shabaloth': 'Each night*, choose 2 players: they die. A dead player you chose last night might be '
                 'regurgitated (brought back to life).',
    'Po': 'Each night*, you may choose a player: they die. If your last choice was no-one, choose 3 players '
          'tonight.',
})

TB = Script('tb', 'Trouble Brewing', TOWNSFOLK, OUTSIDERS, MINIONS, DEMONS)
BMR = Script('bmr', 'Bad Moon Rising', BMR_TOWNSFOLK, BMR_OUTSIDERS, BMR_MINIONS, BMR_DEMONS)
SCRIPTS = {'tb': TB, 'bmr': BMR}


def kind(character):
    for s in SCRIPTS.values():
        if character in s.townsfolk: return 'Townsfolk'
        if character in s.outsiders: return 'Outsider'
        if character in s.minions: return 'Minion'
        if character in s.demons: return 'Demon'
    raise KeyError(character)


def is_evil_character(character):
    return kind(character) in ('Minion', 'Demon')


def card(character):
    team = 'evil' if is_evil_character(character) else 'good'
    return f'{character} ({kind(character)}, {team} team): {ABILITY[character]}'


def script_text(script=None):
    """The character sheet every player and the Storyteller sees."""
    s = script or TB
    lines = []
    for title, group in [('Townsfolk (good)', s.townsfolk), ('Outsiders (good)', s.outsiders),
                         ('Minions (evil)', s.minions), ('Demon (evil)' if len(s.demons) == 1 else 'Demons (evil)', s.demons)]:
        lines.append(f'{title}:')
        lines += [f'- {c}: {ABILITY[c]}' for c in group]
    lines.append('(* = not on the first night)')
    return '\n'.join(lines)
