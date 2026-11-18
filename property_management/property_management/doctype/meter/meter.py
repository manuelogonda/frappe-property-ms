# Copyright (c) 2026, mnorg and contributors
# For license information, please see license.txt

# import frappe
import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today

METER_PATTERN = re.compile(r"^[A-Z0-9\-/]{3,30}$")
ALLOWED_TYPES_BY_UTILITY = {
	"Electricity": ("Individual", "Sub-meter", "Bulk"),
	"Water": ("Individual", "Sub-meter", "Bulk"),
}


class Meter(Document):
	def validate(self):
		self.clean_fields()
		self.validate_unit_for_meter_type()
		self.validate_unit_belongs_to_property()
		self.validate_replacement()
		self.validate_status_change()

	def clean_fields(self):
		self.meter_number = (self.meter_number or "").strip().upper()
		if not METER_PATTERN.match(self.meter_number):
			frappe.throw(_("Meter number can use only letters, numbers, hyphens and slashes (3 to 30 characters)."))

	def validate_unit_for_meter_type(self):
		# A bulk meter serves the whole property, so it must not name a unit.
		# Individual and sub-meters must name the unit they serve.
		if self.meter_type == "Bulk" and self.unit:
			frappe.throw(_("A bulk meter serves the whole property. Remove the unit."))
		if self.meter_type in ("Individual", "Sub-meter") and not self.unit:
			frappe.throw(_("Choose the unit this {0} meter serves.").format(self.meter_type.lower()))

	def validate_unit_belongs_to_property(self):
		if not self.unit:
			return
		unit_property = frappe.db.get_value("Unit", self.unit, "property")
		if unit_property != self.property:
			frappe.throw(_("Unit {0} belongs to property {1}, not {2}.").format(self.unit, unit_property, self.property))

	def validate_replacement(self):
		# A replaced meter must name the meter that replaced it, and the replacement must be active.
		if self.status == "Replaced":
			if not self.replaced_by:
				frappe.throw(_("Name the meter that replaced this one."))
			if self.replaced_by == self.name:
				frappe.throw(_("A meter cannot replace itself."))
			replacement = frappe.db.get_value("Meter", self.replaced_by, ["utility_type", "property", "status"], as_dict=True)
			if not replacement:
				frappe.throw(_("The replacing meter {0} does not exist.").format(self.replaced_by))
			if replacement.utility_type != self.utility_type or replacement.property != self.property:
				frappe.throw(_("The replacing meter must be the same utility and property."))
			if not self.replaced_on:
				self.replaced_on = today()
		elif self.replaced_by:
			frappe.throw(_("Set the status to Replaced to link a replacement meter."))

	def validate_status_change(self):
		# Replaced and Inactive meters keep their history. Only an active meter can take readings.
		if self.is_new():
			return
		old = frappe.db.get_value("Meter", self.name, ["status", "unit", "meter_type"], as_dict=True)
		if old.status == "Replaced" and self.status != "Replaced":
			frappe.throw(_("A replaced meter cannot become active again. Add a new meter."))
		if old.unit != self.unit and frappe.db.exists("Meter Reading", {"meter": self.name}):
			frappe.throw(_("This meter has readings, so it cannot be moved to another unit. Replace it instead."))

	def on_trash(self):
		if frappe.db.exists("Meter Reading", {"meter": self.name}):
			frappe.throw(_("Cannot delete this meter because it has readings. Set its status to Inactive instead."))
		if frappe.db.exists("Meter", {"replaced_by": self.name}):
			frappe.throw(_("Cannot delete this meter because another meter replaced it."))
