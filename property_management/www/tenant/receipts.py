import frappe
from frappe import _
from property_management.portal import current_tenant


def get_context(context):
	tenant = current_tenant()
	context.no_cache = 1

	context.receipts = frappe.get_list(
		"Payment Entry",
		filters={"party": tenant.customer, "party_type": "Customer", "payment_type": "Receive", "docstatus": 1},
		fields=["name", "posting_date", "paid_amount", "mode_of_payment", "reference_no"],
		order_by="posting_date desc",
	)
	context.title = _("Your receipts")
