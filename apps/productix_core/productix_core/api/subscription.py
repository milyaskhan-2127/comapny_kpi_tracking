import frappe


@frappe.whitelist()
def get_subscription_status():
    """Return current license status for the logged-in user."""
    if frappe.session.user in ("Administrator", "Guest"):
        return {"valid": True, "expired": False, "expiring_soon": False}

    from frappe.utils import getdate, today, add_days

    licenses = frappe.get_all("Productix License",
        filters={"is_active": 1},
        fields=["name", "valid_until", "max_users"],
        order_by="valid_until desc",
        limit=1)

    if not licenses:
        return {"valid": False, "expired": True, "valid_until": None, "expiring_soon": False}

    lic = licenses[0]
    today_date = getdate(today())
    exp_date = getdate(lic.valid_until) if lic.valid_until else None

    if not exp_date:
        return {"valid": True, "expired": False, "expiring_soon": False}

    days_left = (exp_date - today_date).days

    return {
        "valid": days_left >= 0,
        "expired": days_left < 0,
        "expiring_soon": 0 <= days_left <= 7,
        "days_left": days_left,
        "valid_until": str(lic.valid_until),
        "license": lic.name,
    }


@frappe.whitelist()
def process_renewal_webhook():
    """
    Secure webhook endpoint for payment gateway callbacks.
    Validates signature, finds license, renews if payment confirmed.
    Idempotent: same webhook_id will not double-renew.
    """
    import json
    import hmac
    import hashlib

    frappe.flags.ignore_permissions = True

    # Get raw payload
    payload_str = frappe.request.data.decode("utf-8")
    payload = json.loads(payload_str)

    # Validate webhook signature (HMAC-SHA256)
    secret = frappe.conf.get("payment_webhook_secret", "")
    received_sig = frappe.get_request_header("X-Webhook-Signature", "")

    if secret:
        expected = hmac.new(secret.encode(), payload_str.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, received_sig):
            frappe.local.response.http_status_code = 400
            return {"status": "error", "message": "Invalid signature"}

    # Extract fields from payload (adapt to your gateway's format)
    event_type = payload.get("event") or payload.get("type")
    webhook_id = payload.get("id") or payload.get("webhook_id")
    payment_status = payload.get("status") or payload.get("payment_status")
    payment_ref = payload.get("payment_id") or payload.get("reference")
    license_key = payload.get("metadata", {}).get("license_key") or payload.get("license_key")

    # Only process successful payments
    if payment_status not in ("succeeded", "paid", "success", "completed"):
        return {"status": "ignored", "reason": f"Payment status: {payment_status}"}

    if not license_key:
        frappe.local.response.http_status_code = 422
        return {"status": "error", "message": "license_key not found in webhook payload"}

    # Find the license
    lic_name = frappe.db.get_value("Productix License", {"license_key": license_key}, "name")
    if not lic_name:
        frappe.local.response.http_status_code = 404
        return {"status": "error", "message": "License not found"}

    lic_doc = frappe.get_doc("Productix License", lic_name)

    # Idempotency check
    if lic_doc.last_webhook_id == webhook_id:
        return {"status": "ok", "message": "Already processed — no duplicate renewal"}

    # Renew
    lic_doc.renew(months=12, payment_ref=payment_ref, webhook_id=webhook_id)

    # Log
    frappe.get_doc({
        "doctype": "AI Agent Log",
        "action_type": "Webhook Event",
        "status": "Success",
        "details": f"Payment webhook processed. License {license_key} renewed. Payment ref: {payment_ref}",
        "emails_sent": 0,
    }).insert(ignore_permissions=True)
    frappe.db.commit()

    return {"status": "ok", "message": "License renewed successfully", "license": lic_name}
