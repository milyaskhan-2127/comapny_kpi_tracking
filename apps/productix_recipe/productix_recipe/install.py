"""
Productix Recipe after-install/uninstall hooks.

Delegates to the idempotent core provisioning (settings + module-def re-owning)
and invalidates the productix module registry so entitlement rows are synced.
"""


def after_install():
    from productix_core.install import after_install as core_provision

    core_provision()


def after_uninstall():
    from productix_core.install import after_uninstall as core_cleanup

    core_cleanup()