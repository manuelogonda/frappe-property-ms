# Copyright (c) 2026, mnorg and contributors
# For license information, please see license.txt

# import frappe
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint


class Building(Document):
	def autoname(self):
		# Rule 10 and 11: normalised before the record name is built, so "a" and "A" are one building.
		self.building_code = clean_code(self.building_code)
		self.name = f"{self.property}-{self.building_code}"

	def validate(self):
		self.clean_fields()
		self.validate_building_code_unique()   # Rule 10
		self.validate_floors()                 # Rule 12
		self.validate_locked_fields()          # Rule 13

	def clean_fields(self):
		self.building_name = (self.building_name or "").strip()
		self.building_code = clean_code(self.building_code)

	def validate_building_code_unique(self):
		# The name already enforces uniqueness. This gives a clearer message.
		duplicate = frappe.db.exists(
			"Building",
			{"property": self.property, "building_code": self.building_code, "name": ["!=", self.name or ""]},
		)
		if duplicate:
			frappe.throw(_("Building code {0} is already used in property {1}.").format(self.building_code, self.property))

	def validate_floors(self):
		if self.number_of_floors is not None and cint(self.number_of_floors) < 1:
			frappe.throw(_("Number of floors must be at least 1."))

	def validate_locked_fields(self):
		# Unit names are built from this building, so the property and code cannot change once units exist.
		if self.is_new() or not units_exist(self.name):
			return
		old = frappe.db.get_value("Building", self.name, ["property", "building_code"], as_dict=True)
		if old.property != self.property:
			frappe.throw(_("This building has units and cannot be moved to another property."))
		if old.building_code != self.building_code:
			frappe.throw(_("This building has units, so its building code cannot be changed."))

	def on_trash(self):
		# Rule 14.
		if units_exist(self.name):
			frappe.throw(_("Cannot delete this building because it has units. Set its status to Inactive instead."))


def clean_code(value):
	return (value or "").strip().upper()


def units_exist(building_name):
	return bool(frappe.db.exists("Unit", {"building": building_name}))
