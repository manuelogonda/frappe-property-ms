import frappe
from property_management.portal import assert_own_invoice


def get_context(context):
	name = frappe.form_dict.get("name")
	if not name:
		frappe.throw("Choose an invoice.", frappe.DoesNotExistError)
	assert_own_invoice(name)
	context.invoice = frappe.get_doc("Sales Invoice", name)
