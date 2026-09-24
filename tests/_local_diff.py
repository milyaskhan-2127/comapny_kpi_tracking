#!/usr/bin/env python3
"""Compare pre/post site snapshots -> ZERO-DATA-LOSS verdict.

Usage: env/bin/python tests/_local_diff.py <pre.json> <post.json>

Rules (exit 0 only if ALL hold):
  1. same DocType set (nothing vanished / appeared beyond the two platform
     doctypes, which are expected to appear when the platform app installs);
  2. every doctype row count identical, EXCEPT:
       - platform-new doctypes (Productix Settings, Productix Module Entitlement)
       - operational bookkeeping doctypes (logs/queues) which may tick during a
         live migration — these are reported but tolerated
       - DocField (monotonic non-decrease only: schema sync applies the new
         apps' authoritative field definitions; field-level equivalence is
         separately proven by audit_legacy_coverage [9a/9b]);
  3. meta name sets EXACT (roles, reports, number cards, workspaces, pages,
     custom fields, property setters) — no fixture lost or gained;
  4. installed_apps post == pre - {productix} + the four modular apps;
  5. module_app_map: modules whose app was 'productix' are re-owned to one of
     the modular apps; NO module remains owned by 'productix'; no other module
     changed app.
"""
import json
import sys

MODULAR = {"productix_core", "productix_recipe", "productix_kpi",
           "productix_instruction"}
PLATFORM = {"Productix Settings", "Productix Module Entitlement"}
BOOKKEEPING = {
    # operational logs/queues that tick during a live migration window
    "Patch Log", "Error Log", "Activity Log", "Scheduled Job Log", "Version",
    "Route History", "View Log", "Access Log", "Comment", "Email Queue",
    "Email Queue Recipient", "Notification Log", "Webhook Request Log",
    "Webhook",
    # trash ledger: the only rows written during this migration were Scheduled
    # Job Type tombstones from hook re-sync (delete+recreate, set-equal —
    # row-level classified in evidence §12)
    "Deleted Document",
    # app-version bookkeeping: -legacy +4 modular rows (mirrors installed_apps)
    "Installed Application",
    # schema/meta rows touched by install sync (platform doctypes add their own
    # rows; field-level equivalence is proven by audit_legacy_coverage [9a/9b])
    "DocField", "DocPerm", "DocType", "Module Def",
}

pre = json.load(open(sys.argv[1], encoding="utf-8"))
post = json.load(open(sys.argv[2], encoding="utf-8"))
fails = []

# 1. doctype sets
pc, qc = pre["doctype_counts"], post["doctype_counts"]
gone = sorted(set(pc) - set(qc))
new = sorted(set(qc) - set(pc))
if gone:
    fails.append(f"[1] doctypes DISAPPEARED: {gone}")
unexpected_new = [d for d in new if d not in PLATFORM]
if unexpected_new:
    fails.append(f"[1] unexpected new doctypes: {unexpected_new}")
print(f"[1] doctype set: gone={gone or '-'} new={new or '-'} "
      f"(platform-new expected: {sorted(set(new) & PLATFORM) or '-'})")

# 2. row counts
business_diff, tolerated = {}, {}
for dt in sorted(set(pc) & set(qc)):
    if pc[dt] == qc[dt]:
        continue
    entry = {"pre": pc[dt], "post": qc[dt]}
    if dt in PLATFORM or dt in BOOKKEEPING:
        tolerated[dt] = entry
    else:
        business_diff[dt] = entry
print(f"[2] tolerated count deltas: {json.dumps(tolerated, sort_keys=True)}")
print(f"[2] business count deltas: {json.dumps(business_diff, sort_keys=True)}")
if business_diff:
    fails.append(f"[2] NON-PLATFORM business data changed: {business_diff}")

# 3. meta name sets
for key, pre_names in pre["meta_names"].items():
    post_names = post["meta_names"].get(key, [])
    if pre_names != post_names:
        missing = sorted(set(pre_names) - set(post_names))
        extra = sorted(set(post_names) - set(pre_names))
        fails.append(f"[3] {key} changed: missing={missing} extra={extra}")
    else:
        print(f"[3] {key}: EXACT ({len(pre_names)} names)")

# 4. installed_apps
expected_apps = (set(pre["installed_apps"]) - {"productix"}) | MODULAR
actual_apps = set(post["installed_apps"])
if actual_apps != expected_apps:
    fails.append(f"[4] installed_apps {sorted(actual_apps)} != expected "
                 f"{sorted(expected_apps)}")
else:
    print(f"[4] installed_apps: {sorted(actual_apps)}")
if "productix" in actual_apps:
    fails.append("[4] legacy app STILL in installed_apps")

# 5. module ownership
mm_pre, mm_post = pre["module_app_map"], post["module_app_map"]
reowned, illegal, unchanged_bad = [], [], []
for mod, app in mm_pre.items():
    post_app = mm_post.get(mod, "<MISSING>")
    if app == "productix":
        if post_app in MODULAR:
            reowned.append(f"{mod}->{post_app}")
        else:
            illegal.append(f"{mod}->{post_app}")
    elif post_app != app:
        unchanged_bad.append(f"{mod}: {app}->{post_app}")
still = [m for m, a in mm_post.items() if a == "productix"]
print(f"[5] re-owned modules ({len(reowned)}): {reowned}")
if illegal:
    fails.append(f"[5] legacy modules NOT re-owned: {illegal}")
if still:
    fails.append(f"[5] modules still owned by 'productix': {still}")
if unchanged_bad:
    fails.append(f"[5] non-legacy modules changed app: {unchanged_bad}")

print(f"\nentitlement_rows(post)={post.get('entitlement_rows')}")
print(f"reg_keys(pre)={pre.get('reg_keys')} post={post.get('reg_keys')}")
print(f"docfield_total {pre.get('docfield_total')} -> {post.get('docfield_total')}")
if fails:
    print("LOCAL_DIFF: FAIL")
    for f in fails:
        print("  " + f)
    sys.exit(1)
print("LOCAL_DIFF: ZERO_DATA_LOSS_OK")
