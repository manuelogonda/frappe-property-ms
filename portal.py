import frappe
from frappe import _



def current_tenant():
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Please log in to view your account."), frappe.PermissionError)
	tenant = frappe.db.get_value(
		"Tenant", {"user": user}, ["name", "customer", "status"], as_dict=True
	)
	if not tenant or tenant.status != "Verified":
		frappe.throw(_("No active tenant account is linked to this login."), frappe.PermissionError)
	return tenant


def assert_own_invoice(invoice_name):
	customer = current_tenant().customer
	owner = frappe.db.get_value("Sales Invoice", invoice_name, "customer")
	if owner != customer:
		# Same message for "not yours" and "does not exist", so the URL reveals nothing.
		frappe.throw(_("Record not found."), frappe.DoesNotExistError)
	return invoice_name



def get_context(context):
	name = frappe.form_dict.get("name")
	if not name:
		frappe.throw("Choose an invoice.", frappe.DoesNotExistError)
	assert_own_invoice(name)
	context.invoice = frappe.get_doc("Sales Invoice", name)
