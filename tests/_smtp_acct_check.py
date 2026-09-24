# Classify Email Account credential rows per site: does any row store the
# OLD (historically-exposed) SMTP password? Prints booleans/lengths only —
# never the credential itself.
# env/bin/python tests/_smtp_acct_check.py <site>   (HISTVAL env = old password)
import json
import os
import sys

import frappe

site = sys.argv[1]
hist = os.environ.get("HISTVAL", "")
os.makedirs(os.path.join(os.path.expanduser("~"), "logs"), exist_ok=True)
for d in (
    os.path.join(os.path.abspath("sites"), site, "logs"),
    os.path.join(os.path.dirname(os.path.abspath("sites")), site, "logs"),
):
    os.makedirs(d, exist_ok=True)
frappe.init(site=site, sites_path=os.path.abspath("sites"))
frappe.connect()
frappe.set_user("Administrator")

try:
    from frappe.utils.password import get_decrypted_password

    def reveal(doctype, name):
        return get_decrypted_password(doctype, name, "password", raise_exception=False) or ""

except Exception:
    def reveal(doctype, name):
        return ""


rows = frappe.get_all("Email Account", fields=["name", "password", "email_id"])
out = []
for r in rows:
    raw = r.password or ""
    plain = reveal("Email Account", r.name)
    verdict = "EMPTY"
    if raw or plain:
        cmp_val = plain or raw
        if hist and cmp_val == hist:
            verdict = "EQUALS_HISTORICAL"
        elif plain:
            verdict = "DIFFERENT_VALUE"
        else:
            verdict = "PRESENT_UNDECRYPTABLE"
    out.append({"name": r.name, "email_id": r.email_id, "pw_len": len(raw), "verdict": verdict})

print("SMTP_ACCT_CHECK", json.dumps({"site": site, "rows": out}))
