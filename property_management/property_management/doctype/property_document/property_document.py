# Copyright (c) 2026, mnorg and contributors
# For license information, please see license.txt

# import frappe
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today


class PropertyDocument(Document):
	def validate(self):
		# An expired document is still a valid record, so warn rather than block.
		if self.expiry_date and getdate(self.expiry_date) < getdate(today()):
			frappe.msgprint(
				_("{0} expired on {1}.").format(self.document_type, self.expiry_date),
				indicator="orange",
				alert=True,
			)
