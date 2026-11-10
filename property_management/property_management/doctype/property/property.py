# Copyright (c) 2026, mnorg and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

SHARE_TOTAL = 100.0
BLOCKED_LANDLORD_STATUSES = ("Rejected", "Inactive")


class Property(Document):
	def autoname(self):
		# Normalised before naming, so "wst-001" and "WST-001" are the same property.
		self.property_code = (self.property_code or "").strip().upper()
		self.name = self.property_code

	def validate(self):
		self.validate_landlords()
		self.validate_activation()

	def validate_landlords(self):
		rows = self.get("landlords") or []

		if not rows:
			return

		names = [row.landlord for row in rows]

		if len(names) != len(set(names)):
			frappe.throw(_("The same landlord appears more than once on this property."))

		for row in rows:
			if flt(row.share_percent) <= 0:
				frappe.throw(
					_("Share for {0} must be greater than zero.").format(row.landlord)
				)

			status = frappe.db.get_value("Landlord", row.landlord, "status")

			if status in BLOCKED_LANDLORD_STATUSES:
				frappe.throw(
					_("Landlord {0} is {1} and cannot be linked to a property.").format(
						row.landlord, status
					)
				)

		# Complete ownership requirements apply when activating the property.
		if self.status != "Active":
			return

		total = sum(flt(row.share_percent) for row in rows)

		if abs(total - SHARE_TOTAL) > 0.001:
			frappe.throw(
				_("Landlord shares must total 100%. Current total is {0}%.").format(
					round(total, 2)
				)
			)

		primaries = [row for row in rows if row.is_primary_contact]

		if len(primaries) != 1:
			frappe.throw(
				_("Select exactly one primary contact among the landlords.")
			)
	def validate_activation(self):
		if self.status != "Active":
			return
		if not self.get("landlords"):
			frappe.throw(_("A property must have at least one landlord before it can be Active."))
		if not frappe.db.exists("Management Agreement", {"property": self.name, "status": "Active"}):
			frappe.throw(_("A property needs an active Management Agreement before it can be Active."))

	def on_trash(self):
		# Lease is checked only once that DocType exists.
		blockers = []
		for doctype in ("Building", "Unit", "Management Agreement", "Lease"):
			if frappe.db.exists("DocType", doctype) and frappe.db.exists(doctype, {"property": self.name}):
				blockers.append(doctype)
		if blockers:
			frappe.throw(
				_("Cannot delete this property because it has {0}. Set its status to Inactive instead.").format(
					", ".join(blockers)
				)
			)
