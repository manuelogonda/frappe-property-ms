# Copyright (c) 2026, mnorg and contributors
# For license information, please see license.txt

# import frappe
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

OCCUPANCY_HOLDING_STATUS = "Active"


class Unit(Document):
	def autoname(self):
		# Named under the building when one is set, otherwise under the property.
		self.unit_code = (self.unit_code or "").strip().upper()
		self.name = f"{self.building}-{self.unit_code}" if self.building else f"{self.property}-{self.unit_code}"
		if frappe.db.exists("Unit", self.name):
			frappe.throw(_("Unit code {0} already exists here.").format(self.unit_code))

	def validate(self):
		self.clean_fields()
		self.validate_building_property()
		self.validate_floor()
		self.validate_amounts()
		self.validate_locked_fields()
		self.validate_occupancy()

	def clean_fields(self):
		self.unit_name = (self.unit_name or "").strip()
		self.unit_code = (self.unit_code or "").strip().upper()

	def validate_building_property(self):
		if not self.building:
			return
		building = frappe.db.get_value(
			"Building", self.building, ["property", "number_of_floors", "status"], as_dict=True
		)
		if self.property and self.property != building.property:
			frappe.throw(
				_("Building {0} belongs to property {1}, not {2}.").format(
					self.building, building.property, self.property
				)
			)
		self.property = building.property
		# Added: no new units in an inactive building.
		if self.is_new() and building.status == "Inactive":
			frappe.throw(_("Building {0} is Inactive. Add units to an active building.").format(self.building))
		self._building_floors = building.number_of_floors

	def validate_floor(self):
		floors = getattr(self, "_building_floors", None)
		if self.floor_number is None or not floors:
			return
		if not 0 <= self.floor_number <= floors:
			frappe.throw(
				_("Floor number must be between 0 and {0}, the number of floors in this building.").format(floors)
			)

	def validate_amounts(self):
		if flt(self.monthly_rent) <= 0:
			frappe.throw(_("Monthly rent must be greater than zero."))
		if flt(self.security_deposit) < 0:
			frappe.throw(_("Security deposit cannot be negative."))
		for field in ("bedrooms", "bathrooms"):
			if self.get(field) is not None and self.get(field) < 0:
				frappe.throw(_("{0} cannot be negative.").format(self.meta.get_label(field)))

	def validate_locked_fields(self):
		if self.is_new():
			return
		old = frappe.db.get_value("Unit", self.name, ["unit_code", "property", "building"], as_dict=True)
		# The unit code is part of the record name, which cannot change once created.
		if old.unit_code != self.unit_code:
			frappe.throw(_("The unit code cannot be changed once the unit is created."))
		# Once a unit has leases, it cannot move to another building or property.
		moved = old.property != self.property or old.building != self.building
		if moved and has_leases(self.name):
			frappe.throw(_("This unit has leases and cannot be moved to another building or property."))

	def validate_occupancy(self):
		# Occupancy follows the lease. A unit cannot be marked Occupied without an active lease,
		# and cannot be marked Vacant while one exists.
		active = has_active_lease(self.name)
		if self.status == "Occupied" and not active:
			frappe.throw(_("A unit can only be Occupied through an active lease."))
		if self.status == "Vacant" and active:
			frappe.throw(_("This unit has an active lease, so it cannot be Vacant."))

	def on_trash(self):
		if has_leases(self.name):
			frappe.throw(_("Cannot delete this unit because it has leases. Set its status to Inactive instead."))


def has_leases(unit_name):
	return bool(frappe.db.exists("Lease", {"unit": unit_name}))


def has_active_lease(unit_name):
	return bool(frappe.db.exists("Lease", {"unit": unit_name, "status": OCCUPANCY_HOLDING_STATUS}))
