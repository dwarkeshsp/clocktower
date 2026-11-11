"""Turn game events into the text each viewer sees.

Viewers: a player name, 'storyteller', or 'omniscient' (the replay transcript).
Visibility ('to'): 'public', a list of player names, 'st' (Storyteller only) or
'audit' (transcript only). Whispers go to their participants only (the Storyteller
also sees them). Games recorded before whispers became private have public whisper
events: there non-participants see who whispered to whom, but not the words.
"""


def visible(ev, viewer):
    to = ev['to']
    if viewer == 'omniscient': return True
    if to == 'public': return True
    if to == 'audit': return False
    if to == 'st': return viewer == 'storyteller'
    if viewer == 'storyteller' and ev['kind'] == 'whisper': return True
    return viewer in to


def _name(n, viewer, dead=()):
    s = n
    if n == viewer: s += ' (you)'
    elif n in dead: s += ' (dead)'
    return s


def render(ev, viewer, dead=()):
    """Text for this viewer, or None. `dead` is the set of dead players at emit time."""
    if not visible(ev, viewer):
        return None
    k, d = ev['kind'], ev['data']
    nm = lambda n: _name(n, viewer, dead)
    if k in ('intro', 'info', 'notice', 'text', 'st_note'):
        return d['text']
    if k == 'header':
        return f"\n— {d['text']} —"
    if k == 'dawn':
        deaths = d['deaths']
        s = d.get('narration') or ''
        tail = (f"Died in the night: {', '.join(deaths)}." if deaths else 'Nobody died in the night.')
        if d.get('risen'):
            tail += f" Back from the dead: {', '.join(d['risen'])}."
        return (s + ' ' if s else '') + tail
    if k == 'say':
        return f"{nm(d['speaker'])}: {d['text']}"
    if k == 'whisper':
        to = ', '.join(nm(x) for x in d['to'])
        if viewer in ('storyteller', 'omniscient') or viewer == d['from'] or viewer in d['to']:
            return f"[whisper] {nm(d['from'])} → {to}: {d['text']}"
        return f"[{d['from']} whispered to {', '.join(d['to'])}]"
    if k == 'whisper_log':
        sent = ' · '.join(f"{nm(p)} → {' and '.join(nm(x) for x in to) if to else 'no one'}" for p, to in d['sent'].items())
        return f"Who whispered to whom in private time {d['beat']}: {sent}"
    if k == 'slayer':
        head = f"{nm(d['shooter'])} claims the Slayer's power and shoots at {d['target']}."
        return head + (f" {d['target']} dies!" if d['died'] else ' Nothing happens.')
    if k == 'nominations_open':
        return 'The Storyteller opens nominations.'
    if k == 'nomination':
        return f"{nm(d['nominator'])} nominates {d['nominee']}: {d['text']}" if d.get('text') else f"{nm(d['nominator'])} nominates {d['nominee']}."
    if k == 'virgin':
        return f"{d['nominator']} is executed immediately! The day ends."
    if k == 'defense':
        return f"{nm(d['nominee'])} (defense): {d['text']}" if d['text'] else f"{nm(d['nominee'])} says nothing in their defense."
    if k == 'vote':
        ghost = ' (spending their ghost vote)' if d.get('ghost') else ''
        remark = f" — {d['text']}" if d.get('text') else ''
        return f"{nm(d['voter'])} votes {'YES' if d['yes'] else 'no'}{ghost}{remark}"
    if k == 'vote_result':
        s = f"{d['nominee']} received {d['votes']} vote{'s' if d['votes'] != 1 else ''} ({d['needed']} needed)."
        return s + {'block': f" {d['nominee']} is about to be executed.",
                    'tie': ' That ties the leader, so nobody is about to be executed.',
                    'short': ''}[d['outcome']]
    if k == 'execution' and d.get('survived'):
        return f"{d['player']} is executed, but does not die."
    if k == 'moonchild':
        return f"{nm(d['player'])}, now dead, makes the Moonchild's choice and points at {d['target']}."
    if k == 'execution':
        return f"{d['player']} is executed." + ('' if d['died'] else ' (They were already dead.)')
    if k == 'no_execution':
        return 'Nobody is executed today.'
    if k == 'game_over':
        return f"GAME OVER — {d['winner'].upper()} wins. {d['reason']}"
    if k == 'st_choice':
        return f"[storyteller] {d['id']} → {d['value']}{'' if d['valid'] else ' (INVALID; default used)'}"
    if k == 'night_choice':
        return f"[night] {d['player']} ({d['role']}) chose {', '.join(d['targets']) or 'nobody'}"
    if k == 'setup':
        lines = ['Setup:']
        for i, seat in enumerate(d['seats'], start=1):
            tag = f" [thinks they are the {seat['shown']}]" if seat['shown'] != seat['character'] else ''
            tag += " [Fortune Teller's red herring]" if seat['name'] == d.get('red_herring') else ''
            lines.append(f"{i}. {seat['name']}: {seat['character']}{tag}")
        return '\n'.join(lines + [f"Demon bluffs: {', '.join(d['bluffs'])}"])
    if k == 'death':
        return f"[{d['player']} dies: {d.get('cause', '')}]"
    if k == 'becomes':
        return f"[{d['player']} is now the {d['character']}]"
    if k == 'thinking':
        return '\n'.join('    > ' + line for line in f"💭 {d['player']}: {d['text']}".split('\n'))
    return f"[{k}] {d}"
