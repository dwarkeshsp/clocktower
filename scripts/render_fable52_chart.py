"""Render docs/charts/final-ratings-fable52.html with docs/plans/f6-ratings.json to a PNG (needs node + playwright):
    python scripts/render_fable52_chart.py docs/charts/clocktower-fable52-ratings.png
    python scripts/render_fable52_chart.py docs/charts/clocktower-fable52-detection-deception.png docs/charts/split-ratings-fable52.html"""
import json,sys,subprocess,pathlib
import tempfile; S=pathlib.Path(tempfile.mkdtemp())
t=open(sys.argv[2] if len(sys.argv)>2 else 'docs/charts/final-ratings-fable52.html').read().replace('__DATA__',open('docs/plans/f6-ratings.json').read())
(S/'chart.html').write_text(t)
js="""const {chromium}=require('playwright');(async()=>{const b=await chromium.launch();const p=await b.newPage({viewport:{width:1200,height:900},deviceScaleFactor:2});
await p.goto('file://%s');await p.evaluate(()=>document.fonts.ready);await (await p.$('.wrap')).screenshot({path:'%s'});await b.close()})()"""%(S/'chart.html',sys.argv[1])
subprocess.run(['node','-e',js],check=True)
