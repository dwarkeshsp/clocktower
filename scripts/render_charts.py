"""Render a static blog chart (a docs/charts/*.html template with __DATA__) from docs/plans/f2-ratings.json to a PNG.
Needs node with playwright and the Inter font.

    python scripts/render_charts.py docs/charts/clocktower-final-ratings.png
    python scripts/render_charts.py docs/charts/clocktower-detection-deception.png docs/charts/split-ratings.html
"""
import json,sys,subprocess,pathlib
import tempfile; S=pathlib.Path(tempfile.mkdtemp())
t=open(sys.argv[2] if len(sys.argv)>2 else 'docs/charts/final-ratings.html').read().replace('__DATA__',open('docs/plans/f2-ratings.json').read())
(S/'chart.html').write_text(t)
js="""const {chromium}=require('playwright');(async()=>{const b=await chromium.launch();const p=await b.newPage({viewport:{width:1200,height:900},deviceScaleFactor:2});
await p.goto('file://%s');await p.evaluate(()=>document.fonts.ready);await (await p.$('.wrap')).screenshot({path:'%s'});await b.close()})()"""%(S/'chart.html',sys.argv[1])
subprocess.run(['node','-e',js],check=True)
