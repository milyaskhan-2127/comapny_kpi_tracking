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

print("\n== HTTP probes (site productix-c.local via gunicorn :8000) ==")
urls = [
    "/assets/productix_recipe/css/productix.css",
    "/assets/productix_kpi/kpi_tracking/doctype/kpi_definition/kpi_definition.js",
    "/assets/productix_instruction/instruction_room/doctype/instruction_message/instruction_message.js",
    "/assets/productix_recipe/recipe_management/doctype/recipe/recipe.js",
    "/assets/productix_core/js/productix_core.js",
    "/app/productix-recipe",
    "/app/kpi-tracking",
    "/app/instruction-room",
]
for u in urls:
    req = urllib.request.Request(
        "http://localhost:8000" + u,
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
