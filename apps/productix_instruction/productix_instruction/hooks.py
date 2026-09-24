from __future__ import unicode_literals
from frappe import _

app_name = "productix_instruction"
app_title = "Productix Instruction Room"
app_publisher = "TechoHub"
app_description = "Productix Instruction Room — in-app announcements and read tracking for factory staff (modularized from the monolithic productix app)"
app_email = "support@techohub.net"
app_license = "MIT"
app_version = "1.0.0"

after_install = "productix_instruction.install.after_install"
after_uninstall = "productix_instruction.install.after_uninstall"

# -----------------------------------------------------------------
# Apps (installed alongside this app)
# -----------------------------------------------------------------
required_apps = ["erpnext", "productix_core"]

# -----------------------------------------------------------------
# Ignore links on delete (allow deleting users without foreign key locks
# on notifications — these doctypes are owned by this app)
# -----------------------------------------------------------------
ignore_links_on_delete = [
    "Message Notification",
    "Instruction Message",
]

# -----------------------------------------------------------------
# Whitelisted API Methods (accessible via /api/method/...)
# -----------------------------------------------------------------
# These are auto-discovered from @frappe.whitelist() decorators.
# Listed here for documentation:
#   productix_instruction.instruction_room.doctype.instruction_message.instruction_message.clear_all_messages
#   productix_instruction.instruction_room.doctype.instruction_message.instruction_message.get_unread_count
#   productix_instruction.instruction_room.doctype.instruction_message.instruction_message.mark_all_read