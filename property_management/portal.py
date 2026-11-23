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
	if frappe.db.exists("Landlord", {"user": user}):
		frappe.local.response["home_page"] = "/landlord"
	elif frappe.db.exists("Tenant", {"user": user}):
		frappe.local.response["home_page"] = "/tenant"


def current_landlord():
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Please log in to view your account."), frappe.PermissionError)
	landlord = frappe.db.get_value("Landlord", {"user": user}, ["name", "status"], as_dict=True)
	if not landlord or landlord.status != "Verified":
		frappe.throw(_("No active landlord account is linked to this login."), frappe.PermissionError)
	return landlord


def landlord_properties(landlord_name):
	return frappe.get_all("Property Landlord", filters={"landlord": landlord_name}, pluck="parent")


@frappe.whitelist()
def acknowledge_rent_review(review_name):
	landlord = current_landlord()
	review = frappe.db.get_value(
		"Lease Rent Review", review_name,
		["parent", "approved_status", "acknowledged_on"], as_dict=True,
	)
	if not review:
		frappe.throw(_("Record not found."), frappe.DoesNotExistError)
	lease_property = frappe.db.get_value("Lease", review.parent, "property")
	if lease_property not in landlord_properties(landlord.name):
		frappe.throw(_("Record not found."), frappe.DoesNotExistError)
	if review.approved_status != "Pending" or review.acknowledged_on:
		frappe.throw(_("This rent review has already been acknowledged."), frappe.ValidationError)
	frappe.db.set_value(
		"Lease Rent Review", review_name,
		{"acknowledged_by": frappe.session.user, "acknowledged_on": now_datetime()},
		update_modified=False,
	)
	return review_name


@frappe.whitelist()
def request_contact_change(changes, reason=None):
	landlord = current_landlord()
	if isinstance(changes, str):
		changes = frappe.parse_json(changes)
	allowed = CONTACT_FIELDS + PAYOUT_FIELDS
	clean = {k: str(v).strip() for k, v in (changes or {}).items() if k in allowed and str(v or "").strip()}
	if not clean:
		frappe.throw(_("Enter at least one change."), frappe.ValidationError)
	doc = frappe.get_doc({
		"doctype": "Portal Request",
		"request_type": "Contact Change",
		"landlord": landlord.name,
		"status": "Pending",
		"reason": reason,
		**clean,
	})
	doc.insert(ignore_permissions=True)
	return doc.name


