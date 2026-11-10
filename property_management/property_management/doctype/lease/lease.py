# Copyright (c) 2026, mnorg and contributors
# For license information, please see license.txt

# import frappe
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, getdate

# Statuses that hold a unit. Decision pending: add "Pending Approval" to reserve units while approval is pending.
RESERVING_STATUSES = ("Active",)
# Once a lease reaches these, it cannot change back.
FINAL_STATUSES = ("Expired", "Terminated")
# Unit statuses that a lease may change. Maintenance and Inactive are set by people and are left alone.
LEASE_CONTROLLED_UNIT_STATUSES = ("Vacant", "Occupied", "Reserved")


class Lease(Document):
	def autoname(self):
		self.lease_number = (self.lease_number or "").strip().upper()
		if frappe.db.exists("Lease", self.lease_number):
			frappe.throw(_("Lease number {0} already exists.").format(self.lease_number))
		self.name = self.lease_number

	def validate(self):
		self.validate_dates()                  # Rule 2
		self.validate_amounts()                # Rules 3 and 4
		self.validate_payment_due_day()        # Rule 5
		self.validate_unit_belongs_to_property()  # Rule 6
		self.validate_management_agreement()   # Rule 8 (agreement must match the property)
		self.validate_status_change()
		self.validate_unit_overlap()           # Rule 9
		if self.status == "Active":
			self.validate_activation()         # Rules 7 and 8

	def validate_dates(self):
		if getdate(self.end_date) <= getdate(self.start_date):
			frappe.throw(_("End date must be later than the start date."))

	def validate_amounts(self):
		if flt(self.monthly_rent) <= 0:
			frappe.throw(_("Monthly rent must be greater than zero."))
		if flt(self.security_deposit) < 0:
			frappe.throw(_("Security deposit cannot be negative."))

	def validate_payment_due_day(self):
		if not 1 <= cint(self.payment_due_day) <= 28:
			frappe.throw(_("Payment due day must be between 1 and 28."))

	def validate_unit_belongs_to_property(self):
		unit_property = frappe.db.get_value("Unit", self.unit, "property")
		if unit_property != self.property:
			frappe.throw(
				_("Unit {0} belongs to property {1}, not {2}.").format(self.unit, unit_property, self.property)
			)

	def validate_management_agreement(self):
		agreement = frappe.db.get_value(
			"Management Agreement",
			self.management_agreement,
			["property", "status", "start_date", "end_date"],
			as_dict=True,
		)
		if agreement.property != self.property:
			frappe.throw(
				_("Management agreement {0} belongs to property {1}, not {2}.").format(
					self.management_agreement, agreement.property, self.property
				)
			)
		# Added: the lease must sit inside the agreement's term.
		if getdate(self.start_date) < getdate(agreement.start_date):
			frappe.throw(_("The lease cannot start before the management agreement starts."))
		if agreement.end_date and getdate(self.end_date) > getdate(agreement.end_date):
			frappe.throw(_("The lease cannot end after the management agreement ends."))

	def validate_status_change(self):
		if self.is_new():
			return
		old_status = frappe.db.get_value("Lease", self.name, "status")
		if old_status in FINAL_STATUSES and self.status != old_status:
			frappe.throw(
				_("Lease {0} is {1} and cannot be changed. Create a new lease instead.").format(
					self.name, old_status
				)
			)

	def validate_unit_overlap(self):
		if self.status not in RESERVING_STATUSES:
			return
		overlapping = frappe.get_all(
			"Lease",
			filters={
				"unit": self.unit,
				"status": ["in", list(RESERVING_STATUSES)],
				"name": ["!=", self.name or ""],
				"start_date": ["<=", self.end_date],
				"end_date": [">=", self.start_date],
			},
			pluck="name",
			limit=1,
		)
		if overlapping:
			frappe.throw(
				_("Unit {0} already has an overlapping lease: {1}.").format(self.unit, overlapping[0])
			)

	def validate_activation(self):
		# Rule 7: the tenant must be verified.
		tenant_status = frappe.db.get_value("Tenant", self.tenant, "status")
		if tenant_status != "Verified":
			frappe.throw(_("Tenant {0} must be Verified before the lease can be Active.").format(self.tenant))

		# Rule 8: the management agreement must be active.
		agreement_status = frappe.db.get_value("Management Agreement", self.management_agreement, "status")
		if agreement_status != "Active":
			frappe.throw(_("Management agreement {0} must be Active before the lease can be Active.").format(
				self.management_agreement))

		# Added: a signed lease must be on file before it is Active.
		if not self.lease_document:
			frappe.throw(_("Attach the signed lease before setting the status to Active."))

	def on_update(self):
		self.sync_unit_status()

	def sync_unit_status(self):
		# Keeps the unit's status in line with its leases.
		# Decision pending: Pending Approval does not change the unit yet.
		unit_status = frappe.db.get_value("Unit", self.unit, "status")
		if unit_status not in LEASE_CONTROLLED_UNIT_STATUSES:
			return

		if self.status == "Active" and unit_status != "Occupied":
			frappe.db.set_value("Unit", self.unit, "status", "Occupied")

		elif self.status in FINAL_STATUSES and unit_status == "Occupied":
			# Only vacate the unit if no other active lease still holds it.
			other_active = frappe.get_all(
				"Lease",
				filters={"unit": self.unit, "status": "Active", "name": ["!=", self.name]},
				limit=1,
			)
			if not other_active:
				frappe.db.set_value("Unit", self.unit, "status", "Vacant")

	def on_trash(self):
		# Only drafts can be deleted. Anything else is part of the record.
		if self.status != "Draft":
			frappe.throw(_("Only draft leases can be deleted. Set the status to Terminated instead."))
