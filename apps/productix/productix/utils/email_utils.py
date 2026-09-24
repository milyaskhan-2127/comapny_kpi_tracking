import os
import frappe
from frappe.utils import cint


def setup_smtp_email_account():
    """
    Setup or update the default outgoing Email Account in Frappe/ERPNext
    using configured SMTP parameters.
    """
    mail_server = os.environ.get("MAIL_SERVER", "mail.techohub.net")
    mail_port = cint(os.environ.get("MAIL_PORT", "465"))
    mail_ssl = os.environ.get("MAIL_USE_SSL", "True").lower() in ("true", "1", "yes")
    mail_tls = os.environ.get("MAIL_USE_TLS", "False").lower() in ("true", "1", "yes")
    mail_user = os.environ.get("MAIL_USERNAME", "support@techohub.net")
    mail_password = os.environ.get("MAIL_PASSWORD", "").strip()
    mail_sender = os.environ.get("MAIL_DEFAULT_SENDER", "Productix ERP <support@techohub.net>")

    account_name = "Productix Support"
    email_id = mail_user or "support@techohub.net"

    account_data = {
        "email_account_name": account_name,
        "email_id": email_id,
        "smtp_server": mail_server,
        "smtp_port": mail_port,
        "use_ssl": 1 if mail_ssl else 0,
        "use_tls": 1 if mail_tls else 0,
        "login_id_is_email": 1,
        "login_id_is_email_address": 1,
        "login_id": email_id,
        "password": mail_password,
        "enable_outgoing": 1,
        "default_outgoing": 1,
        "brand_name": "Productix ERP",
        "send_unsubscribe_message": 0,
        "track_email_status": 1,
    }

    try:
        # Check if existing Email Account with this email_id or name exists
        existing = frappe.db.get_value("Email Account", {"email_id": email_id}, "name")
        if not existing:
            existing = frappe.db.get_value("Email Account", {"email_account_name": account_name}, "name")

        if existing:
            doc = frappe.get_doc("Email Account", existing)
            for k, v in account_data.items():
                setattr(doc, k, v)
            doc.flags.ignore_validate = True
            doc.flags.ignore_permissions = True
            doc.save(ignore_permissions=True)
            print(f"  ✓ Updated Email Account: {existing}")
        else:
            doc = frappe.get_doc({
                "doctype": "Email Account",
                **account_data
            })
            doc.flags.ignore_validate = True
            doc.flags.ignore_permissions = True
            doc.insert(ignore_permissions=True)
            print(f"  ✓ Created Email Account: {doc.name}")

        # Ensure password and settings are saved in DB
        frappe.db.set_value("Email Account", doc.name, {
            "smtp_server": mail_server,
            "smtp_port": mail_port,
            "use_ssl": 1 if mail_ssl else 0,
            "use_tls": 1 if mail_tls else 0,
            "enable_outgoing": 1,
            "default_outgoing": 1,
            "password": mail_password,
        })

        # Set default outgoing in all other accounts to 0 if this is default
        frappe.db.sql("""
            UPDATE `tabEmail Account`
            SET default_outgoing = 0
            WHERE name != %s
        """, (doc.name,))

        frappe.db.commit()
        return {"success": True, "email_account": doc.name}
    except Exception as e:
        frappe.logger().error(f"Failed to setup SMTP Email Account: {e}")
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def test_send_email(recipient=None):
    """
    Whitelisted method to test sending an email via the configured SMTP account.
    """
    if not recipient:
        recipient = frappe.session.user
    if recipient in ("Guest", "Administrator"):
        recipient = "support@techohub.net"

    try:
        frappe.sendmail(
            recipients=[recipient],
            subject="[Productix ERP] SMTP Test Email",
            message="""
                <h3>✅ SMTP Email Configuration Successful!</h3>
                <p>Your Productix ERP email service via <b>mail.techohub.net:465</b> (SSL) is operating properly.</p>
                <p>Automated inventory alerts, batch expiry notices, and system communications will be delivered from this account.</p>
            """,
            delayed=False,
        )
        return {"success": True, "message": f"Test email sent to {recipient}"}
    except Exception as e:
        return {"success": False, "error": str(e)}
