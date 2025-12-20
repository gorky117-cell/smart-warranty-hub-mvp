# -*- coding: utf-8 -*-
from pathlib import Path
p = Path('templates/neo_dashboard.html')
lines = p.read_text(errors='ignore').splitlines()
out = []
for l in lines:
    if 'Enter your warranty number and tap' in l:
        out.append('      <div class="helper">Enter your warranty number and tap "Show my warranty".</div>')
    else:
        out.append(l)
p.write_text('\n'.join(out), encoding='utf-8')
