#!/usr/bin/env python3
"""
validate_dependencies.py — dependency hygiene check for the modular productix apps.

Generic rules (no hard-coded app list — discovery via `_manifest_discovery`):

  * Each app may import/call only: itself + productix apps declared in its
    own `productix_module.json` `requires` (core -> {}, others -> {productix_core}).
  * NO app may import the legacy monolithic `productix` package — checked on
    import statements AND on STRING tokens (comments are excluded by
    tokenize; sanctioned tokens like productix.local / productix.js|css|html
    / assets paths / .migrations.productix. sub-packages are ignored).
  * hooks.py dotted paths: first segment must be self, the platform app, a
    declared requires, or a non-productix (native) app.
  * hooks doctype keys (doc_events / override_doctype_class / has_permission /
    permission_query_conditions) must not target a DocType owned by a
    DIFFERENT productix app (ignore_links_on_delete deliberately excluded).
  * Discovery issues (missing/unparseable manifests) fail this validator too.

Scans Python imports/strings and JS API paths under apps/<app>/<app>/.

Usage:
    python scripts/validate_dependencies.py [--apps-dir apps]

Exit code 0 = clean, 1 = violations found.
API (for tests): run(apps_dir) -> (issues, summaries).
"""
import argparse
import io
import json
import os
import re
import sys
import tokenize

try:
    from _manifest_discovery import (
        ALLOWED_TOKEN_RE,
        build_doctype_owner_map,
        discover_apps,
        parse_hooks,
    )
except ImportError:  # imported as scripts.validate_dependencies (bench root on path)
    from scripts._manifest_discovery import (
        ALLOWED_TOKEN_RE,
        build_doctype_owner_map,
        discover_apps,
        parse_hooks,
    )

# Sanctioned cross-app calls (intentional, documented).
# core's AI Agent Log list view renders a "Run Scan" button that invokes the
# recipe app's trigger_manual_scan — but ONLY when recipe is enabled, so the
# coupling is to the module registry, never to a hard-coded install.
ALLOWED_CROSS_CALLS = {
    ("productix_core", "productix_recipe.api.inventory.trigger_manual_scan"),
}

# Legacy dotted reference inside a STRING token, e.g. "productix.recipe_management.x".
# The lookbehind excludes `productix_core.migrations.productix.…` (preceded by '.')
# and word-char prefixes (`productix_…`).
LEGACY_DOTTED_RE = re.compile(r"(?<![\w.])productix\.[A-Za-z_]")

# A dotted python-ish path string ("pkg.mod.attr") — used to scope the hooks
# first-segment check; excludes asset paths, doctype labels, versions, etc.
DOTTED_PATH_RE = re.compile(r"^[A-Za-z_]\w*(?:\.\w+)+$")


def build_patterns(app_names):
    """Dynamic regexes over discovered productix app names (+ legacy `productix`).

    Longest-first alternation so `productix_core` never partially matches as
    `productix`; `\b`/explicit `.` boundaries keep them from bleeding into
    each other.
    """
    names = sorted(set(app_names) | {"productix"}, key=len, reverse=True)
    alt = "|".join(re.escape(n) for n in names)
    py_import_re = re.compile(
        rf"^\s*(?:import|from)\s+({alt})\b",
        re.MULTILINE,
    )
    # JS API-path references (frappe.call/xcall/route), and /api/method/ URLs.
    js_api_re = re.compile(rf"['\"`/]({alt})\.\w")
    return py_import_re, js_api_re


def iter_files(pkg, exts):
    for dirpath, dirnames, filenames in os.walk(pkg):
        dirnames[:] = [d for d in dirnames if d not in ("__pycache__", "node_modules", ".git")]
        for fn in filenames:
            if fn.endswith(exts):
                yield os.path.join(dirpath, fn)


def legacy_dotted_refs_in_strings(path, text):
    """STRING tokens containing legacy `productix.…` refs (comments skipped)."""
    hits = []
    try:
        reader = io.StringIO(text).readline
        for tok in tokenize.generate_tokens(reader):
            if tok.type != tokenize.STRING:
                continue
            cleaned = ALLOWED_TOKEN_RE.sub("", tok.string)
            if LEGACY_DOTTED_RE.search(cleaned):
                hits.append(tok.start[0])
    except (tokenize.TokenError, IndentationError, SyntaxError, ValueError):
        # Unparseable file: fall back to a raw scan of the whole text so a
        # broken file can't hide legacy references.
        cleaned = ALLOWED_TOKEN_RE.sub("", text)
        if LEGACY_DOTTED_RE.search(cleaned):
            hits.append(0)
    return hits


def check_hooks(app, info, allowed_first, doctype_owner, violations):
    rel = f"{app['name']}/{app['name']}/hooks.py"

    # 1) dotted-path first segment: self | platform+declared requires | native
    for lineno, s in info.get("strings", []):
        if not DOTTED_PATH_RE.match(s):
            continue
        if ALLOWED_TOKEN_RE.search(s):
            continue
        first = s.split(".", 1)[0]
        if first == "productix":
            violations.append(f"{rel}:{lineno}: legacy dotted path {s!r}")
        elif first.startswith("productix_") and first not in allowed_first:
            violations.append(
                f"{rel}:{lineno}: dotted path {s!r} targets {first!r} "
                f"(allowed productix targets: {sorted(allowed_first)})"
            )

    # 2) doctype hook keys must not target another productix app's DocType
    for hook_key, doctypes in info.get("doctype_hooks", {}).items():
        if doctypes is None:
            continue  # dynamic dict — statically unverifiable
        for dt in doctypes:
            owner = doctype_owner.get(dt)
            if owner and owner != app["name"]:
                violations.append(
                    f"{rel}: {hook_key} key {dt!r} is a DocType owned by {owner}"
                )


def check_app(app, app_names, doctype_owner):
    """Scan one discovered app. Returns (violations, summary)."""
    name = app["name"]
    manifest = app["manifest"]
    pkg = app["pkg_dir"]
    violations = []
    scanned_py = 0
    scanned_js = 0

    declared = set(manifest.get("requires") or [])
    allowed = declared & app_names  # productix siblings this app may import
    # hooks dotted paths additionally permit the platform app (the manifest
    # may declare it only via hooks/required_apps); native (non-productix)
    # prefixes are always allowed.
    allowed_first = {name} | allowed
    if app.get("platform"):
        allowed_first.add(app["platform"])

    py_import_re, js_api_re = build_patterns(app_names)

    for path in iter_files(pkg, ".py"):
        scanned_py += 1
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()
        rel = os.path.relpath(path, os.path.dirname(os.path.dirname(pkg)))
        for m in py_import_re.finditer(text):
            target = m.group(1)
            if target == name:
                continue  # self-imports are fine
            if target == "productix":
                violations.append(f"legacy import 'productix' in {rel}")
            elif target not in allowed:
                violations.append(
                    f"{rel} imports {target} but {name} may only import {sorted(allowed)}"
                )
        for lineno in legacy_dotted_refs_in_strings(path, text):
            where = f"{rel}:{lineno}" if lineno else rel
            violations.append(f"{where}: legacy 'productix.…' reference in string")

    for path in iter_files(pkg, (".js", ".html")):
        scanned_js += 1
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()
        rel = os.path.relpath(path, os.path.dirname(os.path.dirname(pkg)))
        for m in js_api_re.finditer(text):
            if ALLOWED_TOKEN_RE.search(m.group(0)):
                continue
            token = m.group(1)
            if token == name:
                continue
            if token == "productix":
                violations.append(f"legacy JS API path 'productix.' in {rel}")
                continue
            if token not in allowed:
                start = m.start()
                if text[start] in "'\"`/":
                    start += 1
                seg = re.match(r"[A-Za-z_][\w.]*", text[start:])
                call = seg.group(0) if seg else ""
                if (name, call) not in ALLOWED_CROSS_CALLS:
                    violations.append(
                        f"{rel} calls {call!r} but {name} may only call its own app + {sorted(allowed)}"
                    )

    info, hook_err = parse_hooks(pkg)
    if hook_err:
        violations.append(hook_err)
    else:
        check_hooks(app, info, allowed_first, doctype_owner, violations)

    summary = {
        "app": name,
        "python_files": scanned_py,
        "js_files": scanned_js,
        "registry_module_key": manifest.get("module_key"),
        "allowed_imports": sorted(allowed),
    }
    return violations, summary


def run(apps_dir):
    """Scan every discovered app. Returns (issues, summaries)."""
    issues = []
    apps, disc_issues = discover_apps(apps_dir)
    issues.extend(disc_issues)

    active = [a for a in apps if a["manifest"] is not None]
    app_names = {a["name"] for a in active}
    doctype_owner = build_doctype_owner_map(apps)
    platform = next(
        (a["name"] for a in active if a["manifest"].get("always_enabled")),
        None,
    )
    for app in active:
        app["platform"] = platform
        violations, summary = check_app(app, app_names, doctype_owner)
        issues.extend(f"[{app['name']}] {v}" for v in violations)
        # summaries collected by caller via return value below
        app["_summary"] = summary

    summaries = [a["_summary"] for a in active if "_summary" in a]
    return issues, summaries


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--apps-dir", default="apps")
    args = ap.parse_args(argv)

    issues, summaries = run(args.apps_dir)

    print(json.dumps(summaries, indent=2))
    if issues:
        print("VIOLATIONS:")
        for v in issues:
            print("  - " + v)
        print(f"FAIL: {len(issues)} violation(s)")
        return 1
    print("DEPENDENCIES_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
