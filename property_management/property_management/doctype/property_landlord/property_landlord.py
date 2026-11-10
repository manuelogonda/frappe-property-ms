# Copyright (c) 2026, mnorg and contributors
# For license information, please see license.txt

# import frappe
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

BLOCKED_LANDLORD_STATUSES = ("Rejected", "Inactive")


class PropertyLandlord(Document):
	def validate(self):
		self.validate_share()
		self.validate_landlord_status()

	def validate_share(self):
		# Each row must hold a share. The total across all rows is checked on the Property.
		share = flt(self.share_percentage)
		if not 0 < share <= 100:
			frappe.throw(_("Share for {0} must be above 0% and at most 100%.").format(self.landlord))

	def validate_landlord_status(self):
		# A rejected or inactive landlord cannot hold a share in any property.
		status = frappe.db.get_value("Landlord", self.landlord, "status")
		if status in BLOCKED_LANDLORD_STATUSES:
			frappe.throw(
				_("Landlord {0} is {1} and cannot be linked to a property.").format(self.landlord, status)
			)

