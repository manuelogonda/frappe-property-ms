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


def assert_own_invoice(invoice_name):
	customer = current_tenant().customer
	if not customer:
		frappe.throw(_("No customer is linked to this account."), frappe.PermissionError)
	owner = frappe.db.get_value("Sales Invoice", invoice_name, "customer")
	if owner != customer:
		frappe.throw(_("Record not found."), frappe.DoesNotExistError)
	return invoice_name


@frappe.whitelist()
def submit_maintenance(category, priority, description):
	tenant = current_tenant()

	# Unit and property come from the tenant's active lease, never from the form.
	lease = frappe.db.get_value(
		"Lease",
		{"tenant": tenant.name, "status": "Active"},
		["unit", "property"],
		as_dict=True,
	)
	if not lease:
		frappe.throw(_("You have no active lease, so you cannot raise a request."), frappe.PermissionError)

	# Emergency is reserved for staff, so a tenant cannot escalate a request to it.
	allowed_priorities = ("Low", "Medium", "High")
	if priority not in allowed_priorities:
		frappe.throw(_("Choose a priority of Low, Medium or High."), frappe.ValidationError)

	if not (description or "").strip():
		frappe.throw(_("Describe the problem before sending."), frappe.ValidationError)

	doc = frappe.get_doc({
		"doctype": "Maintenance Request",
		"tenant": tenant.name,
		"unit": lease.unit,
		"property": lease.property,
		"category": category,
		"priority": priority,
		"description": description.strip(),
		"status": "Open",
	})
	doc.insert()  # Runs as the tenant, so the create permission and the lease check both apply.
	return doc.name


def redirect_portal_user(login_manager):
	user = frappe.session.user
	if frappe.get_cached_value("User", user, "user_type") != "Website User":
		return
	if frappe.db.exists("Tenant", {"user": user}):
		frappe.local.response["home_page"] = "/tenant"

