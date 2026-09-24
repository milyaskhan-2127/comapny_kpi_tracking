"""
Generic manifest-discovery tests (validators + migration helpers).

Proves the tooling has NO hard-coded app lists: every rule is exercised
against synthetic app trees built in a temp dir, so adding a future app
(e.g. productix_manufacturing) requires zero validator changes.

Pure validator tests need only Python (they run anywhere pytest runs);
the registry tests need frappe and skip themselves when it is absent.

Run inside the bench container:
    cd /home/frappe/frappe-bench && \
      env/bin/python -m pytest tests/test_generic_discovery.py -q
"""
import json
import os
import sys

import pytest

# Make `scripts.*` importable no matter where pytest was launched from
# (tests/ -> repo/bench root, which holds scripts/).
_BENCH_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BENCH_ROOT not in sys.path:
    sys.path.insert(0, _BENCH_ROOT)

from scripts import validate_dependencies, validate_modules  # noqa: E402
from scripts.migration_check import co_install_issue, retired_modules  # noqa: E402


# --------------------------------------------------------------------------
# synthetic app factory
# --------------------------------------------------------------------------
def _scrub(name):
    return name.lower().replace(" ", "_").replace("-", "_")


def make_app(
    apps_dir,
    name,
    *,
    module_key,
    module_name,
    requires=("erpnext",),
    always_enabled=False,
    version="1.0.0",
    modules=None,
    hooks_requires=None,
    setup_version=None,
):
    """Create a minimal-but-valid productix app under apps_dir."""
    root = apps_dir / name
    pkg = root / name
    pkg.mkdir(parents=True)

    manifest = {
        "app": name,
        "module_key": module_key,
        "module_name": module_name,
        "title": module_name,
        "description": f"synthetic app {name}",
        "requires": list(requires),
        "version": version,
    }
    if always_enabled:
        manifest["always_enabled"] = True
    (pkg / "productix_module.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    mod_list = list(modules if modules is not None else [module_name])
    (pkg / "modules.txt").write_text("\n".join(mod_list) + "\n", encoding="utf-8")
    for mod in mod_list:
        (pkg / _scrub(mod)).mkdir(exist_ok=True)

    (pkg / "__init__.py").write_text(f'__version__ = "{version}"\n', encoding="utf-8")

    hr = list(hooks_requires) if hooks_requires is not None else list(requires)
    (pkg / "hooks.py").write_text(
        f'app_version = "{version}"\nrequired_apps = {hr!r}\n',
        encoding="utf-8",
    )

    (root / "setup.py").write_text(
        "from setuptools import setup\n\n"
        "setup(\n"
        f"    name='{name}',\n"
        f"    version='{setup_version or version}',\n"
        ")\n",
        encoding="utf-8",
    )
    return pkg


def add_doctype(pkg, owner_module, doctype_name, *, module=None):
    """Ship a DocType JSON inside an app (optionally declaring another module)."""
    dt_dir = pkg / _scrub(owner_module) / "doctype" / _scrub(doctype_name)
    dt_dir.mkdir(parents=True, exist_ok=True)
    (dt_dir / f"{_scrub(doctype_name)}.json").write_text(
        json.dumps(
            {
                "doctype": "DocType",
                "name": doctype_name,
                "module": module or owner_module,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def issues_text(issues):
    return "\n".join(str(i) for i in issues)


def make_platform_and_feature(apps_dir, **feature_kw):
    """Baseline tree: always_enabled platform + one dependent feature app."""
    make_app(
        apps_dir,
        "productix_core",
        module_key="core",
        module_name="Core Platform",
        requires=("erpnext",),
        always_enabled=True,
    )
    return make_app(
        apps_dir,
        "productix_zeta",
        module_key="zeta",
        module_name="Zeta Feature",
        requires=("erpnext", "productix_core"),
        **feature_kw,
    )


# --------------------------------------------------------------------------
# validate_modules — pass case + negatives
# --------------------------------------------------------------------------
def test_clean_tree_passes_both_validators(tmp_path):
    make_platform_and_feature(tmp_path)

    mod_issues, registry = validate_modules.run(str(tmp_path))
    assert mod_issues == [], issues_text(mod_issues)
    assert sorted(registry) == ["productix_core", "productix_zeta"]
    assert registry["productix_core"]["always_enabled"] is True

    dep_issues, summaries = validate_dependencies.run(str(tmp_path))
    assert dep_issues == [], issues_text(dep_issues)
    assert sorted(s["app"] for s in summaries) == ["productix_core", "productix_zeta"]
    assert {s["registry_module_key"] for s in summaries} == {"core", "zeta"}


def test_future_module_discovered_without_validator_changes(tmp_path):
    """productix_manufacturing joins the registry with zero tooling edits."""
    make_platform_and_feature(tmp_path)
    make_app(
        tmp_path,
        "productix_manufacturing",
        module_key="manufacturing",
        module_name="Manufacturing",
        requires=("erpnext", "productix_core"),
    )

    mod_issues, registry = validate_modules.run(str(tmp_path))
    assert mod_issues == [], issues_text(mod_issues)
    assert "manufacturing" in {
        m.get("module_key") for m in registry.values()
    }

    dep_issues, summaries = validate_dependencies.run(str(tmp_path))
    assert dep_issues == [], issues_text(dep_issues)
    mfg = next(s for s in summaries if s["app"] == "productix_manufacturing")
    assert mfg["allowed_imports"] == ["productix_core"]


def test_duplicate_module_key_flagged(tmp_path):
    make_platform_and_feature(tmp_path)
    make_app(
        tmp_path,
        "productix_zeta_clone",
        module_key="zeta",  # duplicate of productix_zeta
        module_name="Zeta Clone",
        requires=("erpnext", "productix_core"),
    )

    issues, _ = validate_modules.run(str(tmp_path))
    assert any("duplicate module_key 'zeta'" in i for i in issues), issues_text(issues)


def test_unknown_dependency_flagged(tmp_path):
    make_app(
        tmp_path,
        "productix_core",
        module_key="core",
        module_name="Core Platform",
        requires=("erpnext",),
        always_enabled=True,
    )
    make_app(
        tmp_path,
        "productix_zeta",
        module_key="zeta",
        module_name="Zeta Feature",
        requires=("erpnext", "productix_ghost"),  # does not exist
    )

    issues, _ = validate_modules.run(str(tmp_path))
    assert any("requires unknown productix app 'productix_ghost'" in i for i in issues), (
        issues_text(issues)
    )


def test_missing_manifest_flagged_by_both_validators(tmp_path):
    make_platform_and_feature(tmp_path)
    ghost = tmp_path / "productix_ghost" / "productix_ghost"
    ghost.mkdir(parents=True)  # productix_* dir, no manifest
    (ghost / "__init__.py").write_text("", encoding="utf-8")

    mod_issues, _ = validate_modules.run(str(tmp_path))
    assert any(
        "productix_ghost" in i and "missing productix_module.json" in i
        for i in mod_issues
    ), issues_text(mod_issues)

    dep_issues, _ = validate_dependencies.run(str(tmp_path))
    assert any(
        "productix_ghost" in i and "missing productix_module.json" in i
        for i in dep_issues
    ), issues_text(dep_issues)


def test_cross_app_doctype_ownership_flagged(tmp_path):
    feature = make_platform_and_feature(tmp_path)
    add_doctype(
        feature,
        "Zeta Feature",
        "Platform Widget",
        module="Core Platform",  # owned by productix_core, not zeta
    )

    issues, _ = validate_modules.run(str(tmp_path))
    assert any(
        "cross-app ownership" in i
        and "platform_widget" in i
        and "productix_core" in i
        for i in issues
    ), issues_text(issues)


def test_hooks_requires_mismatch_flagged(tmp_path):
    make_platform_and_feature(
        tmp_path,
        hooks_requires=("erpnext",),  # manifest declares productix_core too
    )

    issues, _ = validate_modules.run(str(tmp_path))
    assert any(
        "hooks required_apps" in i and "manifest requires" in i for i in issues
    ), issues_text(issues)


def test_dependency_cycle_flagged(tmp_path):
    make_app(
        tmp_path,
        "productix_core",
        module_key="core",
        module_name="Core Platform",
        requires=("erpnext",),
        always_enabled=True,
    )
    make_app(
        tmp_path,
        "productix_zeta",
        module_key="zeta",
        module_name="Zeta Feature",
        requires=("erpnext", "productix_core", "productix_yota"),
    )
    make_app(
        tmp_path,
        "productix_yota",
        module_key="yota",
        module_name="Yota Feature",
        requires=("erpnext", "productix_core", "productix_zeta"),
    )

    issues, _ = validate_modules.run(str(tmp_path))
    assert any("dependency cycle" in i for i in issues), issues_text(issues)


def test_platform_must_not_depend_on_feature_apps(tmp_path):
    make_app(
        tmp_path,
        "productix_zeta",
        module_key="zeta",
        module_name="Zeta Feature",
        requires=("erpnext",),
    )
    make_app(
        tmp_path,
        "productix_core",
        module_key="core",
        module_name="Core Platform",
        requires=("erpnext", "productix_zeta"),  # platform depending downward
        always_enabled=True,
    )

    issues, _ = validate_modules.run(str(tmp_path))
    assert any("platform app must not depend" in i for i in issues), issues_text(
        issues
    )


def test_version_mismatch_flagged(tmp_path):
    make_platform_and_feature(tmp_path, setup_version="2.0.0")

    issues, _ = validate_modules.run(str(tmp_path))
    assert any("version mismatch" in i for i in issues), issues_text(issues)


# --------------------------------------------------------------------------
# validate_dependencies — negatives
# --------------------------------------------------------------------------
def test_undeclared_sibling_import_flagged(tmp_path):
    feature = make_app(
        tmp_path,
        "productix_core",
        module_key="core",
        module_name="Core Platform",
        requires=("erpnext",),
        always_enabled=True,
    )
    del feature
    zeta = make_app(
        tmp_path,
        "productix_zeta",
        module_key="zeta",
        module_name="Zeta Feature",
        requires=("erpnext",),  # productix_core NOT declared
    )
    (zeta / "leak.py").write_text("from productix_core import x\n", encoding="utf-8")

    issues, _ = validate_dependencies.run(str(tmp_path))
    assert any("imports productix_core" in i for i in issues), issues_text(issues)


def test_declared_sibling_import_allowed(tmp_path):
    feature = make_platform_and_feature(tmp_path)
    (feature / "ok.py").write_text(
        "from productix_core.modules.registry import get_registry\n",
        encoding="utf-8",
    )

    issues, _ = validate_dependencies.run(str(tmp_path))
    assert issues == [], issues_text(issues)


def test_legacy_dotted_import_and_string_flagged(tmp_path):
    feature = make_platform_and_feature(tmp_path)
    (feature / "legacy_import.py").write_text(
        "from productix.recipe_management.utils import helper\n",
        encoding="utf-8",
    )
    (feature / "legacy_dynamic.py").write_text(
        'fn = frappe.get_attr("productix.kpi_tracking.api.run")\n',
        encoding="utf-8",
    )

    issues, _ = validate_dependencies.run(str(tmp_path))
    assert any("legacy import 'productix'" in i for i in issues), issues_text(issues)
    assert any("reference in string" in i for i in issues), issues_text(issues)


def test_allowed_legacy_tokens_and_comments_not_flagged(tmp_path):
    feature = make_platform_and_feature(tmp_path)
    (feature / "benign.py").write_text(
        "# historical note: productix.recipe_management moved to productix_recipe\n"
        'email = "info@productix.local"\n'
        'route = "/productix/home"\n'
        "url = 'https://productix.local/app'\n",
        encoding="utf-8",
    )

    issues, _ = validate_dependencies.run(str(tmp_path))
    assert issues == [], issues_text(issues)


def test_legacy_js_api_path_flagged(tmp_path):
    feature = make_platform_and_feature(tmp_path)
    pub = feature / "public" / "js"
    pub.mkdir(parents=True)
    (pub / "old.js").write_text(
        'frappe.call({ method: "productix.api.inventory.get_stock" });\n',
        encoding="utf-8",
    )

    issues, _ = validate_dependencies.run(str(tmp_path))
    assert any("legacy JS API path" in i for i in issues), issues_text(issues)


def test_cross_app_doctype_hook_key_flagged(tmp_path):
    feature = make_platform_and_feature(tmp_path)
    add_doctype(feature, "Zeta Feature", "Zeta Widget")  # owned by zeta
    # platform hooks a DocType it does not own
    core_hooks = tmp_path / "productix_core" / "productix_core" / "hooks.py"
    core_hooks.write_text(
        core_hooks.read_text(encoding="utf-8")
        + '\ndoc_events = {"Zeta Widget": {"on_update": "x.y.z"}}\n',
        encoding="utf-8",
    )

    issues, _ = validate_dependencies.run(str(tmp_path))
    assert any(
        "doc_events key 'Zeta Widget'" in i and "owned by productix_zeta" in i
        for i in issues
    ), issues_text(issues)


def test_hooks_dotted_path_to_undeclared_sibling_flagged(tmp_path):
    feature = make_platform_and_feature(tmp_path)  # zeta requires productix_core
    other = make_app(
        tmp_path,
        "productix_yota",
        module_key="yota",
        module_name="Yota Feature",
        requires=("erpnext", "productix_core"),
    )
    del other
    # zeta hooks reach into yota (not declared in requires)
    zeta_hooks = feature / "hooks.py"
    zeta_hooks.write_text(
        zeta_hooks.read_text(encoding="utf-8")
        + '\non_login = "productix_yota.api.session.on_login"\n',
        encoding="utf-8",
    )

    issues, _ = validate_dependencies.run(str(tmp_path))
    assert any("targets 'productix_yota'" in i for i in issues), issues_text(issues)


def test_native_and_self_hooks_paths_allowed(tmp_path):
    feature = make_platform_and_feature(tmp_path)
    core_hooks = tmp_path / "productix_core" / "productix_core" / "hooks.py"
    core_hooks.write_text(
        core_hooks.read_text(encoding="utf-8")
        + '\ndoc_events = {"User": {"after_insert": "frappe.utils.on_user"}}\n'
        + 'boot_session = "productix_core.utils.boot.boot_session"\n',
        encoding="utf-8",
    )

    issues, _ = validate_dependencies.run(str(tmp_path))
    assert issues == [], issues_text(issues)


# --------------------------------------------------------------------------
# migration_check — pure helpers
# --------------------------------------------------------------------------
def test_co_install_issue_rules():
    # legacy site alone: acceptable (still running the monolith)
    assert co_install_issue(["frappe", "erpnext", "productix"], ["productix_core"]) is None
    # modular site alone: acceptable
    assert (
        co_install_issue(["frappe", "erpnext", "productix_core"], ["productix_core"])
        is None
    )
    # bench ships both apps but this site only installed legacy: acceptable
    assert (
        co_install_issue(
            ["frappe", "productix"], ["productix_core", "productix_kpi"]
        )
        is None
    )
    # both architectures on ONE site: forbidden
    issue = co_install_issue(
        ["frappe", "productix", "productix_core", "productix_kpi"],
        ["productix_core", "productix_kpi"],
    )
    assert issue is not None
    assert "mutually exclusive" in issue


def test_retired_modules_derivation():
    legacy = {
        "Recipe Management",
        "Subscription Management",
        "Instruction Room",
        "Alerts",
        "KPI Tracking",
    }
    owned = {
        "Productix Core",
        "Subscription Management",
        "Recipe Management",
        "KPI Tracking",
        "Instruction Room",
    }
    assert retired_modules(legacy, owned) == ["Alerts"]
    assert retired_modules(legacy, legacy) == []
    assert retired_modules(set(), owned) == []


# --------------------------------------------------------------------------
# runtime registry (frappe required — skipped elsewhere)
# --------------------------------------------------------------------------
def test_registry_discovers_future_module_and_excludes_legacy(monkeypatch, tmp_path):
    """_load_registry picks up ANY installed app shipping a manifest.

    A synthetic productix_manufacturing (not referenced anywhere in Core)
    must appear; the legacy `productix` app (no manifest) must not.
    """
    frappe = pytest.importorskip("frappe")

    from productix_core.modules import registry as reg

    pkg = tmp_path / "productix_manufacturing" / "productix_manufacturing"
    pkg.mkdir(parents=True)
    (pkg / "productix_module.json").write_text(
        json.dumps(
            {
                "app": "productix_manufacturing",
                "module_key": "manufacturing",
                "module_name": "Manufacturing",
                "requires": ["erpnext", "productix_core"],
                "version": "1.0.0",
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        frappe,
        "get_installed_apps",
        lambda *a, **k: [
            "frappe",
            "erpnext",
            "productix",  # legacy: no manifest -> must be excluded
            "productix_core",
            "productix_manufacturing",
        ],
    )
    real_get_app_path = frappe.get_app_path

    def fake_get_app_path(app, *joins):
        if app == "productix_manufacturing":
            base = str(pkg)
            return os.path.join(base, *joins) if joins else base
        return real_get_app_path(app, *joins)

    monkeypatch.setattr(frappe, "get_app_path", fake_get_app_path)

    loaded = reg._load_registry()
    assert set(loaded) == {"core", "manufacturing"}
    assert loaded["manufacturing"]["app"] == "productix_manufacturing"
    # no manifest-bearing entry for the legacy app
    assert all(m.get("app") != "productix" for m in loaded.values())

    # platform keys derived from the always_enabled flag, not hard-coded
    monkeypatch.setattr(reg, "get_registry", lambda: loaded)
    assert reg.platform_module_keys() == {"core"}
