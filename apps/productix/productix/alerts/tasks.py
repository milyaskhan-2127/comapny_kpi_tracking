"""
Productix Scheduled Tasks — runs via ERPNext scheduler or manual trigger.
Registered in hooks.py scheduler_events.
"""
import frappe
from frappe.utils import today, getdate, add_days, flt


def run_daily_inventory_scan():
    """
    Daily scheduled job or manual scan:
    1. Find ingredients below minimum stock
    2. Find batches expiring within 7 days
    3. Send email alert if SMTP is configured, and record in-app alert
    4. Log the result to AI Agent Log
    """
    from productix.alerts.doctype.ai_agent_log.ai_agent_log import log_event

    try:
        low_stock_items = _get_low_stock_items()
        expiring_batches = _get_expiring_batches()

        if low_stock_items or expiring_batches:
            recipients = _get_alert_recipients()
            email_result = _send_alert_email(low_stock_items, expiring_batches, recipients)

            items_summary = ", ".join(
                [i["item_name"] for i in low_stock_items] +
                [b["item_name"] for b in expiring_batches]
            )

            # Also create an In-App Instruction Message so team sees it immediately
            _create_in_app_alert(low_stock_items, expiring_batches)

            emails_sent = len(recipients) if email_result.get("sent") else 0
            note = f" (Email Status: {email_result.get('note', 'OK')})"

            log_event(
                action_type="Scheduled Scan",
                status="Success" if email_result.get("sent") else "Warning",
                details=(
                    f"Found {len(low_stock_items)} low-stock item(s) and "
                    f"{len(expiring_batches)} expiring batch(es). "
                    f"Emails sent: {emails_sent}.{note}"
                ),
                items_affected=items_summary,
                emails_sent=emails_sent,
            )
            return {
                "low_stock_count": len(low_stock_items),
                "expiring_count": len(expiring_batches),
                "email_sent": email_result.get("sent", False),
                "note": email_result.get("note", "")
            }
        else:
            log_event(
                action_type="Scheduled Scan",
                status="Info",
                details="All inventory levels healthy — no shortages or near-term batch expiries.",
                emails_sent=0,
            )
            return {
                "low_stock_count": 0,
                "expiring_count": 0,
                "email_sent": False,
                "note": "All stock healthy"
            }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Productix Daily Scan Failed")
        try:
            from productix.alerts.doctype.ai_agent_log.ai_agent_log import log_event as _log
            _log(action_type="Scheduled Scan", status="Failed",
                 details=str(e), emails_sent=0)
        except Exception:
            pass
        return {"error": str(e)}


def mark_expired_batches():
    """
    Daily job: find batches past their expiry date and disable them.
    Preserves historical records — marks them disabled and logs audit event.
    """
    from productix.alerts.doctype.ai_agent_log.ai_agent_log import log_event

    today_date = getdate(today())

    expired = frappe.get_all("Batch", filters={
        "disabled": 0,
        "expiry_date": ["<", str(today_date)],
    }, fields=["name", "item", "expiry_date"])

    count = 0
    for batch in expired:
        try:
            old_desc = frappe.db.get_value("Batch", batch.name, "description") or ""
            frappe.db.set_value("Batch", batch.name, {
                "disabled": 1,
                "description": f"[AUTO-EXPIRED {today()}] {old_desc}".strip()
            })
            count += 1
        except Exception as e:
            frappe.log_error(f"Could not expire batch {batch.name}: {e}", "Productix Batch Expiry")

    if count:
        frappe.db.commit()
        log_event(
            action_type="System",
            status="Warning",
            details=f"Auto-disabled {count} expired batch(es).",
            items_affected=", ".join(b["name"] for b in expired),
        )


# ─────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────

def _get_low_stock_items():
    """Return list of items where usable stock < min_stock_qty."""
    from productix.recipe_management.utils.fefo_utils import get_usable_stock

    items = frappe.get_all("Item", filters={
        "disabled": 0,
        "min_stock_qty": [">", 0],
    }, fields=["name", "item_name", "item_group", "stock_uom", "min_stock_qty"])

    low = []
    for item in items:
        usable = get_usable_stock(item.name)
        min_qty = flt(item.min_stock_qty)
        if usable < min_qty:
            low.append({
                "item_code": item.name,
                "item_name": item.item_name or item.name,
                "item_group": item.item_group,
                "unit": item.stock_uom,
                "current_stock": usable,
                "minimum_stock": min_qty,
                "shortage": min_qty - usable,
            })
    return low


def _get_expiring_batches(days=7):
    """Return batches expiring within the next N days (default 7)."""
    today_date = getdate(today())
    window_end = add_days(today_date, days)

    batches = frappe.get_all("Batch", filters={
        "disabled": 0,
        "expiry_date": ["between", [str(today_date), str(window_end)]],
    }, fields=["name", "item", "expiry_date", "batch_qty", "supplier"])

    result = []
    for b in batches:
        if not b.item:
            continue
        item_name = frappe.db.get_value("Item", b.item, "item_name") or b.item
        exp_date = getdate(b.expiry_date)
        days_left = (exp_date - today_date).days

        actual_qty = frappe.db.sql("""
            SELECT IFNULL(SUM(actual_qty), 0)
            FROM `tabStock Ledger Entry`
            WHERE item_code = %s AND batch_no = %s AND is_cancelled = 0
        """, (b.item, b.name))[0][0] or 0

        result.append({
            "batch": b.name,
            "item_code": b.item,
            "item_name": item_name,
            "expiry_date": str(b.expiry_date),
            "days_left": days_left,
            "qty_remaining": flt(actual_qty),
            "supplier": b.supplier or "—",
        })

    return result


def _get_alert_recipients():
    """
    Return list of email addresses to send alerts to based on roles and active users.
    """
    recipients = []

    # 1. Look for active users with Manager / Admin / Store Keeper roles
    target_roles = [
        "Factory Admin",
        "Assistant System Administrator",
        "Production Manager",
        "Store Keeper",
        "Purchase Manager",
        "System Manager",
        "Productix Admin",
        "Productix Production Manager",
        "Productix Store Keeper",
    ]

    try:
        user_roles = frappe.get_all(
            "Has Role",
            filters={"role": ["in", target_roles], "parenttype": "User"},
            fields=["parent"],
            distinct=True,
        )
        for ur in user_roles:
            user_data = frappe.db.get_value("User", ur.parent, ["email", "enabled"], as_dict=True)
            if user_data and user_data.enabled and user_data.email and "@" in user_data.email:
                if not user_data.email.endswith("example.com") and user_data.email not in recipients:
                    recipients.append(user_data.email)
    except Exception as e:
        frappe.logger().warning(f"Error fetching role-based recipients: {e}")

    # 2. Fallback: System Administrator email
    if not recipients:
        admin_email = frappe.db.get_value("User", "Administrator", "email")
        if admin_email and "@" in admin_email and not admin_email.endswith("example.com"):
            recipients = [admin_email]

    return recipients


def _send_alert_email(low_stock_items, expiring_batches, recipients):
    """Build and safely send the HTML alert email without breaking if SMTP is unconfigured."""
    if not recipients:
        return {"sent": False, "note": "No recipients configured with valid emails."}

    has_outgoing_email = frappe.db.exists("Email Account", {"default_outgoing": 1, "enable_outgoing": 1})
    if not has_outgoing_email:
        return {"sent": False, "note": "Outgoing email account (SMTP) not configured on site."}

    subject = f"[Productix] Daily Inventory Alert — {today()}"

    # Build low-stock table
    low_stock_html = ""
    if low_stock_items:
        rows = "".join(
            f"<tr>"
            f"<td style='padding:8px;border-bottom:1px solid #eee'>{i['item_name']}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee;color:#e74c3c;font-weight:600'>"
            f"{i['current_stock']:.2f} {i['unit']}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee'>{i['minimum_stock']:.2f}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee;color:#e74c3c'>"
            f"{i['shortage']:.2f}</td>"
            f"</tr>"
            for i in low_stock_items
        )
        low_stock_html = f"""
        <h3 style="color:#e74c3c;margin:24px 0 12px">
            ⚠️ Low Stock Items ({len(low_stock_items)})
        </h3>
        <table style="width:100%;border-collapse:collapse;font-size:14px">
            <thead>
                <tr style="background:#fef2f2">
                    <th style="padding:10px 8px;text-align:left;border-bottom:2px solid #fca5a5">Item</th>
                    <th style="padding:10px 8px;text-align:left;border-bottom:2px solid #fca5a5">Current Stock</th>
                    <th style="padding:10px 8px;text-align:left;border-bottom:2px solid #fca5a5">Min Stock</th>
                    <th style="padding:10px 8px;text-align:left;border-bottom:2px solid #fca5a5">Shortage</th>
                </tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
        """

    # Build expiry table
    expiry_html = ""
    if expiring_batches:
        rows = "".join(
            f"<tr>"
            f"<td style='padding:8px;border-bottom:1px solid #eee'>{b['item_name']}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee'>{b['batch']}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee'>{b['expiry_date']}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee;"
            f"color:{'#e74c3c' if b['days_left'] <= 2 else '#f39c12'};font-weight:600'>"
            f"{b['days_left']} days</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee'>{b['qty_remaining']:.2f}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee'>{b['supplier']}</td>"
            f"</tr>"
            for b in sorted(expiring_batches, key=lambda x: x["days_left"])
        )
        expiry_html = f"""
        <h3 style="color:#f39c12;margin:24px 0 12px">
            ⏰ Batches Expiring Within 7 Days ({len(expiring_batches)})
        </h3>
        <table style="width:100%;border-collapse:collapse;font-size:14px">
            <thead>
                <tr style="background:#fffbf0">
                    <th style="padding:10px 8px;text-align:left;border-bottom:2px solid #fcd34d">Item</th>
                    <th style="padding:10px 8px;text-align:left;border-bottom:2px solid #fcd34d">Batch</th>
                    <th style="padding:10px 8px;text-align:left;border-bottom:2px solid #fcd34d">Expiry Date</th>
                    <th style="padding:10px 8px;text-align:left;border-bottom:2px solid #fcd34d">Days Left</th>
                    <th style="padding:10px 8px;text-align:left;border-bottom:2px solid #fcd34d">Qty Remaining</th>
                    <th style="padding:10px 8px;text-align:left;border-bottom:2px solid #fcd34d">Supplier</th>
                </tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
        """

    body = f"""
    <!DOCTYPE html>
    <html>
    <body style="margin:0;padding:0;font-family:Arial,sans-serif;background:#f5f5f5">
        <div style="max-width:700px;margin:24px auto;background:white;border-radius:12px;
                    overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.08)">
            <div style="background:linear-gradient(135deg,#2c3e50,#3498db);color:white;padding:28px 32px">
                <h1 style="margin:0;font-size:22px;font-weight:700">📊 Productix ERP — Daily Inventory Alert</h1>
                <p style="margin:6px 0 0;opacity:0.85;font-size:14px">{today()} &nbsp;|&nbsp; Recipe &amp; Stock Operations</p>
            </div>
            <div style="padding:24px 32px">
                {low_stock_html}
                {expiry_html}
            </div>
            <div style="padding:20px 32px;background:#f8fafc;border-top:1px solid #eee;font-size:12px;color:#9ca3af;text-align:center">
                This is an automated alert from <strong>Productix ERP</strong>.
            </div>
        </div>
    </body>
    </html>
    """

    try:
        frappe.sendmail(
            recipients=recipients,
            subject=subject,
            message=body,
            delayed=True,
        )
        return {"sent": True, "note": f"Sent to {len(recipients)} recipient(s)"}
    except Exception as e:
        frappe.logger().warning(f"Productix sendmail failed: {e}")
        return {"sent": False, "note": f"Email sending error: {str(e)}"}


def _create_in_app_alert(low_stock_items, expiring_batches):
    """Post an announcement in the Instruction Room DocType so all logged-in managers see it."""
    try:
        summary_lines = []
        if low_stock_items:
            items_str = ", ".join([f"{i['item_name']} (have {i['current_stock']:.1f}, min {i['minimum_stock']:.1f})" for i in low_stock_items[:4]])
            summary_lines.append(f"⚠️ <b>Low Stock:</b> {items_str}")
        if expiring_batches:
            batches_str = ", ".join([f"{b['item_name']} ({b['days_left']}d left)" for b in expiring_batches[:4]])
            summary_lines.append(f"⏰ <b>Expiring Soon:</b> {batches_str}")

        msg = f"<b>[Automated Inventory Scan]</b><br>" + "<br>".join(summary_lines)

        frappe.get_doc({
            "doctype": "Instruction Message",
            "sender": "Administrator",
            "message": msg,
        }).insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception as e:
        frappe.logger().warning(f"Could not post in-app inventory alert: {e}")
