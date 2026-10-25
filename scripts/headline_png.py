"""Headline chart: Elo rating of each 2026 model against its release date, with the trend.

python scripts/headline_png.py  ->  docs/charts/headline.png (reads docs/plans/f2-ratings.json)
"""
import datetime, json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib import font_manager
import matplotlib.patheffects as pe
import numpy as np

for f in font_manager.findSystemFonts():
    if '/inter/' in f.lower():
        font_manager.fontManager.addfont(f)
plt.rcParams['font.family'] = 'Inter'

NAMES = {'claude-opus-4-6': 'Opus 4.6', 'gpt-5.4': 'GPT-5.4', 'claude-opus-4-7': 'Opus 4.7', 'gpt-5.5': 'GPT-5.5',
         'claude-opus-4-8': 'Opus 4.8', 'claude-fable-5': 'Fable 5', 'gpt-5.6-sol': 'GPT-5.6 Sol',
         'claude-fable-5-1': 'Fable 5.1', 'gpt-6-astra': 'GPT-6 Astra', 'claude-opus-5-5': 'Opus 5.5',
         'gpt-6.1-sol': 'GPT-6.1 Sol'}
# label placement (dx days, dy Elo, horizontal alignment), chosen by eye so nothing collides
PLACE = {'Opus 4.6': (5, 0, 'left'), 'GPT-5.4': (5, 0, 'left'), 'Opus 4.7': (-5, 0, 'right'),
         'GPT-5.5': (5, 0, 'left'), 'Opus 4.8': (5, 0, 'left'), 'Fable 5': (-5, 0, 'right'),
         'GPT-5.6 Sol': (0, 80, 'center'), 'Fable 5.1': (-5, 0, 'right'), 'GPT-6 Astra': (-5, 0, 'right'),
         'Opus 5.5': (5, 0, 'left'), 'GPT-6.1 Sol': (5, 0, 'left')}
COLOR = {'OpenAI': '#2b6cb0', 'Anthropic': '#d97757'}
INK, MUTED, GRID = '#1a1a1a', '#6b6b6b', '#e6e6e3'

d = json.load(open('docs/plans/f2-ratings.json'))
slope, (lo, hi) = d['trend_per_year']['c']
ms = d['models']
day = lambda m: datetime.date.fromisoformat(m['date'])
x = np.array([mdates.date2num(day(m)) for m in ms])
y = np.array([m['combined'] for m in ms])

fig, ax = plt.subplots(figsize=(10, 6.6), dpi=200)
fig.patch.set_facecolor('#fcfcfb'); ax.set_facecolor('#fcfcfb')

# trend (least squares on the points, as in scripts/ratings2026.py)
b, a = np.polyfit(x, y, 1)
tx = np.array([x.min() - 12, x.max() + 12])
ax.plot(tx, a + b * tx, color=MUTED, lw=1.6, ls=(0, (5, 4)), zorder=1)
lx = mdates.date2num(datetime.date(2026, 8, 3))
ax.text(lx, a + b * lx - 70, f'+{slope} Elo\nper year', ha='left', va='top', linespacing=1.3,
        color=INK, fontsize=12, fontweight='semibold')

for m, xi, yi in zip(ms, x, y):
    c = COLOR[m['lab']]
    ax.plot([xi, xi], m['c90'], color=c, alpha=0.28, lw=2.2, solid_capstyle='round', zorder=2)
    ax.scatter(xi, yi, s=90, color=c, edgecolor='#fcfcfb', linewidth=2, zorder=3)
    name = NAMES[m['id']]
    dx, dy, ha = PLACE[name]
    ax.text(xi + dx, yi + dy, name, ha=ha, va='center', fontsize=11, color=INK, zorder=4,
            path_effects=[pe.withStroke(linewidth=4, foreground='#fcfcfb')])

ax.set_ylim(1050, 2010)
ax.set_xlim(mdates.date2num(datetime.date(2026, 1, 20)), mdates.date2num(datetime.date(2026, 10, 31)))
ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=range(2, 11)))
ax.xaxis.set_major_formatter(mdates.DateFormatter('%b'))
ax.yaxis.set_major_locator(plt.MultipleLocator(200))
ax.grid(axis='y', color=GRID, lw=1); ax.set_axisbelow(True)
for s in ('top', 'right', 'left'):
    ax.spines[s].set_visible(False)
ax.spines['bottom'].set_color('#bdbdb8')
ax.tick_params(colors=MUTED, labelsize=11, length=0, pad=8)
ax.set_ylabel('Elo rating', color=MUTED, fontsize=11, labelpad=10)

# legend as coloured text in the corner
ax.text(0.015, 0.97, '●  OpenAI', transform=ax.transAxes, color=COLOR['OpenAI'], fontsize=12, va='top', fontweight='semibold')
ax.text(0.015, 0.91, '●  Anthropic', transform=ax.transAxes, color=COLOR['Anthropic'], fontsize=12, va='top', fontweight='semibold')

fig.text(0.06, 0.965, f'AI models are getting better at social deduction by ~{round(slope, -1):.0f} Elo a year',
         fontsize=19, fontweight='bold', color=INK, va='top')
fig.text(0.06, 0.905, f'Rating of each 2026 model at Blood on the Clocktower, by release date. One model plays the good team\n'
         f'(find the Demon), another the evil team (lie and survive). {d["games"]} games. 400 points ≈ 10-to-1 win odds.',
         fontsize=11.5, color=MUTED, va='top', linespacing=1.45)
fig.text(0.06, 0.025, f'Bars: 90% CI per model. Dashed: least-squares trend, 90% CI {lo}–{hi} Elo/year (bootstrap over game pairs). '
         f'1500 = mean of these 11 models.', fontsize=9, color=MUTED)
fig.subplots_adjust(left=0.08, right=0.97, top=0.80, bottom=0.13)
fig.savefig('docs/charts/headline.png', facecolor=fig.get_facecolor())
