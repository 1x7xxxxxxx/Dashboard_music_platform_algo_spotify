#!/usr/bin/env python3
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from build import expand           # noqa: E402
from style import CSS              # noqa: E402
from part1 import PART1            # noqa: E402
from part2 import PART2            # noqa: E402
from part3 import PART3            # noqa: E402
from part4 import PART4            # noqa: E402
from part5 import PART5            # noqa: E402
from part6 import PART6            # noqa: E402

body = "".join([PART1, PART2, PART3, PART4, PART5, PART6])
print("rendu des schémas mermaid…", flush=True)
body = expand(body)

html = f"""<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">
<title>streaMLytics — architecture et qualité des données</title>
<style>{CSS}</style></head><body>{body}</body></html>"""

out_html = HERE / "dossier.html"
out_html.write_text(html, encoding="utf-8")

from weasyprint import HTML        # noqa: E402
dest = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "dossier.pdf"
HTML(string=html, base_url=str(HERE)).write_pdf(dest)
print(f"✅ {dest}  ({dest.stat().st_size/1024:.0f} Ko)")
