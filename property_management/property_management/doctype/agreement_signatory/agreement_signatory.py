# Copyright (c) 2026, mnorg and contributors
# For license information, please see license.txt

# import frappe
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today


class AgreementSignatory(Document):
	def validate(self):
		self.validate_landlord_verified()
		self.validate_signing_date()

	def validate_landlord_verified(self):
		# Only a verified landlord can give authority to manage their property.
		status = frappe.db.get_value("Landlord", self.landlord, "status")
		if status != "Verified":
			frappe.throw(
				_("Landlord {0} must be Verified before signing (current status: {1}).").format(
					self.landlord, status
				)
			)

	def validate_signing_date(self):
		if self.signing_date and getdate(self.signing_date) > getdate(today()):
			frappe.throw(_("The signing date for {0} cannot be in the future.").format(self.landlord))
