# Minimal pytest plugin hooks for the productix modularity tests.
#
# Tests are designed to run INSIDE a bench (frappe importable) and to skip
# gracefully outside one (e.g. plain `pytest` on a dev machine).
#
# Inside a bench, set PRODUCTIX_TEST_SITE=<site> to have this plugin connect
# frappe to that site before collection:
#
#   cd /home/frappe/frappe-bench
#   PRODUCTIX_TEST_SITE=productix-a.local \
#     env/bin/python -m pytest ../tests/test_registry_consistency.py -v
import os

import pytest


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    site = os.environ.get("PRODUCTIX_TEST_SITE")
    if not site:
        return
    # HOME-based logger fallback (~/logs) is not part of the image or any
    # volume — a fresh container lacks it and frappe's import-time logging
    # then raises FileNotFoundError (INTERNALERROR). Create it first.
    os.makedirs(os.path.join(os.path.expanduser("~"), "logs"), exist_ok=True)
    try:
        import frappe
        from frappe.utils import get_bench_path
    except ImportError:
        return
    if not getattr(frappe.local, "site", None):
        bench_path = get_bench_path()
        sites_path = os.path.join(bench_path, "sites")
        # raw `env/bin/python -m pytest` (outside the bench CLI) lacks the
        # log dirs frappe's RotatingFileHandler requires.
        for log_dir in (
            os.path.join(bench_path, site, "logs"),
            os.path.join(sites_path, site, "logs"),
        ):
            os.makedirs(log_dir, exist_ok=True)
        frappe.init(site=site, sites_path=sites_path)
        frappe.connect()
        frappe.set_user("Administrator")