import frappe
from frappe import _
from property_management.portal import current_tenant


def get_context(context):
	tenant = current_tenant()
	context.no_cache = 1

	context.requests = frappe.get_list(
		"Maintenance Request",
		filters={"tenant": tenant.name},
		fields=["name", "category", "priority", "status", "unit", "creation", "work_order"],
		order_by="creation desc",
	)
	context.title = _("My requests")
