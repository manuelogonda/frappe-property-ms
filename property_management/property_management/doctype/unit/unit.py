# Copyright (c) 2026, mnorg and contributors
# For license information, please see license.txt

# import frappe
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt

HOLDS_UNIT = "Active"  # Only Active leases hold a unit.


class Unit(Document):
	def autoname(self):
		# Rule 15: a unit is named under its building if it has one, otherwise under its property.
		self.unit_code = clean_code(self.unit_code)
		self.name = f"{self.building}-{self.unit_code}" if self.building else f"{self.property}-{self.unit_code}"
		if frappe.db.exists("Unit", self.name):
			frappe.throw(_("Unit code {0} already exists here.").format(self.unit_code))

	def validate(self):
		self.clean_fields()
		self.validate_building_belongs_to_property()   # Rule 16
		self.validate_floor()                           # Rule 17
		self.validate_amounts()                         # Rule 18
		self.validate_code_locked()                     # Rule 21
		self.validate_location_locked()                 # Rule 20
		self.validate_occupancy()                       # Rule 19

	def clean_fields(self):
		self.unit_name = (self.unit_name or "").strip()
		self.unit_code = clean_code(self.unit_code)

	def validate_building_belongs_to_property(self):
		if not self.building:
			return
		building = frappe.db.get_value(
			"Building", self.building, ["property", "number_of_floors", "status"], as_dict=True
		)
		if self.property and self.property != building.property:
			frappe.throw(_("Building {0} belongs to property {1}, not {2}.").format(
				self.building, building.property, self.property))
		self.property = building.property
		if self.is_new() and building.status == "Inactive":
			frappe.throw(_("Building {0} is Inactive. Add units to an active building.").format(self.building))
		self._building_floors = building.number_of_floors

	def validate_floor(self):
		floors = getattr(self, "_building_floors", None)
		if self.floor_number is None or not floors:
			return
		if not 0 <= cint(self.floor_number) <= cint(floors):
			frappe.throw(_("Floor number must be between 0 and {0}, the number of floors in this building.").format(floors))

	def validate_amounts(self):
		if flt(self.monthly_rent) <= 0:
			frappe.throw(_("Monthly rent must be greater than zero."))
		if flt(self.security_deposit) < 0:
			frappe.throw(_("Security deposit cannot be negative."))
		for field in ("bedrooms", "bathrooms"):
			if self.get(field) is not None and cint(self.get(field)) < 0:
				frappe.throw(_("{0} cannot be negative.").format(self.meta.get_label(field)))

	def validate_code_locked(self):
		# Rule 21: the code is part of the record name, so it cannot change.
		if self.is_new():
			return
		old_code = frappe.db.get_value("Unit", self.name, "unit_code")
		if old_code != self.unit_code:
			frappe.throw(_("The unit code cannot be changed once the unit is created."))

	def validate_location_locked(self):
		# Rule 20: a unit with leases cannot change building or property.
		if self.is_new():
			return
		old = frappe.db.get_value("Unit", self.name, ["property", "building"], as_dict=True)
		moved = old.property != self.property or old.building != self.building
		if moved and has_leases(self.name):
			frappe.throw(_("This unit has leases and cannot be moved to another building or property."))

	def validate_occupancy(self):
		# Rule 19: Occupied needs an active lease; Vacant is refused while one exists.
		if self.is_new():
			# A new unit has no leases yet, so Occupied is refused outright.
			if self.status == "Occupied":
				frappe.throw(_("A unit can only be Occupied through an active lease."))
			return
		active = has_active_lease(self.name)
		if self.status == "Occupied" and not active:
			frappe.throw(_("A unit can only be Occupied through an active lease."))
		if self.status == "Vacant" and active:
			frappe.throw(_("This unit has an active lease, so it cannot be Vacant."))

	def on_trash(self):
		# Rule 20: no delete with leases.
		if has_leases(self.name):
			frappe.throw(_("Cannot delete this unit because it has leases. Set its status to Inactive instead."))


def clean_code(value):
	return (value or "").strip().upper()


def has_leases(unit_name):
	return bool(frappe.db.exists("Lease", {"unit": unit_name}))


def has_active_lease(unit_name):
	return bool(frappe.db.exists("Lease", {"unit": unit_name, "status": HOLDS_UNIT}))
