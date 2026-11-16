# Copyright (c) 2026, mnorg and contributors
# For license information, please see license.txt

# import frappe
import re

import frappe
from frappe import _
from frappe.model.document import Document

KRA_PIN_PATTERN = re.compile(r"^[A-Z]\d{9}[A-Z]$")


class Landlord(Document):
	def validate(self):
		self.clean_fields()
		self.validate_kra_pin()                 # Rule 23
		self.validate_unique_identifier()       # Rule 22
		self.validate_unique_email()            # Email unique when entered
		self.validate_verification()            # Rule 24
		self.validate_payout_method()           # Payout detail consistency

	def clean_fields(self):
		self.landlord_name = (self.landlord_name or "").strip()
		self.id_number_or_registration_number = (self.id_number_or_registration_number or "").strip()
		if self.email:
			self.email = self.email.strip().lower()

	def validate_kra_pin(self):
		if not self.kra_pin:
			return
		self.kra_pin = self.kra_pin.strip().upper()
		if not KRA_PIN_PATTERN.match(self.kra_pin):
			frappe.throw(_("KRA PIN must be one letter, nine digits, and one letter."))
		existing = frappe.db.get_value("Landlord", {"kra_pin": self.kra_pin, "name": ["!=", self.name or ""]}, "name")
		if existing:
			frappe.throw(_("KRA PIN {0} is already registered to landlord {1}.").format(self.kra_pin, existing))

	def validate_unique_identifier(self):
		existing = frappe.db.get_value(
			"Landlord",
			{"id_number_or_registration_number": self.id_number_or_registration_number, "name": ["!=", self.name or ""]},
			"name",
		)
		if existing:
			frappe.throw(_("A landlord with this ID or registration number already exists: {0}.").format(existing))

	def validate_unique_email(self):
		if not self.email:
			return
		existing = frappe.db.get_value("Landlord", {"email": self.email, "name": ["!=", self.name or ""]}, "name")
		if existing:
			frappe.throw(_("A landlord with this email already exists: {0}.").format(existing))

	def validate_verification(self):
		if self.status != "Verified":
			return
		missing = []
		if not self.kyc_documents:
			missing.append(_("KYC documents"))
		if not self.kra_pin:
			missing.append(_("KRA PIN"))
		if missing:
			frappe.throw(_("Before a landlord can be Verified, add: {0}.").format(", ".join(missing)))

	def validate_payout_method(self):
		# Only the chosen method's details are required; the other can be blank.
		if self.preferred_payment_method == "M-Pesa" and not self.mpesa_phone_number:
			frappe.throw(_("Enter the M-Pesa number for the preferred payment method."))
		if self.preferred_payment_method == "Bank Transfer" and not (self.bank_name and self.bank_account_number):
			frappe.throw(_("Enter the bank name and account number for the preferred payment method."))

	def on_trash(self):
		# Rule 25.
		linked = frappe.get_all("Property Landlord", filters={"landlord": self.name}, fields=["parent"], limit=1)
		if linked:
			frappe.throw(_("Cannot delete this landlord because it is linked to property {0}. "
						   "Set the status to Inactive instead.").format(linked[0].parent))
