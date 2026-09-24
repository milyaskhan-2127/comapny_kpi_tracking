# Resolve the Recipe workspace fixture-vs-module-dir divergence:
# rewrite the module-dir workspace JSON as an exact deep copy of
# fixtures/workspace.json[0] (the fixture == live state, proven authoritative
# last writer during migrate). No live data/functionality changes: on the next
# migrate the module-dir sync imports this content first and the fixture sync
# re-imports the identical content last.
import json
import sys

FIXTURE = "apps/productix_recipe/productix_recipe/fixtures/workspace.json"
TARGET = (
    "apps/productix_recipe/productix_recipe/recipe_management/workspace/"
    "recipe_management/recipe_management.json"
)

with open(FIXTURE, encoding="utf-8") as f:
    fixture = json.load(f)
assert isinstance(fixture, list) and len(fixture) == 1, f"fixture shape: {type(fixture)}"
entry = fixture[0]
assert entry.get("doctype") == "Workspace", entry.get("doctype")
assert entry.get("name") == "Recipe Management", entry.get("name")

with open(TARGET, encoding="utf-8") as f:
    current = json.load(f)
if isinstance(current, list):
    print("TARGET_WAS_LIST (unexpected shape) — aborting")
    sys.exit(1)

# indent=1 matches frappe's module-dir export style (the file's current format)
with open(TARGET, "w", encoding="utf-8") as f:
    json.dump(entry, f, indent=1, ensure_ascii=False)
    f.write("\n")

with open(TARGET, encoding="utf-8") as f:
    written = json.load(f)
same = written == entry
print(
    "RECIPE_WS_RESOLVED",
    json.dumps(
        {
            "target": TARGET,
            "identical_to_fixture": same,
            "links": len(entry.get("links") or []),
            "shortcuts": len(entry.get("shortcuts") or []),
            "roles": len(entry.get("roles") or []),
        }
    ),
)
sys.exit(0 if same else 1)
