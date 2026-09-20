"""
Production Order workflow utilities for Productix.
Hooks on Work Order (ERPNext native) — minimal, since we use
custom Production Order DocType for main logic.
"""
import frappe


def on_work_order_submit(doc, method):
    """Hook on ERPNext Work Order submit (if used alongside custom Production Order)."""
    pass


def on_work_order_cancel(doc, method):
    """Hook on ERPNext Work Order cancel."""
    pass
