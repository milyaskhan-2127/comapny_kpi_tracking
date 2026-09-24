# Compare the Recipe workspace fixture entry against the LIVE workspace doc —
# raw python. Prints which fields differ / are absent on either side, so the
# module-dir rewrite can be proven zero-write on the next migrate.
# env/bin/python tests/_recipe_ws_analyze.py <site>
import json
import os
import sys

import frappe

site = sys.argv[1]
os.makedirs(os.path.join(os.path.expanduser("~"), "logs"), exist_ok=True)
for d in (
    os.path.join(os.path.abspath("sites"), site, "logs"),
    os.path.join(os.path.dirname(os.path.abspath("sites")), site, "logs"),
):
    os.makedirs(d, exist_ok=True)
frappe.init(site=site, sites_path=os.path.abspath("sites"))
frappe.connect()
frappe.set_user("Administrator")

FIXTURE = "apps/productix_recipe/productix_recipe/fixtures/workspace.json"
with open(FIXTURE, encoding="utf-8") as f:
    fixture = json.load(f)[0]
live = frappe.get_doc("Workspace", "Recipe Management").as_dict(no_nulls=False)

fk, lk = set(fixture), set(live)
only_fixture = sorted(fk - lk)
only_live = sorted(lk - fk)
differing = []
for k in sorted(fk & lk):
    a = json.dumps(fixture[k], sort_keys=True, default=str, ensure_ascii=False)
    b = json.dumps(live[k], sort_keys=True, default=str, ensure_ascii=False)
    if a != b:
        differing.append(k)


def normalize(value):
    """Drop system/metadata keys frappe adds to child rows at runtime so the
    semantic content (links/roles/shortcuts/charts/cards) can be compared."""
    if isinstance(value, dict):
        drop = {"creation", "modified", "modified_by", "owner", "idx", "parent", "docstatus"}
        return {k: normalize(v) for k, v in value.items() if k not in drop}
    if isinstance(value, list):
        return [normalize(v) for v in value]
    return value


children_normalized_equal = all(
    normalize(fixture[k]) == normalize(live[k]) for k in fixture
) and not (set(fixture) ^ set(live)) - {"creation", "idx", "modified_by", "owner"}

print(
    "RECIPE_WS_ANALYZE",
    json.dumps(
        {
            "site": site,
            "modified_values_equal": str(fixture.get("modified")) == str(live.get("modified")),
            "fixture_modified": fixture.get("modified"),
            "live_modified": str(live.get("modified")),
            "differing_common_fields": differing,
            "only_in_fixture": only_fixture,
            "only_in_live": only_live,
            "normalized_equal_modulo_system_fields": children_normalized_equal,
        },
        ensure_ascii=False,
    ),
)
