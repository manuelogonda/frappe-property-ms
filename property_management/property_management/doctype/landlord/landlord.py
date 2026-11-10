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
		self.validate_kra_pin()
		self.validate_unique("id_number_or_registration_number", _("ID or registration number"))
		self.validate_unique("kra_pin", _("KRA PIN"))
		self.validate_unique("email", _("email"))
		self.validate_verification()

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

	def validate_unique(self, fieldname, label):
		# Only checks when a value is entered, so blank optional fields never collide.
		value = self.get(fieldname)
		if not value:
			return
		existing = frappe.db.get_value(
			"Landlord", {fieldname: value, "name": ["!=", self.name or ""]}, "name"
		)
		if existing:
			frappe.throw(_("A landlord with this {0} already exists: {1}.").format(label, existing))

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

	def on_trash(self):
		linked = frappe.get_all(
			"Property Landlord", filters={"landlord": self.name}, fields=["parent"], limit=1
		)
		if linked:
			frappe.throw(
				_("Cannot delete this landlord because it is linked to property {0}. "
				  "Set the status to Inactive instead.").format(linked[0].parent)
			)
