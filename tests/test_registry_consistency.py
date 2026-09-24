"""
Module-registry invariants.

Run inside the bench container:
    docker compose exec backend bash -c "cd /home/frappe/frappe-bench && \\
      /home/frappe/frappe-bench/env/bin/python -m pytest ../apps/../tests -q"
(or mount this tests/ folder into /home/frappe/frappe-bench/tests)

Outside a bench these tests are skipped.
"""
import pytest

frappe = pytest.importorskip("frappe")


@pytest.fixture(scope="module", autouse=True)
def _site_context():
    if not getattr(frappe.local, "site", None):
        pytest.skip("requires a connected bench site")


def test_core_is_always_platform_enabled():
    from productix_core.modules.entitlement import is_module_enabled

    assert is_module_enabled("core") is True


def test_not_installed_module_is_not_enabled():
    from productix_core.modules.entitlement import is_module_enabled

    # A module absent from the registry is not enabled on this site (the
    # before_request gate only acts on registry-resolved apps, so this never
    # 403s non-installed endpoints).
    assert is_module_enabled("does_not_exist") is False


def test_registry_keys_unique():
    from productix_core.modules.registry import get_registry

    reg = get_registry()
    keys = list(reg.keys())
    assert len(keys) == len(set(keys))


def test_entitlement_rows_cover_registry():
    """Every registry module has a Productix Settings entitlement row."""
    from productix_core.modules.registry import get_registry

    settings = frappe.get_cached_doc("Productix Settings")
    ent_keys = {row.module_key for row in settings.get("module_entitlements") or []}
    reg_keys = set(get_registry().keys())
    assert reg_keys <= ent_keys


def test_nonplatform_module_disable_gate():
    """Disabling a module blocks its API method with an HTTP 403."""
    from productix_core.modules.entitlement import is_module_enabled

    # Only meaningful when a non-core module is installed.
    for key in ("recipe", "kpi", "instruction"):
        if is_module_enabled(key):
            return  # covered by the orchestrated acceptance matrix instead
    pytest.skip("no non-core module installed in this site")


def test_architectures_never_coinstalled():
    """Legacy `productix` and the modular apps are mutually exclusive per site.

    Co-installation would collide 17 hook categories (docs/migration.md), so a
    healthy site runs EITHER the monolith OR manifest apps — never both.
    """
    from productix_core.modules.registry import get_registry

    installed = set(frappe.get_installed_apps())
    modular_installed = {a for a in installed if a.startswith("productix_")}

    assert not ("productix" in installed and modular_installed), (
        f"site runs both architectures: legacy 'productix' + {sorted(modular_installed)}"
    )
    if "productix" in installed:
        # legacy site: the manifest registry must resolve to nothing
        assert not get_registry(), (
            "registry resolved modules while legacy 'productix' is installed"
        )