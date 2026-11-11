"""Seats and the Storyteller.

A seat receives the text of everything it saw since its last turn plus a prompt,
and returns an action dict (the JSON schema in schema.py). Model seats, random
seats (for tests) and human seats all implement the same `act`.
"""
from __future__ import annotations
import asyncio
import random
import time
from dataclasses import dataclass, field

from .llm import Reply


@dataclass
class Request:
    kind: str                   # night | ravenkeeper | beat | nominate | defense | comment | vote | death
    prompt: str
    day: int
    beat: int | None = None
    n_targets: int = 0          # night choices
    options: list = field(default_factory=list)   # legal targets / nominees
    alive: bool = True
    mode: str = ''              # 'private' (whispers only) or 'public' (speech only)
    optional: bool = False      # a night choice the player may decline (no targets)
    characters: list = field(default_factory=list)  # legal values of `character`, when one is asked for


class ModelSeat:
    def __init__(self, conversation):
        self.conversation = conversation

    async def act(self, text, request: Request) -> Reply:
        return await self.conversation.send(text, {'kind': request.kind, 'day': request.day, 'beat': request.beat})

    async def probe(self, text, meta) -> Reply:
        """An out-of-game question on a fork of the conversation (see probe.py)."""
        return await self.conversation.send(text, {'kind': 'probe', **meta}, commit=False)


LINES = ['I have info, will share soon.', 'Who wants to claim first?', 'I trust Alex for now.',
         'That claim sounds off to me.', 'Let us not rush an execution.', 'I think we should nominate today.']


class RandomSeat:
    """Plays legal random moves. For tests only."""

    def __init__(self, name, rng: random.Random, names):
        self.name, self.rng, self.names = name, rng, names

    async def act(self, text, request: Request) -> Reply:
        r, others = self.rng, [n for n in self.names if n != self.name]
        a = {'say': '', 'whispers': [], 'nominate': None, 'vote': None, 'targets': [],
             'slayer_shot': None}
        if request.kind in ('night', 'ravenkeeper'):
            a['targets'] = r.sample(request.options, min(request.n_targets, len(request.options)))
            if request.optional and r.random() < 0.4:
                a['targets'] = []
            if request.characters and not (request.optional and r.random() < 0.4):
                a['character'] = r.choice(request.characters)
        elif request.kind == 'death':  # the Moonchild's public choice, which anyone may claim to make
            if request.options and r.random() < 0.3:
                a['targets'] = [r.choice(request.options)]
        elif request.kind == 'beat':
            if r.random() < 0.5: a['say'] = r.choice(LINES)
            if r.random() < 0.3: a['whispers'] = [{'to': [r.choice(others)], 'text': 'psst, what are you?'}]
            if r.random() < 0.03: a['slayer_shot'] = r.choice(others)
        elif request.kind == 'nominate':
            if request.options and r.random() < 0.4:
                a['nominate'] = r.choice(request.options)
                a['say'] = 'You seem suspicious.'
        elif request.kind == 'comment':
            if r.random() < 0.3: a['say'] = r.choice(LINES)
        elif request.kind == 'defense':
            a['say'] = 'I am good, I promise.'
        elif request.kind == 'vote':
            a['vote'] = r.random() < 0.5
        return Reply(a)


class ScriptedStoryteller:
    """Makes every Storyteller choice by the policy in state.py (what an experienced human
    Storyteller would usually do, with some randomness). No API calls."""

    def __init__(self, rng: random.Random):
        self.rng = rng

    def choose(self, choice):
        return choice.options(self.rng)


class HumanSeat:
    """Waits for a move submitted through the web UI (see web.py). `timeout` (seconds, optional) passes
    the turn when nobody answers in time, the way a seat that says nothing passes; so does `away()`
    turning true (the player's page has stopped checking in), so a closed tab never stalls the table."""

    def __init__(self, name, timeout=None, away=None):
        self.name, self.timeout, self.away = name, timeout, away
        self.pending: Request | None = None
        self.future: asyncio.Future | None = None
        self.loop: asyncio.AbstractEventLoop | None = None
        self.turn = 0               # increments per request, so a late submit can't answer the next one
        self.deadline = None        # epoch seconds, when there is a timeout

    async def act(self, text, request: Request) -> Reply:
        self.loop = asyncio.get_running_loop()
        self.future = self.loop.create_future()
        self.turn += 1
        self.deadline = time.time() + self.timeout if self.timeout else None
        self.pending = request
        try:
            while not (self.away and self.away()):  # someone already gone passes at once
                wait = 2 if self.deadline is None else max(0, min(2, self.deadline - time.time()))
                try:
                    return Reply(await asyncio.wait_for(asyncio.shield(self.future), wait))
                except asyncio.TimeoutError:
                    if self.deadline and time.time() >= self.deadline:
                        return Reply({})
            return Reply({})
        finally:
            self.pending, self.future, self.deadline = None, None, None

    def submit(self, action: dict, turn=None):
        """Called from the web server thread. Returns False if nothing (or another turn) is pending."""
        future, loop = self.future, self.loop
        if not (future and loop) or (turn is not None and turn != self.turn):
            return False
        loop.call_soon_threadsafe(lambda: future.done() or future.set_result(action))
        return True
