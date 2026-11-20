import frappe
from frappe.utils import flt
from property_management.portal import current_tenant


def get_context(context):
	tenant = current_tenant()
	context.tenant_name = tenant.name

	context.leases = frappe.get_list(
		"Lease",
		filters={"tenant": tenant.name},
		fields=["name", "unit", "property", "status", "rent_amount", "start_date", "end_date"],
		order_by="start_date desc",
	)

	# Balance comes from ERPNext's own outstanding figures, not recalculated here.
	open_invoices = frappe.get_list(
		"Sales Invoice",
		filters={"customer": tenant.customer, "docstatus": 1, "outstanding_amount": [">", 0]},
		fields=["name", "due_date", "outstanding_amount"],
		order_by="due_date asc",
	)
	context.balance = sum(flt(i.outstanding_amount) for i in open_invoices)
	context.open_invoices = open_invoices
