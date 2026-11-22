# Copyright (c) 2026, mnorg and contributors
# For license information, please see license.txt

# import frappe
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

APPROVER_ROLE = "Accounts Manager"


class LeaseRentReview(Document):
	def validate(self):
		if self.is_new():
			return
		old_status = frappe.db.get_value("Lease Rent Review", self.name, "approved_status")
		if self.approved_status == "Approved" and old_status != "Approved":
			if APPROVER_ROLE not in frappe.get_roles() and "System Manager" not in frappe.get_roles():
				frappe.throw(_("Only an Accounts Manager can approve a rent review."))
			if not self.acknowledged_on:
				frappe.throw(_("The landlord must acknowledge this rent review before it is approved."))
			self.approved_by = frappe.session.user
			self.approved_on = now_datetime()
