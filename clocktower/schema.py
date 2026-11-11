"""One fixed output schema for every player decision.

Every decision uses the same schema, so it never changes the request prefix; the
prompt says which fields matter and the engine validates the rest.
"""


def _obj(props):
    return {'type': 'object', 'properties': props, 'required': list(props), 'additionalProperties': False}


def _nullable(schema):
    return {'anyOf': [schema, {'type': 'null'}]}


def player_schema(names, script='tb'):
    name = {'type': 'string', 'enum': list(names)}
    if script == 'bmr':  # no Slayer; the Courtier and the Gambler name a character
        from .characters import BMR
        return _obj({
            'say': {'type': 'string'},
            'whispers': {'type': 'array', 'items': _obj({'to': {'type': 'array', 'items': name}, 'text': {'type': 'string'}})},
            'nominate': _nullable(name),
            'vote': _nullable({'type': 'boolean'}),
            'targets': {'type': 'array', 'items': name},
            'character': _nullable({'type': 'string', 'enum': list(BMR.all)}),
        })
    return _obj({
        'say': {'type': 'string'},
        'whispers': {'type': 'array', 'items': _obj({'to': {'type': 'array', 'items': name}, 'text': {'type': 'string'}})},
        'nominate': _nullable(name),
        'vote': _nullable({'type': 'boolean'}),
        'targets': {'type': 'array', 'items': name},
        'slayer_shot': _nullable(name),
    })
