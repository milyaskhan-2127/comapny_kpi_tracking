#!/usr/bin/env python3
"""
_manifest_discovery.py — shared, generic discovery for the productix validators.

There is deliberately **no hard-coded list of productix apps anywhere** in this
tooling: an app participates iff it ships a `productix_module.json` manifest —
the same rule the runtime registry uses (productix_core.modules.registry).
Adding a future app (e.g. `productix_manufacturing`) therefore requires no
validator edits.

Discovery rules
---------------
* `apps/<app>/<app>/productix_module.json` exists  -> productix module app
* `apps/productix_*` without that manifest         -> reported as an issue
  (a future module forgot its manifest, or the tree is incomplete)
* `apps/productix` (the retired monolithic app)    -> exempt: the legacy
  directory has no `productix_` prefix, so the validators never force a
  manifest onto it while it is being retained for the live legacy site.

Shared helpers: parse_modules_txt, scrub_module, parse_hooks (AST-based),
build_module_owner_map.
"""
import ast
import json
import os
import re

MANIFEST_NAME = "productix_module.json"
LEGACY_APP = "productix"
APP_PREFIX = "productix_"

# False positives that must be ignored wherever legacy `productix.…` refs are
# searched (shared by validate_dependencies' string + hooks scans):
#  - demo e-mail domains         productix.local
#  - asset bundle filenames      /assets/productix_kpi/js/productix.js
#  - migration sub-package names productix_<app>.migrations.productix.xxx
ALLOWED_TOKEN_RE = re.compile(
    r"(productix\.local|productix\.(js|css|html)|/assets/productix_|\.migrations\.productix\.)"
)

# hooks keys whose DICT KEYS are DocType names (checked for cross-app
# ownership). Deliberately excludes ignore_links_on_delete (a plain list used
# for platform-level cleanup of ERPNext-native doctypes).
DOCTYPE_HOOK_KEYS = (
    "doc_events",
    "override_doctype_class",
    "has_permission",
    "permission_query_conditions",
)


def discover_apps(apps_dir):
    """Find every productix module app under `apps_dir`.

    Returns (apps, issues):

    * apps — list of dicts: ``name``, ``root`` (apps/<app>), ``pkg_dir``
      (apps/<app>/<app>), ``manifest_path``, ``manifest`` (parsed dict, or
      None when missing/unparseable — the accompanying issue already failed
      the run, so per-app checks skip such entries).
    * issues — discovery-level problems (missing/unparseable manifests).
    """
    apps = []
    issues = []
    if not os.path.isdir(apps_dir):
        return apps, [f"apps directory not found: {apps_dir}"]
    for entry in sorted(os.listdir(apps_dir)):
        root = os.path.join(apps_dir, entry)
        if not os.path.isdir(root):
            continue
        pkg = os.path.join(root, entry)
        manifest_path = os.path.join(pkg, MANIFEST_NAME)
        if os.path.isfile(manifest_path):
            manifest = None
            try:
                with open(manifest_path, encoding="utf-8") as f:
                    manifest = json.load(f)
                if not isinstance(manifest, dict):
                    raise ValueError("manifest is not a JSON object")
            except (OSError, ValueError) as e:
                issues.append(f"{entry}: unparseable {MANIFEST_NAME}: {e}")
                manifest = None
            apps.append(
                {
                    "name": entry,
                    "root": root,
                    "pkg_dir": pkg,
                    "manifest_path": manifest_path,
                    "manifest": manifest,
                }
            )
        elif entry.startswith(APP_PREFIX):
            # A productix_* directory that forgot its manifest: flag it and
            # still return the entry (manifest=None) so the failure is visible.
            issues.append(
                f"{entry}: missing {MANIFEST_NAME} "
                f"(expected at {os.path.join(entry, entry, MANIFEST_NAME)})"
            )
            apps.append(
                {
                    "name": entry,
                    "root": root,
                    "pkg_dir": pkg,
                    "manifest_path": manifest_path,
                    "manifest": None,
                }
            )
        # else: frappe / erpnext / legacy `productix` / unrelated apps — ignore.
    return apps, issues


def parse_modules_txt(pkg_dir):
    """modules.txt -> {lowercased_key: display name} (supports `key = Name`)."""
    path = os.path.join(pkg_dir, "modules.txt")
    out = {}
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if " = " in line:
                key, name = line.split(" = ", 1)
                key = key.strip().lower()
                name = name.strip()
            else:
                key = line.lower().replace(" ", "_")
                name = line
            out[key] = name
    return out


def scrub_module(module_name):
    """Frappe's folder-name convention for a module (matches install behavior)."""
    return module_name.lower().replace(" ", "_").replace("-", "_")


def build_doctype_owner_map(apps):
    """{DocType name: owning app} across all discovered apps.

    Used by validate_dependencies to flag cross-app DocType hook keys
    (doc_events / override_doctype_class / has_permission /
    permission_query_conditions). Doctypes absent from this map are
    frappe/erpnext-native (e.g. "User", "Purchase Receipt") and may be
    hooked by any app.
    """
    owners = {}
    for app in apps:
        pkg = app["pkg_dir"]
        for dirpath, dirnames, filenames in os.walk(pkg):
            dirnames[:] = [d for d in dirnames if d not in ("__pycache__", "node_modules", ".git")]
            rel_parts = os.path.relpath(dirpath, pkg).split(os.sep)
            if "doctype" not in rel_parts:
                continue
            for fn in filenames:
                if not fn.endswith(".json"):
                    continue
                try:
                    with open(os.path.join(dirpath, fn), encoding="utf-8") as f:
                        data = json.load(f)
                except (OSError, ValueError):
                    continue
                if isinstance(data, dict) and data.get("doctype") == "DocType" and data.get("name"):
                    owners.setdefault(data["name"], app["name"])
    return owners


def build_module_owner_map(apps):
    """{module_name: owning_app} across all discovered apps + duplicate claims.

    Duplicate claims (the same module declared in two apps' modules.txt) are
    returned separately so callers can fail on ambiguous ownership.
    """
    claims = {}
    for app in apps:
        for name in parse_modules_txt(app["pkg_dir"]).values():
            claims.setdefault(name, []).append(app["name"])
    owners = {name: owners_[0] for name, owners_ in claims.items()}
    duplicates = {name: owners_ for name, owners_ in claims.items() if len(owners_) > 1}
    return owners, duplicates


def parse_hooks(pkg_dir):
    """AST-parse hooks.py (never executes it — validators run without frappe).

    Returns (info, issue): issue is None on success. info contains:

    * ``required_apps`` — list[str] (None when absent / not a literal list)
    * ``app_version``   — str (None when absent / not a literal string)
    * ``strings``       — list[(lineno, str)] every string constant in the file
    * ``doctype_hooks``  — {hook_key: [doctype, ...]} for DOCTYPE_HOOK_KEYS;
      a hook key maps to None when its value is not a literal dict (frappe
      imports hooks.py, so dynamic values are legal — we only statically
      verify what we can read)
    """
    path = os.path.join(pkg_dir, "hooks.py")
    if not os.path.exists(path):
        return {}, "hooks.py missing"
    try:
        with open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=path)
    except SyntaxError as e:
        return {}, f"hooks.py unparseable: {e}"

    info = {"required_apps": None, "app_version": None, "strings": [], "doctype_hooks": {}}

    # top-level assignments (hooks are always top-level)
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            targets = [node.target.id]
        else:
            continue
        value = node.value
        for target in targets:
            if target == "required_apps":
                try:
                    literal = ast.literal_eval(value)
                except (ValueError, SyntaxError):
                    literal = None
                if isinstance(literal, list) and all(isinstance(x, str) for x in literal):
                    info["required_apps"] = literal
            elif target == "app_version":
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    info["app_version"] = value.value
            elif target in DOCTYPE_HOOK_KEYS:
                try:
                    literal = ast.literal_eval(value)
                except (ValueError, SyntaxError):
                    literal = None
                if isinstance(literal, dict):
                    info["doctype_hooks"][target] = [
                        k for k in literal if isinstance(k, str)
                    ]
                else:
                    info["doctype_hooks"][target] = None

    # every string constant (for dotted-path / legacy-reference checks)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            info["strings"].append((node.lineno, node.value))

    return info, None
