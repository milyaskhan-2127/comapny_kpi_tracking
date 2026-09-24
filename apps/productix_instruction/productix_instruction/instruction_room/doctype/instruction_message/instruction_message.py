import frappe
import re
from frappe.model.document import Document
from frappe.utils import strip_html


class InstructionMessage(Document):

    def after_insert(self):
        self._send_notifications()

    def _send_notifications(self):
        """
        Dynamically notify recipients via Frappe's native Notification Log (navbar bell icon)
        and realtime socketio broadcast.
        """
        sender = self.sender or frappe.session.user
        sender_fullname = frappe.utils.get_fullname(sender) or sender
        raw_msg = self.message or ""
        clean_msg = strip_html(raw_msg).strip()
        preview = clean_msg[:100] + "..." if len(clean_msg) > 100 else clean_msg

        recipients = set()

        # 1. Check if tagged to specific user
        if getattr(self, "tag_target", None) == "Specific User" and getattr(self, "tagged_user", None):
            recipients.add(self.tagged_user)

        # 2. Check for @mentions in message text (@username, @email, @all)
        mentions = re.findall(r"@([\w.@+\-]+)", clean_msg)
        is_all_tagged = "all" in [m.lower() for m in mentions] or getattr(self, "tag_target", "All Staff") == "All Staff"

        if is_all_tagged:
            # Notify all active users except the sender
            active_users = frappe.get_all("User", filters={"enabled": 1, "name": ["not in", ["Guest", sender]]}, pluck="name")
            recipients.update(active_users)
        else:
            for mention in mentions:
                user = (
                    frappe.db.get_value("User", {"name": mention}) or
                    frappe.db.get_value("User", {"username": mention}) or
                    frappe.db.get_value("User", {"first_name": mention}) or
                    frappe.db.get_value("User", {"email": ["like", f"{mention}%"]})
                )
                if user and user != sender:
                    recipients.add(user)

        # Remove sender from recipients
        recipients.discard(sender)
        recipients.discard("Guest")

        # 3. Create Frappe native Notification Log for each recipient (shows on ERPNext Navbar Bell Icon!)
        for user in recipients:
            try:
                # Custom app Message Notification
                if not frappe.db.exists("Message Notification", {"recipient": user, "message_ref": self.name}):
                    frappe.get_doc({
                        "doctype": "Message Notification",
                        "recipient": user,
                        "message_ref": self.name,
                        "is_read": 0,
                    }).insert(ignore_permissions=True)

                # ERPNext Native Notification Log (Bell Icon)
                notif = frappe.get_doc({
                    "doctype": "Notification Log",
                    "subject": f"💬 New instruction from {sender_fullname}: {preview}",
                    "for_user": user,
                    "from_user": sender,
                    "type": "Mention" if (getattr(self, "tagged_user", None) == user or not is_all_tagged) else "Alert",
                    "document_type": "Instruction Message",
                    "document_name": self.name,
                    "email_content": raw_msg,
                    "read": 0,
                })
                notif.insert(ignore_permissions=True)

                # Emit real-time notification to user's active session
                frappe.publish_realtime(
                    "notification",
                    {
                        "subject": f"💬 {sender_fullname}: {preview}",
                        "document_type": "Instruction Message",
                        "document_name": self.name,
                        "from_user": sender,
                    },
                    user=user,
                    after_commit=True,
                )
            except Exception as e:
                frappe.logger().warning(f"Could not create notification log for {user}: {e}")

        # Record mentions field
        if recipients:
            frappe.db.set_value(
                "Instruction Message", self.name,
                "mentions", ", ".join(list(recipients)[:10]) + (f" (+{len(recipients)-10} more)" if len(recipients) > 10 else ""),
                update_modified=False,
            )


@frappe.whitelist()
def clear_all_messages():
    """Admin-only: delete all instruction messages and notifications."""
    allowed_roles = {"Productix Admin", "Productix Assistant Admin", "System Manager", "Factory Admin", "Administrator"}
    user_roles = set(frappe.get_roles(frappe.session.user))
    if not allowed_roles.intersection(user_roles):
        frappe.throw("Not permitted to clear messages.")

    frappe.db.delete("Message Notification")
    frappe.db.delete("Instruction Message")
    frappe.db.commit()
    frappe.msgprint("All instruction room messages cleared.", indicator="green")


@frappe.whitelist()
def get_unread_count():
    """Return unread notification count for the current user."""
    return frappe.db.count("Message Notification", {
        "recipient": frappe.session.user,
        "is_read": 0,
    })


@frappe.whitelist()
def mark_all_read():
    """Mark all notifications for current user as read."""
    frappe.db.set_value(
        "Message Notification",
        {"recipient": frappe.session.user, "is_read": 0},
        "is_read", 1
    )

