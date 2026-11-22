import frappe
from frappe import _
from property_management.portal import current_tenant, submit_maintenance

CATEGORIES = ["Plumbing", "Electrical", "Structural", "Appliance", "Security", "Cleaning", "Other"]
PRIORITIES = ["Low", "Medium", "High"]  # Emergency is not offered to tenants; see decisions.


def get_context(context):
	tenant = current_tenant()
	context.no_cache = 1
	context.categories = CATEGORIES
	context.priorities = PRIORITIES
	context.error = None
	context.created = None

	if frappe.request.method == "POST":
		form = frappe.form_dict
		try:
			context.created = submit_maintenance(
				category=form.get("category"),
				priority=form.get("priority"),
				description=(form.get("description") or "").strip(),
			)
		except Exception as exc:
			context.error = str(exc)
	context.tenant_name = tenant.name
