# -*- coding: utf-8 -*-
# Generic site probe: registry vs cache vs entitlement rows vs installed apps.
# Usage: python3 probe_site.py <site> [outfile]
import frappe, json, sys
site = sys.argv[1]
OUT = sys.argv[2] if len(sys.argv) > 2 else "/tmp/probe_site.txt"
frappe.init(site=site, sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
lines = []
def w(s):
    lines.append(str(s))
w("=== INSTALLED APPS ===")
w(frappe.get_installed_apps())
w("\n=== REGISTRY cached get_registry ===")
from productix_core.modules.registry import get_registry, _load_registry, REGISTRY_CACHE_KEY, ENTITLEMENT_CACHE_KEY, _site_scoped
w(json.dumps(sorted(get_registry().keys())))
w("\n=== REDIS CACHE VALUES ===")
for k in (REGISTRY_CACHE_KEY, ENTITLEMENT_CACHE_KEY):
    sk = _site_scoped(k)
    try:
        v = frappe.cache.get_value(sk)
        w("REDIS %s: %s" % (sk, json.dumps(v) if v is not None else None))
    except Exception as e:
        w("REDIS %s ERR: %r" % (sk, e))
w("\n=== ENTITLEMENT MAP fresh ===")
from productix_core.modules.entitlement import get_entitlement_map, is_module_enabled, invalidate_entitlement_cache
invalidate_entitlement_cache()
w(json.dumps(get_entitlement_map(), indent=1))
w("\n=== is_module_enabled ===")
for key in ("core", "recipe", "kpi", "instruction"):
    w("%s: %s" % (key, is_module_enabled(key)))
w("\n=== PRODUCTIX SETTINGS child rows ===")
if frappe.db.exists("DocType", "Productix Settings"):
    doc = frappe.get_doc("Productix Settings")
    rows = [{"module_key": r.get("module_key"), "module_name": r.get("module_name"), "enabled": r.get("enabled")} for r in (doc.get("module_entitlements") or [])]
    w(json.dumps(rows, indent=1))
else:
    w("Productix Settings DocType missing")
with open(OUT, "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines))
print("wrote", OUT)