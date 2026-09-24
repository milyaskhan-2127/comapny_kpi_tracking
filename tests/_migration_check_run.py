# -*- coding: utf-8 -*-
# tests/_migration_check_run.py — run scripts/migration_check.main via console
# (scripts/ lives at /home/frappe/frappe-bench/scripts, not a Frappe app).
import sys

sys.path.insert(0, "/home/frappe/frappe-bench")

from scripts.migration_check import main

rc = main()
print("MIGRATION_RC:", rc)