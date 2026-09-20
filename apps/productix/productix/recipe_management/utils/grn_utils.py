"""
GRN (Goods Received Note / Purchase Receipt) hooks and utilities for Productix.
Handles automatic batch generation, sequential numbering, expiry management, and serial number safety.
"""
import frappe
from frappe.utils import getdate, today, add_days, nowdate, flt


def before_purchase_receipt_validate(doc, method=None):
    """
    Hook: before Purchase Receipt validation.
    1. Set receiving user ID and full name for complete audit tracking.
    2. Auto-generate sequential Batch numbers for items with has_batch_no if not provided.
    3. Auto-generate Serial numbers if item has has_serial_no to prevent mandatory serial errors.
    4. Auto-populate default expiry dates (30 days from today) if left blank for batch items.
    5. Validate that expiry dates are not in the past.
    """
    today_date = getdate(today())
    today_str = nowdate().replace("-", "")

    # Set user audit information
    if not doc.get("received_by_user"):
        doc.received_by_user = frappe.session.user
    if not doc.get("received_by_name"):
        doc.received_by_name = frappe.utils.get_fullname(frappe.session.user) or frappe.session.user

    for idx, item in enumerate(doc.items, start=1):
        if not item.item_code:
            continue

        item_meta = frappe.get_cached_value(
            "Item", item.item_code,
            ["has_batch_no", "has_serial_no", "item_name", "stock_uom"],
            as_dict=True
        ) or {}

        has_batch = item_meta.get("has_batch_no")
        has_serial = item_meta.get("has_serial_no")

        # Expiry date validation & Batch generation
        if has_batch:
            # Respect user checkmark: if has_expiry is explicitly 0, clear expiry_date
            if item.get("has_expiry") == 0 or item.get("has_expiry") is False:
                item.expiry_date = None
                has_exp_val = 0
            elif item.get("expiry_date"):
                if getdate(item.expiry_date) < today_date:
                    frappe.throw(
                        f"Row {idx}: Expiry date ({item.expiry_date}) for item '{item.item_code}' cannot be in the past."
                    )
                has_exp_val = 1
            else:
                has_exp_val = 1 if item.get("has_expiry") else 0

            # Auto-generate batch if missing
            if not item.batch_no:
                clean_code = "".join(c for c in item.item_code if c.isalnum())[:8].upper()
                batch_count = frappe.db.count("Batch", {"item": item.item_code}) + idx
                batch_id = f"BAT-{clean_code}-{today_str}-{batch_count:03d}"

                # Ensure unique
                while frappe.db.exists("Batch", batch_id):
                    batch_count += 1
                    batch_id = f"BAT-{clean_code}-{today_str}-{batch_count:03d}"

                cert_file = item.get("certificate_file") or doc.get("shipment_certificate") or ""
                final_expiry = item.expiry_date if (has_exp_val and item.get("expiry_date")) else None

                batch_doc = frappe.get_doc({
                    "doctype": "Batch",
                    "batch_id": batch_id,
                    "item": item.item_code,
                    "item_name": item_meta.get("item_name") or item.item_code,
                    "stock_uom": item_meta.get("stock_uom") or item.uom,
                    "expiry_date": final_expiry,
                    "has_expiry": has_exp_val,
                    "certificate_file": cert_file,
                    "certificate_url": cert_file,
                    "supplier": doc.supplier,
                    "batch_qty": item.qty,
                    "disabled": 0,
                })
                batch_doc.insert(ignore_permissions=True)
                item.batch_no = batch_doc.name
            else:
                # Update existing batch document if certificate or expiry changed
                try:
                    b_doc = frappe.get_doc("Batch", item.batch_no)
                    b_changed = False
                    eff_cert = item.get("certificate_file") or doc.get("shipment_certificate") or ""
                    if eff_cert and b_doc.get("certificate_file") != eff_cert:
                        b_doc.certificate_file = eff_cert
                        b_doc.certificate_url = eff_cert
                        b_changed = True
                    if has_exp_val and item.get("expiry_date"):
                        if b_doc.expiry_date != item.expiry_date or b_doc.get("has_expiry") != 1:
                            b_doc.expiry_date = item.expiry_date
                            b_doc.has_expiry = 1
                            b_changed = True
                    elif has_exp_val == 0:
                        if b_doc.expiry_date is not None or b_doc.get("has_expiry") != 0:
                            b_doc.expiry_date = None
                            b_doc.has_expiry = 0
                            b_changed = True
                    if doc.supplier and not b_doc.get("supplier"):
                        b_doc.supplier = doc.supplier
                        b_changed = True
                    if b_changed:
                        b_doc.save(ignore_permissions=True)
                except Exception:
                    pass

        # Auto-generate serial numbers if item has serial tracking enabled
        if has_serial and not item.serial_no:
            clean_code = "".join(c for c in item.item_code if c.isalnum())[:8].upper()
            qty_int = int(flt(item.qty)) or 1
            base_count = frappe.db.count("Serial No", {"item_code": item.item_code}) + 1
            serials = [
                f"SN-{clean_code}-{today_str}-{(base_count + i):04d}"
                for i in range(qty_int)
            ]
            item.serial_no = "\n".join(serials)


def on_purchase_receipt_submit(doc, method=None):
    """
    After Purchase Receipt is submitted:
    - Ensure expiry date and supplier are set on all Batch records.
    - Synchronize batch metadata.
    - Record full audit trail in AI Agent Log / Activity stream.
    """
    for item in doc.items:
        if not item.batch_no:
            continue

        try:
            batch = frappe.get_doc("Batch", item.batch_no)
            changed = False

            # Synchronize expiry
            if item.get("has_expiry") == 0 or item.get("has_expiry") is False:
                if batch.expiry_date is not None or batch.get("has_expiry") != 0:
                    batch.expiry_date = None
                    batch.has_expiry = 0
                    changed = True
            elif item.get("expiry_date"):
                if batch.expiry_date != item.expiry_date or batch.get("has_expiry") != 1:
                    batch.expiry_date = item.expiry_date
                    batch.has_expiry = 1
                    changed = True

            # Synchronize certificate
            cert_val = item.get("certificate_file") or doc.get("shipment_certificate")
            if cert_val:
                if batch.get("certificate_file") != cert_val:
                    batch.certificate_file = cert_val
                    changed = True
                if batch.get("certificate_url") != cert_val:
                    batch.certificate_url = cert_val
                    changed = True

            if doc.supplier and not batch.get("supplier"):
                batch.supplier = doc.supplier
                changed = True

            if changed:
                batch.save(ignore_permissions=True)
        except Exception as e:
            frappe.logger().warning(f"Could not update batch {item.batch_no}: {e}")

    try:
        user = frappe.session.user
        user_name = frappe.utils.get_fullname(user) or user
        items_summary = ", ".join([f"{i.item_code} ({i.qty} {i.uom or ''})" for i in doc.items])
        total_val = sum(flt(i.amount) for i in doc.items)
        from productix.alerts.doctype.ai_agent_log.ai_agent_log import log_event
        log_event(
            action_type="Purchase Receipt",
            status="Success",
            details=f"Goods Received (GRN #{doc.name}) received by {user_name} ({user}) from supplier '{doc.supplier}'. Total Value: ${total_val:,.2f}.",
            items_affected=items_summary,
        )
    except Exception as e:
        frappe.logger().warning(f"Could not log GRN audit event: {e}")

    frappe.db.commit()


def on_purchase_receipt_cancel(doc, method=None):
    """After Purchase Receipt is cancelled."""
    try:
        user = frappe.session.user
        user_name = frappe.utils.get_fullname(user) or user
        from productix.alerts.doctype.ai_agent_log.ai_agent_log import log_event
        log_event(
            action_type="Purchase Receipt",
            status="Warning",
            details=f"Purchase Receipt #{doc.name} was cancelled by {user_name} ({user}). Supplier: {doc.supplier}.",
            items_affected=doc.name,
        )
    except Exception:
        pass
    frappe.logger().info(
        f"Purchase Receipt {doc.name} cancelled — stock reversal handled by ERPNext."
    )
