# Copyright (c) 2026, mnorg and contributors
# For license information, please see license.txt

# import frappe
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate

FINAL_STATUSES = ("Expired", "Terminated")


class ManagementAgreement(Document):
	def autoname(self):
		# Normalised before naming, so "ma-001" and "MA-001" are the same agreement.
		self.agreement_number = (self.agreement_number or "").strip().upper()
		if frappe.db.exists("Management Agreement", self.agreement_number):
			frappe.throw(_("Agreement number {0} already exists.").format(self.agreement_number))
		self.name = self.agreement_number

	def validate(self):
		self.validate_dates()
		self.validate_fee()
		self.validate_status_change()
		self.validate_single_active_agreement()
		self.validate_active_requirements()

	def validate_dates(self):
		# End date is optional. A blank end date means the agreement runs until it is terminated.
		if self.end_date and getdate(self.end_date) <= getdate(self.start_date):
			frappe.throw(_("End date must be later than the start date."))

	def validate_fee(self):
		if self.fee_structure == "Percentage":
			if not 0 < flt(self.management_fee_percent) <= 100:
				frappe.throw(_("Management fee must be above 0% and at most 100%."))
			self.fixed_management_fee = 0
		elif self.fee_structure == "Fixed Amount":
			if flt(self.fixed_management_fee) <= 0:
				frappe.throw(_("Fixed management fee must be greater than zero."))
			self.management_fee_percent = 0

	def validate_status_change(self):
		# Expired and Terminated agreements are final. Create a new agreement to continue.
		if self.is_new():
			return
		old_status = frappe.db.get_value("Management Agreement", self.name, "status")
		if old_status in FINAL_STATUSES and self.status != old_status:
			frappe.throw(
				_("Agreement {0} is {1} and cannot be changed. Create a new agreement instead.").format(
					self.name, old_status
				)
			)

	def validate_single_active_agreement(self):
		if self.status != "Active":
			return
		other = frappe.db.get_value(
			"Management Agreement",
			{"property": self.property, "status": "Active", "name": ["!=", self.name or ""]},
			"name",
		)
		if other:
			frappe.throw(_("Property {0} already has an active agreement: {1}.").format(self.property, other))

	def validate_active_requirements(self):
		if self.status == "Active" and not self.agreement_document:
			frappe.throw(_("Attach the signed agreement before setting the status to Active."))

	def on_trash(self):
		# Only drafts can be deleted. Active and past agreements are part of the record.
		if self.status != "Draft":
			frappe.throw(_("Only draft agreements can be deleted. Set the status to Terminated instead."))
		if frappe.db.exists("Lease", {"management_agreement": self.name}):
			frappe.throw(_("Cannot delete this agreement because leases use it."))
