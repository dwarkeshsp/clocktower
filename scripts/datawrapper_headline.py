"""Build the headline chart (2026 ratings vs release date) in Datawrapper.

python scripts/datawrapper_headline.py [CHART_ID]   # needs DATAWRAPPER_API_TOKEN
Creates a chart (or updates CHART_ID), publishes it and saves a PNG next to the CSV.
"""
import json, os, sys, urllib.request

API = 'https://api.datawrapper.de/v3'
HERE = 'docs/charts/datawrapper'


def call(method, path, body=None, ctype='application/json', raw=False):
    data = body if isinstance(body, (bytes, type(None))) else json.dumps(body).encode()
    req = urllib.request.Request(API + path, data=data, method=method, headers={
        'Authorization': 'Bearer ' + os.environ['DATAWRAPPER_API_TOKEN'], 'Content-Type': ctype})
    with urllib.request.urlopen(req) as r:
        out = r.read()
    return out if raw else (json.loads(out) if out else None)


ratings = json.load(open('docs/plans/f2-ratings.json'))
slope, (lo, hi) = ratings['trend_per_year']['c']
chart = sys.argv[1] if len(sys.argv) > 1 else call('POST', '/charts', {'type': 'd3-scatter-plot', 'title': 'x'})['id']
print('chart', chart, flush=True)
call('PUT', f'/charts/{chart}/data', open(f'{HERE}/headline.csv', 'rb').read(), 'text/csv')
call('PATCH', f'/charts/{chart}', {
    'title': f'AI models are getting better at social deduction by ~{slope} Elo a year',
    'metadata': {
        'describe': {
            'intro': (f'Elo rating of each 2026 model in Blood on the Clocktower, where one model plays the good team '
                      f'(find the Demon) and another the evil team (lie and survive). {ratings["games"]} games; '
                      f'1500 = average of these 11 models.'),
            'source-name': 'Clocktower eval, Bradley–Terry fit over side-swapped game pairs',
            'byline': 'Dwarkesh Patel',
            'aria-description': 'Scatter plot of Elo rating against release date for 11 models; ratings rise over 2026.',
        },
        'annotate': {'notes': f'Line: least-squares trend, +{slope} Elo/year (90% CI {lo}–{hi}, bootstrap). '
                              f'Model ratings are ±60–110 Elo (90% CI). '
                              f'A 400-point gap means the stronger model wins about 10 games to 1.'},
        'axes': {'x': 'Released', 'y': 'Elo rating', 'color': 'Lab', 'labels': 'Model'},
        'visualize': {
            'x-grid': 'off', 'y-grid': 'on',
            'y-range': ['1100', '1950'], 'y-grid-format': '0',
            'x-range': ['', ''],
            'regression': True, 'regression-method': 'linear',
            'show-color-key': True,
            'color-category': {'map': {'Anthropic': '#d97757', 'OpenAI': '#3c6e9f'}},
            'fixed-size': 9, 'opacity': 1, 'outlines': True,
            'auto-labels': False, 'show-labels': True,
            'add-labels': [],
            'tooltip': {'body': '{{ Model }}: {{ elo_rating }} (90% CI {{ _90_ci_low }}–{{ _90_ci_high }}), {{ games }} games',
                        'title': '{{ Model }}', 'sticky': False, 'enabled': True},
        },
    }})
call('POST', f'/charts/{chart}/publish')
png = call('GET', f'/charts/{chart}/export/png?unit=px&width=720&plain=false&scale=2&borderWidth=20', raw=True)
open(f'{HERE}/headline.png', 'wb').write(png)
info = call('GET', f'/charts/{chart}')
print(chart, info.get('publicUrl'))
