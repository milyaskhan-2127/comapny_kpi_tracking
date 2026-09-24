# Diagnostic: why pytest's frappe logging targeted /home/frappe/logs.
# Run from bench root inside backend: env/bin/python tests/_diag_paths.py
import os
import sys

import frappe
import frappe.utils as u

print("python     =", sys.executable)
print("frappe file=", frappe.__file__)
print("FRAPPE_BENCH_ROOT env =", os.environ.get("FRAPPE_BENCH_ROOT"))
print("get_bench_path()      =", u.get_bench_path())
print("cwd                   =", os.getcwd())
for envk in sorted(k for k in os.environ if "BENCH" in k or k == "HOME"):
    print("env:", envk, "=", os.environ[envk])

# where does frappe's database logger build its path?
import subprocess

src = os.path.dirname(frappe.__file__)
out = subprocess.run(
    ["grep", "-rn", "--include=*.py", "-e", "database.log", "-e", "log_dir", src],
    capture_output=True, text=True,
)
print("--- logger path source hits ---")
print(out.stdout[:3000])
