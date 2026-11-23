import frappe
from frappe import _
from property_management.portal import current_landlord


def get_context(context):
	landlord = current_landlord()
	context.no_cache = 1
	context.title = _("My requests")

	context.requests = frappe.get_list(
		"Portal Request",
		filters={"landlord": landlord.name},
		fields=["name", "request_type", "status", "has_payout_change", "creation", "reviewed_on", "applied_on"],
		order_by="creation desc",
		limit=50,
	)
