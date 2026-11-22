# Copyright (c) 2026, mnorg and contributors
# For license information, please see license.txt

# import frappe
import frappe
from frappe import _
from frappe.utils import now_datetime

PAYOUT_FIELDS = ("mpesa_phone_number", "bank_name", "bank_branch", "bank_account_name", "bank_account_number")
CONTACT_FIELDS = ("phone", "email", "address")


def validate(doc, method=None):
	doc.has_payout_change = 1 if any(doc.get(f) for f in PAYOUT_FIELDS) else 0

	if doc.is_new():
		return

	old_status = frappe.db.get_value("Portal Request", doc.name, "status")
	if old_status == doc.status:
		return

	roles = frappe.get_roles()

	if doc.status in ("Approved", "Rejected"):
		if "Property Manager" not in roles and "System Manager" not in roles:
			frappe.throw(_("Only a Property Manager can approve or reject a change request."))
		if old_status != "Pending":
			frappe.throw(_("Only a pending request can be approved or rejected."))
		doc.reviewed_by = frappe.session.user
		doc.reviewed_on = now_datetime()

	elif doc.status == "Applied":
		if "Accounts Manager" not in roles and "System Manager" not in roles:
			frappe.throw(_("Only an Accounts Manager can apply a change."))
		if old_status != "Approved":
			frappe.throw(_("Only an approved request can be applied."))
		doc.applied_by = frappe.session.user
		doc.applied_on = now_datetime()
		apply_to_landlord(doc)


def apply_to_landlord(doc):
	values = {f: doc.get(f) for f in CONTACT_FIELDS + PAYOUT_FIELDS if doc.get(f)}
	if values:
		frappe.db.set_value("Landlord", doc.landlord, values, update_modified=True)
