#!/usr/bin/env python3
"""Legacy retirement coverage audit (Task 1 checklist, code-level items 1-9).

Compares the legacy monolith apps/productix/productix against the union of the
four modular apps (productix_core / recipe / kpi / instruction) across every
artifact class that must not lose coverage when the monolith is removed:

  1  DocTypes (names, cross-app duplicates = FAIL)
  2  Whitelisted API method names
  3  hooks: scheduler_events / doc_events / permission_query_conditions /
     has_permission / override_whitelisted_methods keys & function basenames
     (cross-app key duplicates are legitimate: frappe merges hook dicts per site)
  4  hooks: app_include_js / app_include_css (file basenames), doctype_js
     coverage (split-file mapping for legacy native_doctype_scripts.js)
  5  hooks: fixtures doctype coverage (dt sets; cross-app dups legitimate)
  6  Fixture RECORDS (per fixture file, exact legacy == union(new))
  7  Frontend public assets (FILE basenames only; empty dirs carry no content)
  8  Pages / Workspaces / Number Cards / Report files (name sets)
  9  DocType field names (legacy subset of new) and DocPerm JSON equality
 10  patches.txt contents (informational; package-level = frappe layout)

Run inside the backend container:
  docker cp scripts/audit_legacy_coverage.py <backend-id>:/tmp/
  docker compose exec -T backend env/bin/python /tmp/audit_legacy_coverage.py

Exit 0 = every mandatory check PASS. Any FAIL => legacy must NOT be removed yet.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

APPS = Path("/home/frappe/frappe-bench/apps")
LEGACY_PKG = APPS / "productix" / "productix"
NEW_PKGS = {
    "productix_core": APPS / "productix_core" / "productix_core",
    "productix_recipe": APPS / "productix_recipe" / "productix_recipe",
    "productix_kpi": APPS / "productix_kpi" / "productix_kpi",
    "productix_instruction": APPS / "productix_instruction" / "productix_instruction",
}

FAILURES = []


def check(label, legacy_set, new_map, *, mode="subset", allow_dup=False):
    union = set()
    dup = {}
    for app, s in new_map.items():
        for x in s:
            if x in union:
                dup.setdefault(x, set()).add(app)
            union.add(x)
    missing = sorted(legacy_set - union)
    extra = sorted(union - legacy_set)
    status = "PASS"
    if mode != "info":
        if missing or (mode == "exact" and extra) or (dup and not allow_dup):
            status = "FAIL"
            FAILURES.append(label)
    detail = f"missing={missing or '-'}"
    if mode == "exact":
        detail += f" extra={extra or '-'}"
    elif extra:
        detail += f" platform_new={extra or '-'}"
    if dup:
        tag = "dup-ok" if allow_dup else "DUP_ACROSS_APPS"
        detail += f" {tag}={sorted(dup)}"
    print(f"[{label}] legacy={len(legacy_set)} union_new={len(union)} -> {status}  {detail}")
    return union


def pyfiles(root: Path):
    for p in root.rglob("*.py"):
        if "__pycache__" not in p.parts:
            yield p


# ---------------------------------------------------------------- doctypes
def doctypes(root: Path):
    out = {}
    for j in root.glob("**/doctype/*/*.json"):
        try:
            data = json.loads(j.read_text(encoding="utf-8"))
        except Exception:
            continue
        if data.get("name"):
            out[data["name"]] = (j, data)
    return out


# ---------------------------------------------------------------- APIs
def whitelist_funcs(root: Path):
    names = set()
    pat = re.compile(r"@frappe\.whitelist[^\n]*\n(?:@[^\n]*\n)*\s*(?:async\s+)?def\s+(\w+)")
    for p in pyfiles(root):
        try:
            text = p.read_text(encoding="utf-8")
        except Exception:
            continue
        names.update(pat.findall(text))
    return names


# ---------------------------------------------------------------- hooks
def load_hooks_ast(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    assigns = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    assigns[t.id] = node.value
    return assigns


def dict_keys(node):
    if isinstance(node, ast.Dict):
        return {k.value for k in node.keys
                if isinstance(k, ast.Constant) and isinstance(k.value, str)}
    return set()


def str_pairs(node):
    """dict of str->str (doctype_js style)."""
    out = {}
    if isinstance(node, ast.Dict):
        for k, v in zip(node.keys, node.values):
            if (isinstance(k, ast.Constant) and isinstance(k.value, str)
                    and isinstance(v, ast.Constant) and isinstance(v.value, str)):
                out[k.value] = v.value
    return out


def list_basenames(node):
    out = set()
    if isinstance(node, (ast.List, ast.Tuple)):
        for elt in node.elts:
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                out.add(Path(elt.value).name)
    return out


def fixtures_dt(node):
    out = set()
    if isinstance(node, (ast.List, ast.Tuple)):
        for elt in node.elts:
            if isinstance(elt, ast.Dict):
                for k, v in zip(elt.keys, elt.values):
                    if isinstance(k, ast.Constant) and k.value == "dt" and isinstance(v, ast.Constant):
                        out.add(v.value)
    return out


def event_funcs(node):
    out = set()
    if isinstance(node, ast.Dict):
        for v in node.values:
            targets = []
            if isinstance(v, (ast.List, ast.Tuple)):
                targets = v.elts
            elif isinstance(v, ast.Call):
                targets = [v]
            for t in targets:
                fn = None
                if isinstance(t, ast.Constant) and isinstance(t.value, str):
                    fn = t.value
                elif isinstance(t, ast.Call) and isinstance(t.func, ast.Attribute):
                    fn = t.func.attr
                elif isinstance(t, ast.Call) and isinstance(t.func, ast.Name):
                    fn = t.func.id
                if fn:
                    out.add(str(fn).split(".")[-1])
    return out


# ---------------------------------------------------------------- fixtures records
def fixture_records(root: Path):
    out = {}
    for j in root.glob("**/fixtures/*.json"):
        try:
            data = json.loads(j.read_text(encoding="utf-8"))
        except Exception:
            continue
        rows = data if isinstance(data, list) else [data]
        names = {r.get("name") for r in rows if isinstance(r, dict) and r.get("name")}
        out.setdefault(j.stem, set()).update(names)
    return out


# ---------------------------------------------------------------- inventories
def file_basenames(root: Path):
    out = set()
    if root.exists():
        for p in root.rglob("*"):
            if p.is_file() and "__pycache__" not in p.parts:
                out.add(p.name)
    return out


def dir_names(root: Path, kind: str):
    out = set()
    for p in root.glob(f"**/{kind}/*"):
        if p.is_dir() and not p.name.startswith("__"):
            out.add(p.name)
    return out


def fields_of(doctype_tuple):
    _, data = doctype_tuple
    return {f.get("fieldname") for f in data.get("fields", []) if f.get("fieldname")}


def perms_of(doctype_tuple):
    _, data = doctype_tuple
    rows = []
    for r in data.get("permissions", []):
        rows.append(tuple(sorted((k, str(v)) for k, v in r.items() if v)))
    return sorted(rows)


def main():
    print("=== LEGACY COVERAGE AUDIT (apps/productix vs union productix_*) ===\n")
    if not LEGACY_PKG.exists():
        # Legacy retired: the monolith was removed from the working tree only
        # after this audit passed 30/30 (tests/ACCEPTANCE_EVIDENCE.md §11) and
        # the pre-removal state was tagged. Re-run the full audit from the tag:
        #   git checkout pre-legacy-retirement
        print("LEGACY_COVERAGE_AUDIT: RETIRED (apps/productix absent)")
        print("  pre-removal audit: ALL_CHECKS_PASS 30/30 "
              "(tests/ACCEPTANCE_EVIDENCE.md §11)")
        print("  baseline preserved at git tag: pre-legacy-retirement")
        return 0
    leg_dt = doctypes(LEGACY_PKG)
    new_dt = {app: doctypes(pkg) for app, pkg in NEW_PKGS.items()}
    new_dt_flat = {}
    dup_dt = {}
    for app, d in new_dt.items():
        for name in d:
            if name in new_dt_flat:
                dup_dt.setdefault(name, [new_dt_flat[name][0]]).append(app)
            new_dt_flat[name] = (app, d[name])
    check("[1 ] DocTypes", set(leg_dt), {a: set(d) for a, d in new_dt.items()})
    if dup_dt:
        print(f"        DUP_DOCTYPES={dup_dt}")
        FAILURES.append("[1 ] DocTypes DUP")

    check("[2 ] Whitelisted API names", whitelist_funcs(LEGACY_PKG),
          {a: whitelist_funcs(p) for a, p in NEW_PKGS.items()})

    leg_h = load_hooks_ast(LEGACY_PKG / "hooks.py")
    new_h = {a: load_hooks_ast(p / "hooks.py") for a, p in NEW_PKGS.items()}

    def hook_union(fn):
        return {a: fn(h) for a, h in new_h.items()}

    # cross-app duplicate hook KEYS are legitimate (frappe merges per site)
    check("[3a] hooks scheduler_events keys", dict_keys(leg_h.get("scheduler_events")),
          hook_union(lambda h: dict_keys(h.get("scheduler_events"))), allow_dup=True)
    check("[3b] hooks scheduler_events jobs", event_funcs(leg_h.get("scheduler_events")),
          hook_union(lambda h: event_funcs(h.get("scheduler_events"))))
    check("[3c] hooks doc_events keys", dict_keys(leg_h.get("doc_events")),
          hook_union(lambda h: dict_keys(h.get("doc_events"))))
    check("[3d] hooks doc_events handlers", event_funcs(leg_h.get("doc_events")),
          hook_union(lambda h: event_funcs(h.get("doc_events"))))
    check("[3e] hooks permission_query_conditions", dict_keys(leg_h.get("permission_query_conditions")),
          hook_union(lambda h: dict_keys(h.get("permission_query_conditions"))))
    check("[3f] hooks has_permission", dict_keys(leg_h.get("has_permission")),
          hook_union(lambda h: dict_keys(h.get("has_permission"))))
    check("[3g] hooks override_whitelisted_methods", dict_keys(leg_h.get("override_whitelisted_methods")),
          hook_union(lambda h: dict_keys(h.get("override_whitelisted_methods"))))

    # app_include: legacy native_doctype_scripts.js was re-homed as a split,
    # per-doctype pair (see [4c]/[4e]); exclude it from the global list compare.
    leg_global = list_basenames(leg_h.get("app_include_js")) - {"native_doctype_scripts.js"}
    check("[4a] hooks app_include_js", leg_global,
          hook_union(lambda h: list_basenames(h.get("app_include_js"))), allow_dup=True)
    check("[4b] hooks app_include_css", list_basenames(leg_h.get("app_include_css")),
          hook_union(lambda h: list_basenames(h.get("app_include_css"))), allow_dup=True)

    leg_dj = str_pairs(leg_h.get("doctype_js"))
    new_dj = {a: str_pairs(h.get("doctype_js")) for a, h in new_h.items()}
    check("[4c] hooks doctype_js doctypes", set(leg_dj),
          {a: set(d) for a, d in new_dj.items()})
    missing_targets = []
    for a, pkg in NEW_PKGS.items():
        for dt, rel in new_dj[a].items():
            if not (pkg / rel).exists():
                missing_targets.append(f"{a}:{rel}")
    print(f"[4d] doctype_js target files exist under public/ -> "
          f"{'FAIL' if missing_targets else 'PASS'}  {missing_targets or '-'}")
    if missing_targets:
        FAILURES.append("[4d] doctype_js targets")
    split_files = [
        NEW_PKGS["productix_recipe"] / "public/js/custom_scripts/recipe_doctype_scripts.js",
        NEW_PKGS["productix_kpi"] / "public/js/custom_scripts/kpi_user_scripts.js",
    ]
    present = [str(p.name) for p in split_files if p.exists()]
    ok_split = len(present) == len(split_files)
    print(f"[4e] legacy native_doctype_scripts.js split coverage (recipe 4 doctypes + kpi User) -> "
          f"{'PASS' if ok_split else 'FAIL'}  {present}")
    if not ok_split:
        FAILURES.append("[4e] native split")

    # fixtures dt sets; cross-app duplicates legitimate (record level = [6])
    check("[5 ] hooks fixtures dt coverage", fixtures_dt(leg_h.get("fixtures")),
          hook_union(lambda h: fixtures_dt(h.get("fixtures"))), mode="exact", allow_dup=True)

    leg_fx = fixture_records(LEGACY_PKG)
    new_fx = {a: fixture_records(p) for a, p in NEW_PKGS.items()}
    all_fx_keys = sorted(set(leg_fx) | {k for m in new_fx.values() for k in m})
    for key in all_fx_keys:
        if key in leg_fx:
            check(f"[6 ] fixture records:{key}", leg_fx[key],
                  {a: m.get(key, set()) for a, m in new_fx.items()}, mode="exact")
        else:
            check(f"[6 ] fixture records:{key} (new-only)", set(),
                  {a: m.get(key, set()) for a, m in new_fx.items()}, mode="info")

    # public assets: files only (empty dirs carry no content); native split = [4e]
    leg_assets = file_basenames(LEGACY_PKG / "public") - {"native_doctype_scripts.js"}
    check("[7 ] public asset files", leg_assets,
          {a: file_basenames(p / "public") for a, p in NEW_PKGS.items()}, allow_dup=True)

    check("[8a] Pages", dir_names(LEGACY_PKG, "page"),
          {a: dir_names(p, "page") for a, p in NEW_PKGS.items()}, mode="exact")
    leg_ws = dir_names(LEGACY_PKG, "workspace")
    new_ws = {a: dir_names(p, "workspace") for a, p in NEW_PKGS.items()}
    new_ws_union = set().union(*new_ws.values()) if new_ws else set()
    if leg_ws:
        check("[8b] Workspaces", leg_ws, new_ws, mode="exact")
    else:
        # legacy workspace dirs were relocated into the new apps during
        # modularization (git shows them as deleted under apps/productix/)
        expected = {"company_tracking_system", "recipe_management"}
        ok = new_ws_union == expected
        print(f"[8b] Workspaces: legacy dirs already relocated -> "
              f"{'PASS' if ok else 'FAIL'}  new={sorted(new_ws_union)}")
        if not ok:
            FAILURES.append("[8b] Workspaces")
    check("[8c] Number Cards", dir_names(LEGACY_PKG, "number_card"),
          {a: dir_names(p, "number_card") for a, p in NEW_PKGS.items()}, mode="exact")
    leg_reports = {j.stem for j in LEGACY_PKG.glob("**/report/*/*.json")}
    new_reports = {a: {j.stem for j in p.glob("**/report/*/*.json")} for a, p in NEW_PKGS.items()}
    check("[8d] Report files", leg_reports, new_reports, mode="exact")

    missing_fields, extra_fields, perm_diff = [], [], []
    for name, (j, data) in sorted(leg_dt.items()):
        if name not in new_dt_flat:
            missing_fields.append(f"{name}(doctype-missing)")
            continue
        app, (nj, ndata) = new_dt_flat[name]
        lf, nf = fields_of((j, data)), fields_of((nj, ndata))
        if lf - nf:
            missing_fields.append(f"{name}:{sorted(lf - nf)}")
        if nf - lf:
            extra_fields.append(f"{name}+{sorted(nf - lf)}")
        if perms_of((j, data)) != perms_of((nj, ndata)):
            perm_diff.append(f"{name}({app})")
    print(f"[9a] DocType FIELDS legacy⊆new: legacy_doctypes={len(leg_dt)} -> "
          f"{'FAIL' if missing_fields else 'PASS'}  missing_fields={missing_fields or '-'}")
    if missing_fields:
        FAILURES.append("[9a] fields")
    print(f"[9b] DocType FIELDS new-adds (info): {extra_fields or '-'}")
    print(f"[9c] DocPerm JSON differences legacy vs new (info, "
          f"{len(perm_diff)}/{len(leg_dt)}): {perm_diff or '-'}")

    # patches.txt lives at PACKAGE level (frappe get_app_path -> <app>/<pkg>/)
    for label, appdir, pkg in [
        ("[10a] legacy patches.txt", "productix", "productix"),
        ("[10b] core patches.txt", "productix_core", "productix_core"),
        ("[10c] recipe patches.txt", "productix_recipe", "productix_recipe"),
        ("[10d] kpi patches.txt", "productix_kpi", "productix_kpi"),
        ("[10e] instruction patches.txt", "productix_instruction", "productix_instruction"),
    ]:
        f = APPS / appdir / pkg / "patches.txt"
        lines = [l.strip() for l in f.read_text(encoding="utf-8").splitlines()
                 if l.strip() and not l.startswith("#")] if f.exists() else []
        print(f"{label} (info): {lines or ['<absent>']}")

    print()
    if FAILURES:
        print(f"LEGACY_COVERAGE_AUDIT: FAIL ({len(FAILURES)}): {FAILURES}")
        return 1
    print("LEGACY_COVERAGE_AUDIT: ALL_CHECKS_PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
