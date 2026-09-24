#!/usr/bin/env python3
"""Retirement audit helper: static asset resolution + legacy images probe.
Run inside backend: env/bin/python /tmp/asset_probe.py
"""
import json
import os
import urllib.request
from pathlib import Path

print("== legacy public tree ==")
pub = Path("/home/frappe/frappe-bench/apps/productix/productix/public")
if not pub.exists():
    print("  RETIRED: apps/productix removed (tag pre-legacy-retirement); "
          "no legacy assets to probe")
else:
    for p in sorted(pub.rglob("*")):
        rel = p.relative_to(pub)
        kind = "DIR " if p.is_dir() else f"{p.stat().st_size:>7}B"
        print(f"  {kind} {rel}")

print("\n== sites/assets symlinks ==")
for p in sorted(Path("/home/frappe/frappe-bench/sites/assets").iterdir()):
    print(f"  {p.name} -> {'LINK->' + os.readlink(p) if p.is_symlink() else ('dir' if p.is_dir() else 'file')}")

print("\n== assets.json apps ==")
try:
    data = json.loads(Path("/home/frappe/frappe-bench/sites/assets/assets.json").read_text())
    print("  " + ", ".join(sorted(data)))
except Exception as e:
    print(f"  read fail: {e}")

print("\n== HTTP probes ==")
# /assets/* must be probed through nginx (frontend:8080): gunicorn does not
# serve symlinked public assets (tests/README.md §5). doctype_js hook targets
# are served public-stripped: <app>/public/js/custom_scripts/<file> ->
# /assets/<app>/js/custom_scripts/<file> (the module-tree doctype js paths
# return 404 for every app, including erpnext — framework characteristic).
# /app/* stays on gunicorn :8000 with an explicit site header (site-scoped).
urls = [
    ("http://frontend:8080", "/assets/productix_recipe/css/productix.css"),
    ("http://frontend:8080", "/assets/productix_core/js/productix_core.js"),
    ("http://frontend:8080", "/assets/productix_kpi/js/custom_scripts/kpi_user_scripts.js"),
    ("http://frontend:8080", "/assets/productix_recipe/js/custom_scripts/recipe_doctype_scripts.js"),
    ("http://localhost:8000", "/app/productix-recipe"),
    ("http://localhost:8000", "/app/kpi-tracking"),
    ("http://localhost:8000", "/app/instruction-room"),
]
for base, u in urls:
    req = urllib.request.Request(
        base + u,
        headers={"X-Frappe-Site-Name": "productix-c.local"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            body = r.read(200)
            print(f"  {r.status} {u}  ({len(body)}B peek)")
    except urllib.error.HTTPError as e:
        print(f"  {e.code} {u}")
    except Exception as e:
        print(f"  ERR {u}: {e}")
