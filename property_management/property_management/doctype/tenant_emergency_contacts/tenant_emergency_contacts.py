# Copyright (c) 2026, mnorg and contributors
# For license information, please see license.txt

# import frappe
import frappe
from frappe import _
from frappe.model.document import Document


class TenantEmergencyContact(Document):
	def validate(self):
		self.contact_name = (self.contact_name or "").strip()
		if not self.contact_name:
			frappe.throw(_("Enter the emergency contact's name."))
