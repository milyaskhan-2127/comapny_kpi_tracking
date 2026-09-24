import frappe

from productix_core.modules.entitlement import require_module
from productix_core.modules.registry import app_for_module_key


@frappe.whitelist()
def trigger_module_action(module_key, action_name):
    """
    Generic dispatcher for module-specific actions.

    Core remains completely generic — it resolves the module_key to its
    owning app via the manifest registry, then calls the standard action
    endpoint on that app: `{app}.api.actions.{action_name}`.

    This allows the platform UI (e.g., AI Agent Log) to expose module-specific
    actions without hard-coding any business module dependencies.

    Args:
        module_key: The module key (e.g., "recipe", "kpi", "instruction")
        action_name: The action to invoke (e.g., "trigger_manual_scan")

    Returns:
        The result from the module's action handler, or an error dict.
    """
    # Verify the module is enabled on this site (entitlement enforcement)
    require_module(module_key)

    # Resolve module_key -> app via the manifest registry
    app = app_for_module_key(module_key)
    if not app:
        frappe.throw(
            frappe._("Module '{0}' is not installed on this site.").format(module_key),
            frappe.ValidationError,
        )

    # Construct the standard action path: {app}.api.actions.{action_name}
    method = f"{app}.api.actions.{action_name}"

    try:
        return frappe.call(method)
    except frappe.DoesNotExistError:
        frappe.throw(
            frappe._("Action '{0}' not implemented for module '{1}'.").format(
                action_name, module_key
            ),
            frappe.ValidationError,
        )
    except Exception as e:
        frappe.logger().error(
            f"Error calling module action {module_key}.{action_name}: {e!s}"
        )
        raise


@frappe.whitelist()
def get_module_actions(module_key):
    """
    Return available actions for a module.

    Modules can implement this by providing `api.actions.get_actions`
    returning a dict of {action_name: description}.
    """
    require_module(module_key)

    app = app_for_module_key(module_key)
    if not app:
        return {}

    method = f"{app}.api.actions.get_actions"
    try:
        return frappe.call(method) or {}
    except frappe.DoesNotExistError:
        return {}
    except Exception:
        frappe.logger().debug(f"No get_actions for {module_key}")
        return {}