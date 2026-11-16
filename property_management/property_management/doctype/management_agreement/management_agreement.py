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
		# Rule 33: normalised before the record name is set.
		self.agreement_number = clean_number(self.agreement_number)
		self.name = self.agreement_number

	def validate(self):
		self.clean_fields()
		self.validate_dates()                  # Rule 34
		self.validate_fee()                    # Rule 35
		self.validate_status_change()          # Rule 37
		self.validate_single_active()          # Rule 36
		self.validate_active_requirements()    # Rule 38, document part
		self.validate_signatories()            # Rules 38 and 39

	def clean_fields(self):
		self.agreement_number = clean_number(self.agreement_number)

	def validate_dates(self):
		# Rule 34: a blank end date is open-ended, so only compare when one is entered.
		if self.end_date and getdate(self.end_date) <= getdate(self.start_date):
			frappe.throw(_("End date must be later than the start date."))

	def validate_fee(self):
		# Rule 35: the fee that does not apply is cleared, so the record holds one structure only.
		if self.fee_structure == "Percentage":
			if not 0 < flt(self.management_fee_percent) <= 100:
				frappe.throw(_("Management fee must be above 0% and at most 100%."))
			self.fixed_management_fee = 0
		elif self.fee_structure == "Fixed Amount":
			if flt(self.fixed_management_fee) <= 0:
				frappe.throw(_("Fixed management fee must be greater than zero."))
			self.management_fee_percent = 0

	def validate_status_change(self):
		# Rule 37: Expired and Terminated are final.
		if self.is_new():
			return
		old_status = frappe.db.get_value("Management Agreement", self.name, "status")
		if old_status in FINAL_STATUSES and self.status != old_status:
			frappe.throw(_("Agreement {0} is {1} and cannot be changed. Create a new agreement instead.").format(
				self.name, old_status))

	def validate_single_active(self):
		# Rule 36: one active agreement per property.
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

	def validate_signatories(self):
		rows = self.get("signatories") or []
		signed = [row.landlord for row in rows]

		# Rule 39: no duplicates.
		if len(signed) != len(set(signed)):
			frappe.throw(_("The same landlord cannot sign this agreement twice."))

		# Rule 39: each signatory must be a landlord of this property.
		property_landlords = set(frappe.get_all(
			"Property Landlord", filters={"parent": self.property}, pluck="landlord"
		))
		outside = set(signed) - property_landlords
		if outside:
			frappe.throw(_("These landlords are not on property {0}: {1}.").format(
				self.property, ", ".join(sorted(outside))))

		# Rule 39: each signatory must be Verified.
		for landlord in signed:
			status = frappe.db.get_value("Landlord", landlord, "status")
			if status != "Verified":
				frappe.throw(_("Landlord {0} must be Verified before signing (current status: {1}).").format(
					landlord, status))

		# Rule 39: a signature cannot be dated after the start date.
		for row in rows:
			if row.signing_date and getdate(row.signing_date) > getdate(self.start_date):
				frappe.throw(_("The signing date for {0} cannot be after the agreement's start date.").format(row.landlord))

		# Rule 38: an Active agreement needs every property landlord to have signed.
		if self.status == "Active":
			if not rows:
				frappe.throw(_("Add the signing landlords before setting the agreement to Active."))
			if any(not row.signing_date for row in rows):
				frappe.throw(_("Enter a signing date for every signatory before setting the agreement to Active."))
			missing = property_landlords - set(signed)
			if missing:
				frappe.throw(_("These landlords have not signed: {0}.").format(", ".join(sorted(missing))))

	def on_trash(self):
		# Only drafts can be deleted, and only if no lease uses the agreement.
		if self.status != "Draft":
			frappe.throw(_("Only draft agreements can be deleted. Set the status to Terminated instead."))
		if frappe.db.exists("Lease", {"management_agreement": self.name}):
			frappe.throw(_("Cannot delete this agreement because leases use it."))


def clean_number(value):
	return (value or "").strip().upper()
