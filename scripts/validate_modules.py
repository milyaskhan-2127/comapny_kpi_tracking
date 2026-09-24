#!/usr/bin/env python3
"""
validate_modules.py — module-registry & ownership validation.

Discovers every productix app under the apps dir that ships a
`productix_module.json` (shared with validate_dependencies via
_manifest_discovery — no hard-coded app list), then checks:

  1. Manifest well-formed: `app` == directory, `module_key`/`module_name`
     present and unique across apps, `module_name` owned via the app's own
     modules.txt, `version` present, `requires` a list of strings.
  2. Platform invariants: exactly one manifest flagged `always_enabled`; that
     platform app declares no productix_* dependency; every other app can
     reach the platform through its requires graph.
  3. Dependency graph: productix_* requires must name a discovered app;
     no cycles; no self-requires.
  4. Structure: every modules.txt entry has a module folder (scrub convention).
  5. Ownership: every DocType/Page JSON declares a module the app owns —
     cross-app ownership and orphan modules are both errors; the same DocType
     name is never shipped by two apps.
  6. Hooks: hooks.py required_apps == manifest requires (same set);
     hooks.py exists and parses.
  7. Version sync: manifest `version` == __init__ `__version__` ==
     hooks `app_version` == setup.py `version` (all must be present).

Usage:
    python scripts/validate_modules.py [--apps-dir apps]

Exit code 0 = clean, 1 = violations found.
API (for tests): run(apps_dir) -> (issues, registry) where
registry = {app_name: manifest}.
"""
import argparse
import json
import os
import re
import sys

try:
    from _manifest_discovery import (
        build_module_owner_map,
        discover_apps,
        parse_hooks,
        parse_modules_txt,
        scrub_module,
    )
except ImportError:  # imported as scripts.validate_modules (bench root on path)
    from scripts._manifest_discovery import (
        build_module_owner_map,
        discover_apps,
        parse_hooks,
        parse_modules_txt,
        scrub_module,
    )

JSON_SKIP_DIRS = {"fixtures", "__pycache__", "node_modules", "dist", ".git", "public", "www", "tests"}
RECORD_TYPES = {"DocType", "Page"}

INIT_VERSION_RE = re.compile(r'^__version__\s*=\s*["\']([^"\']+)["\']', re.M)
SETUP_VERSION_RE = re.compile(r'^\s*version\s*=\s*["\']([^"\']+)["\']', re.M)


def _read_text(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def _read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def check_manifest(app, issues):
    """Rule 1: manifest fields consistent with the directory it lives in."""
    name = app["name"]
    manifest = app["manifest"]
    if manifest is None:
        # discovery already reported missing/unparseable manifest
        return False

    if manifest.get("app") != name:
        issues.append(
            f"[{name}] manifest app={manifest.get('app')!r} != directory {name!r}"
        )
    key = manifest.get("module_key")
    if not isinstance(key, str) or not key:
        issues.append(f"[{name}] manifest module_key missing/empty")
    mod_name = manifest.get("module_name")
    if not isinstance(mod_name, str) or not mod_name:
        issues.append(f"[{name}] manifest module_name missing/empty")
    if not isinstance(manifest.get("requires"), list) or not all(
        isinstance(r, str) for r in manifest.get("requires") or []
    ):
        issues.append(f"[{name}] manifest requires must be a list of strings")
    if not isinstance(manifest.get("version"), str) or not manifest.get("version"):
        issues.append(f"[{name}] manifest version missing/empty")
    return True

def check_modules_txt(app, issues):
    """Rule 4: modules.txt entries each have a module folder."""
    name = app["name"]
    modules = parse_modules_txt(app["pkg_dir"])
    if not modules:
        issues.append(f"[{name}] modules.txt missing or empty")
        return modules
    for mod in modules.values():
        folder = os.path.join(app["pkg_dir"], scrub_module(mod))
        if not os.path.isdir(folder):
            issues.append(
                f"[{name}] module folder missing for {mod!r}: expected "
                f"{os.path.join(name, scrub_module(mod))}"
            )
    return modules


def check_ownership(app, owners, issues, doctype_claims):
    """Rule 5: DocType/Page JSONs declare a module this app owns."""
    name = app["name"]
    owned = set(parse_modules_txt(app["pkg_dir"]).values())
    pkg = app["pkg_dir"]

    for dirpath, dirnames, filenames in os.walk(pkg):
        rel = os.path.relpath(dirpath, pkg)
        dirnames[:] = [d for d in dirnames if d not in JSON_SKIP_DIRS]
        if rel.split(os.sep, 1)[0] in JSON_SKIP_DIRS:
            continue
        for fn in filenames:
            if not fn.endswith(".json"):
                continue
            data = _read_json(os.path.join(dirpath, fn))
            if not isinstance(data, dict):
                continue
            if data.get("doctype") not in RECORD_TYPES:
                continue
            mod = data.get("module")
            rec_name = data.get("name")
            if not mod:
                issues.append(f"[{name}] {rel}/{fn} has no 'module'")
                continue
            if mod in owned:
                pass
            elif mod in owners:
                issues.append(
                    f"[{name}] {rel}/{fn} declares module {mod!r} owned by "
                    f"{owners[mod]} (cross-app ownership)"
                )
            else:
                issues.append(
                    f"[{name}] {rel}/{fn} declares module {mod!r} owned by no "
                    f"productix app (orphan module)"
                )
            if data.get("doctype") == "DocType" and rec_name:
                doctype_claims.setdefault(rec_name, []).append(name)


def check_hooks(app, issues):
    """Rules 6+7: hooks.py required_apps == manifest requires; version sync."""
    name = app["name"]
    manifest = app["manifest"] or {}
    info, err = parse_hooks(app["pkg_dir"])
    if err:
        issues.append(f"[{name}] {err}")
        return info
    if info.get("required_apps") is None:
        issues.append(f"[{name}] hooks.py has no required_apps literal list")
    else:
        if sorted(info["required_apps"]) != sorted(manifest.get("requires") or []):
            issues.append(
                f"[{name}] hooks required_apps {sorted(info['required_apps'])} != "
                f"manifest requires {sorted(manifest.get('requires') or [])}"
            )
    if info.get("app_version") is None:
        issues.append(f"[{name}] hooks.py has no app_version string")
    return info


def check_versions(app, issues, hooks_info):
    """Rule 7: version sync across manifest / __init__ / hooks / setup.py."""
    name = app["name"]
    manifest = app["manifest"] or {}
    versions = {
        "manifest version": manifest.get("version"),
        "__init__ __version__": None,
        "hooks app_version": hooks_info.get("app_version") if hooks_info else None,
        "setup.py version": None,
    }

    init_src = _read_text(os.path.join(app["pkg_dir"], "__init__.py"))
    if init_src is not None:
        m = INIT_VERSION_RE.search(init_src)
        versions["__init__ __version__"] = m.group(1) if m else None
    setup_src = _read_text(os.path.join(app["root"], "setup.py"))
    if setup_src is not None:
        m = SETUP_VERSION_RE.search(setup_src)
        versions["setup.py version"] = m.group(1) if m else None

    missing = [label for label, val in versions.items() if not val]
    for label in missing:
        issues.append(f"[{name}] {label} missing")
    present = {val for val in versions.values() if val}
    if len(present) > 1:
        detail = ", ".join(
            f"{label}={val!r}" for label, val in versions.items() if val
        )
        issues.append(f"[{name}] version mismatch: {detail}")


def check_unique_and_platform(apps, issues):
    """Rule 2 (uniqueness + platform invariants) across all apps."""
    by_key = {}
    by_name = {}
    platforms = []
    for app in apps:
        manifest = app["manifest"]
        if manifest is None:
            continue
        key = manifest.get("module_key")
        mod_name = manifest.get("module_name")
        if isinstance(key, str) and key:
            by_key.setdefault(key, []).append(app["name"])
        if isinstance(mod_name, str) and mod_name:
            by_name.setdefault(mod_name, []).append(app["name"])
        if manifest.get("always_enabled") is True:
            platforms.append(app)

    for key, names in sorted(by_key.items()):
        if len(names) > 1:
            issues.append(f"duplicate module_key {key!r} claimed by {names}")
    for mod_name, names in sorted(by_name.items()):
        if len(names) > 1:
            issues.append(f"duplicate module_name {mod_name!r} claimed by {names}")
    if len(platforms) != 1:
        issues.append(
            "expected exactly one always_enabled platform app, found "
            f"{len(platforms)}: {[p['name'] for p in platforms]}"
        )
        return None
    platform = platforms[0]
    platform_requires = platform["manifest"].get("requires") or []
    bad = [r for r in platform_requires if r.startswith("productix_")]
    if bad:
        issues.append(
            f"[{platform['name']}] platform app must not depend on productix "
            f"apps, but requires {bad}"
        )
    return platform["name"] if isinstance(platform["name"], str) else None


def check_dep_graph(apps, platform_name, issues):
    """Rule 3: productix deps exist, no cycles, platform reachable."""
    known = {app["name"] for app in apps if app["manifest"] is not None}
    graph = {}
    for app in apps:
        manifest = app["manifest"]
        if manifest is None:
            continue
        requires = manifest.get("requires") or []
        edges = []
        for req in requires:
            if req == app["name"]:
                issues.append(f"[{app['name']}] requires itself")
                continue
            if req.startswith("productix_"):
                if req not in known:
                    issues.append(
                        f"[{app['name']}] requires unknown productix app {req!r}"
                    )
                    continue
                edges.append(req)
        graph[app["name"]] = edges

    # cycle detection (DFS, colour marking)
    WHITE, GREY, BLACK = 0, 1, 2
    colour = {node: WHITE for node in graph}

    def dfs(node, path):
        colour[node] = GREY
        for nxt in graph.get(node, []):
            if colour.get(nxt, WHITE) == GREY:
                issues.append(f"dependency cycle: {' -> '.join(path + [nxt])}")
            elif colour.get(nxt, WHITE) == WHITE:
                dfs(nxt, path + [nxt])
        colour[node] = BLACK

    for node in sorted(graph):
        if colour.get(node, WHITE) == WHITE:
            dfs(node, [node])

    # platform reachability for every non-platform app
    if platform_name:
        for node, edges in sorted(graph.items()):
            if node == platform_name:
                continue
            seen, stack = set(), list(edges)
            while stack:
                cur = stack.pop()
                if cur in seen:
                    continue
                seen.add(cur)
                stack.extend(graph.get(cur, []))
            if platform_name not in seen and platform_name != node:
                issues.append(
                    f"[{node}] does not (transitively) require the platform app "
                    f"{platform_name}"
                )


def run(apps_dir):
    """Validate module structure/ownership under apps_dir.

    Returns (issues, registry) — registry = {app_name: manifest}.
    """
    issues = []
    apps, disc_issues = discover_apps(apps_dir)
    issues.extend(disc_issues)

    registry = {
        app["name"]: app["manifest"]
        for app in apps
        if app["manifest"] is not None
    }

    active = [app for app in apps if check_manifest(app, issues)]
    owners, dup_modules = build_module_owner_map(apps)
    for mod_name, claimants in sorted(dup_modules.items()):
        issues.append(f"module {mod_name!r} claimed by multiple apps: {claimants}")

    platform_name = check_unique_and_platform(apps, issues)
    check_dep_graph(apps, platform_name, issues)

    doctype_claims = {}
    for app in active:
        check_modules_txt(app, issues)
        check_ownership(app, owners, issues, doctype_claims)
        hooks_info = check_hooks(app, issues)
        check_versions(app, issues, hooks_info)

    for doctype, claimants in sorted(doctype_claims.items()):
        if len(claimants) > 1:
            issues.append(
                f"DocType {doctype!r} shipped by multiple apps: {claimants}"
            )

    return issues, registry


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apps-dir", default="apps", help="apps directory (default: apps)")
    args = parser.parse_args(argv)

    apps_dir = args.apps_dir
    issues, registry = run(apps_dir)

    print(f"Registry ({len(registry)} apps):")
    for app_name in sorted(registry):
        manifest = registry[app_name]
        key = manifest.get("module_key")
        mod_name = manifest.get("module_name")
        always = manifest.get("always_enabled")
        requires = ",".join(manifest.get("requires") or [])
        print(f"  {app_name}: key={key!r} module={mod_name!r} always_enabled={bool(always)} requires=[{requires}]")

    if issues:
        print("VIOLATIONS:")
        for issue in issues:
            print(f"  - {issue}")
        print(f"FAIL: {len(issues)} violation(s)")
        return 1
    print("MODULES_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
