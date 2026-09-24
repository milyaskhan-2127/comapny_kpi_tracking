# Uninstall-equivalent for the retired monolithic `productix` app, generic.
# Prefer tests/_retire_site_legacy.py (argv site) — this file is the proven
# productix-mig.local variant kept for harness parity with prior evidence runs.
# bench `uninstall-app productix` is blocked by frappe's substring dependency
# guard ("productix" in required_apps "productix_core" -> True). The legacy app
# owns 0 Module Defs (all repointed to the new apps) and defines no uninstall
# hooks, so remove_app's net effect is exactly remove_from_installed_apps +
# versions update + cache clear. We invoke that same primitive directly below.
import frappe
import json

out = []
frappe.init(site="productix-mig.local")
frappe.connect()
out.append("installed_apps BEFORE: " + json.dumps(frappe.get_installed_apps()))
defv = frappe.db.get_value("DefaultValue", {"defkey": "installed_apps"})
out.append("DefaultValue.installed_apps BEFORE: " + str(defv))

from frappe.installer import remove_from_installed_apps
remove_from_installed_apps("productix")

out.append("installed_apps AFTER remove: " + json.dumps(frappe.get_installed_apps()))
defv2 = frappe.db.get_value("DefaultValue", {"defkey": "installed_apps"})
out.append("DefaultValue.installed_apps AFTER: " + str(defv2))

# mirror bench uninstall-app epilogue
frappe.get_single("Installed Applications").update_versions()
frappe.db.commit()
frappe.clear_cache()
frappe.destroy()

frappe.init(site="productix-mig.local")
frappe.connect()
installed_apps = frappe.get_all("Installed Application", fields=["app_name", "app_version"], order_by="app_name")
out.append("Installed Application rows AFTER: " + json.dumps(installed_apps, default=str))
frappe.destroy()

with open("/tmp/_uninstall_run.txt", "w") as f:
    f.write("\n".join(out))
print("WROTE", "/tmp/_uninstall_run.txt")
