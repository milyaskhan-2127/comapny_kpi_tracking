#!/usr/bin/env python
"""End-to-end asset verification through nginx (frontend:8080).

Reproducible evidence harness: asserts that every stylesheet/script the
served pages reference (login page, productix app_include assets, desk
framework bundles) returns HTTP 200 via the reverse proxy.
"""
import json
import re
import urllib.request

BASE = "http://frontend:8080"

productix_assets = [
    "/assets/productix_core/js/productix_core.js",
    "/assets/productix_recipe/css/productix.css",
    "/assets/productix_recipe/js/productix.js",
    "/assets/productix_kpi/css/kpi_tracking.css",
    "/assets/productix_kpi/js/productix.js",
]

with open("/home/frappe/frappe-bench/sites/assets/assets.json") as f:
    am = json.load(f)
desk_stems = [
    "desk.bundle.css", "desk.bundle.js", "erpnext.bundle.js",
    "controls.bundle.js", "form.bundle.js", "list.bundle.js",
    "report.bundle.js", "erpnext-web.bundle.js", "erpnext-web.bundle.css",
]
bundle_urls = sorted({am[s] for s in desk_stems if s in am})

html = urllib.request.urlopen(f"{BASE}/", timeout=30).read().decode("utf-8", "replace")
login_urls = sorted(set(re.findall(r'(?:href|src)="(/assets/[^"]+)"', html)))

def check(urls, label):
    fails = []
    for u in urls:
        try:
            r = urllib.request.urlopen(BASE + u, timeout=20)
            size = len(r.read())
            print(f"{r.status} {u} ({size}B)")
            if r.status != 200:
                fails.append(u)
        except Exception as e:
            code = getattr(e, "code", None)
            print(f"{code} {u} ERROR {e}")
            fails.append(u)
    print(f"-- {label}: {'ALL OK' if not fails else str(fails)}")
    return fails

f1 = check(login_urls, "login page assets")
f2 = check(productix_assets, "productix source assets (app_include)")
f3 = check(bundle_urls, "desk framework bundles")
allf = f1 + f2 + f3
print("VERDICT:", "ALL ASSETS OK" if not allf else f"{len(allf)} FAILURES: {allf}")
raise SystemExit(1 if allf else 0)