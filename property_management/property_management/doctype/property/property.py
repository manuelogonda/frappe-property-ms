# Copyright (c) 2026, mnorg and contributors
# For license information, please see license.txt

import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

SHARE_TOTAL = 100.0
PROPERTY_CODE_PATTERN = re.compile(r"^[A-Z0-9-]{2,20}$")  # Addition, not in the agreed rules. Confirm.


class Property(Document):
	def autoname(self):
		# Rule 3: the code is normalised before it becomes the record name.
		self.property_code = clean_code(self.property_code)
		self.name = self.property_code

	def validate(self):
		self.clean_fields()
		self.validate_code_locked()          # Rule 3
		self.validate_amenities()            # Rule 8
		self.validate_landlords()            # Rules 4 and 5
		self.validate_activation()           # Rule 7

	def clean_fields(self):
		self.property_name = (self.property_name or "").strip()
		self.county = (self.county or "").strip()
		self.town_area = (self.town_area or "").strip()
		self.property_code = clean_code(self.property_code)
		if not PROPERTY_CODE_PATTERN.match(self.property_code):
			frappe.throw(_("Property code can use only letters, numbers and hyphens (2 to 20 characters)."))

	def validate_code_locked(self):
		# Building and unit names are built from this code, so it cannot change once created.
		if not self.is_new() and self.property_code != self.name:
			frappe.throw(_("The property code cannot be changed once the property is created."))

	def validate_amenities(self):
		names = [row.amenity for row in self.get("amenities") or []]
		if len(names) != len(set(names)):
			frappe.throw(_("The same amenity appears more than once on this property."))

	def validate_landlords(self):
		# Per-row checks (share above zero, landlord not Rejected or Inactive) run in Property Landlord.
		rows = self.get("landlords") or []
		if not rows:
			return

		names = [row.landlord for row in rows]
		if len(names) != len(set(names)):
			frappe.throw(_("The same landlord appears more than once on this property."))

		total = sum(flt(row.share_percentage) for row in rows)
		if abs(total - SHARE_TOTAL) > 0.001:
			frappe.throw(_("Landlord shares must total 100%. Current total is {0}%.").format(round(total, 2)))

		primaries = [row for row in rows if row.is_primary_contact]
		if len(primaries) != 1:
			frappe.throw(_("Select exactly one primary contact among the landlords."))

	def validate_activation(self):
		if self.status != "Active":
			return
		if not self.get("landlords"):
			frappe.throw(_("A property must have at least one landlord before it can be Active."))
		if not frappe.db.exists("Management Agreement", {"property": self.name, "status": "Active"}):
			frappe.throw(_("A property needs an active Management Agreement before it can be Active."))

	def on_trash(self):
		# Rule 9: nothing linked may remain.
		blockers = [
			doctype for doctype in ("Building", "Unit", "Management Agreement", "Lease")
			if frappe.db.exists(doctype, {"property": self.name})
		]
		if blockers:
			frappe.throw(
				_("Cannot delete this property because it has {0}. Set its status to Inactive instead.").format(
					", ".join(blockers)
				)
			)


def clean_code(value):
	return (value or "").strip().upper()
