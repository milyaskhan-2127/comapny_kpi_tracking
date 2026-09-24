# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, "/home/frappe/frappe-bench")

import frappe

frappe.clear_cache()
frappe.local.app_modules = None
frappe.setup_module_map(include_all_apps=True)
print("CACHE_CLEARED app_modules:", sorted(frappe.local.app_modules.keys()))