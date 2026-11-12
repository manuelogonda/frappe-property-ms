# Copyright (c) 2026, mnorg and contributors
# For license information, please see license.txt

# import frappe
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, getdate

from property_management import rent

FINAL_STATUSES = ("Expired", "Terminated")
LEASE_CONTROLLED_UNIT_STATUSES = ("Vacant", "Occupied", "Reserved")
TERM_FIELDS = ("start_date", "end_date", "payment_frequency", "payment_due_day")


class Lease(Document):
	def autoname(self):
		self.lease_number = (self.lease_number or "").strip().upper()
		if frappe.db.exists("Lease", self.lease_number):
			frappe.throw(_("Lease number {0} already exists.").format(self.lease_number))
		self.name = self.lease_number

	def validate(self):
		self.validate_dates()
		self.validate_amounts()
		self.validate_unit_belongs_to_property()
		self.validate_management_agreement()
		self.validate_status_change()
		self.validate_unit_overlap()
		if self.status == "Active":
			self.validate_activation()
		self.validate_rent_change()
		self.validate_schedule()
		self.validate_termination()
		self.warn_unsupported_charges()

	def validate_dates(self):
		if self.end_date and getdate(self.end_date) <= getdate(self.start_date):
			frappe.throw(_("End date must be later than the start date."))
		if not 1 <= cint(self.payment_due_day) <= 28:
			frappe.throw(_("Payment due day must be between 1 and 28."))

	def validate_amounts(self):
		if flt(self.rent_amount) <= 0:
			frappe.throw(_("Rent amount must be greater than zero."))
		if flt(self.security_deposit) < 0:
			frappe.throw(_("Security deposit cannot be negative."))

	def validate_unit_belongs_to_property(self):
		unit_property = frappe.db.get_value("Unit", self.unit, "property")
		if unit_property != self.property:
			frappe.throw(_("Unit {0} belongs to property {1}, not {2}.").format(self.unit, unit_property, self.property))

	def validate_management_agreement(self):
		agreement = frappe.db.get_value(
			"Management Agreement", self.management_agreement,
			["property", "start_date", "end_date"], as_dict=True,
		)
		if agreement.property != self.property:
			frappe.throw(_("Management agreement {0} belongs to property {1}, not {2}.").format(
				self.management_agreement, agreement.property, self.property))
		if getdate(self.start_date) < getdate(agreement.start_date):
			frappe.throw(_("The lease cannot start before the management agreement starts."))
		if agreement.end_date and self.end_date and getdate(self.end_date) > getdate(agreement.end_date):
			frappe.throw(_("The lease cannot end after the management agreement ends."))
		if agreement.end_date and not self.end_date:
			frappe.throw(_("The management agreement has an end date, so this lease needs one too."))

	def validate_status_change(self):
		if self.is_new():
			return
		old_status = frappe.db.get_value("Lease", self.name, "status")
		if old_status in FINAL_STATUSES and self.status != old_status:
			frappe.throw(_("Lease {0} is {1} and cannot be changed. Create a new lease instead.").format(self.name, old_status))

	def validate_unit_overlap(self):
		# A blank end date means open-ended, so it overlaps any later lease.
		clash = frappe.db.sql(
			"""
			select name from `tabLease`
			where unit = %(unit)s and name != %(name)s and status = 'Active'
			  and start_date <= %(end)s
			  and (end_date is null or end_date >= %(start)s)
				limit 1
			""",
			{
				"unit": self.unit,
				"name": self.name or "",
				"start": self.start_date,
				"end": self.end_date or "9999-12-31",
			},
		)
		if self.status == "Active" and clash:
			frappe.throw(_("Unit {0} already has an overlapping active lease: {1}.").format(self.unit, clash[0][0]))

	def validate_activation(self):
		if frappe.db.get_value("Tenant", self.tenant, "status") != "Verified":
			frappe.throw(_("Tenant {0} must be Verified before the lease can be Active.").format(self.tenant))
		if frappe.db.get_value("Management Agreement", self.management_agreement, "status") != "Active":
			frappe.throw(_("Management agreement {0} must be Active before the lease can be Active.").format(self.management_agreement))
		if not self.lease_document:
			frappe.throw(_("Attach the signed lease before setting the status to Active."))

	def validate_rent_change(self):
		# Once active, rent changes only through an approved rent review.
		if self.is_new():
			return
		old = frappe.db.get_value("Lease", self.name, ["rent_amount", "status"], as_dict=True)
		if old.status != "Active" or flt(old.rent_amount) == flt(self.rent_amount):
			return

		matches = [
			r for r in self.get("rent_reviews") or []
			if r.approved_status == "Approved" and flt(r.approved_rent) == flt(self.rent_amount) and r.effective_date
		]
		if not matches:
			frappe.throw(_("Rent on an active lease can change only through an approved rent review."))
		self._rent_effective = max(getdate(r.effective_date) for r in matches)

	def validate_schedule(self):
		effective = getattr(self, "_rent_effective", None)
		if effective:
			rent.rebuild_from(self, effective)
			return

		if self.status != "Active":
			return
		if not self.get("rent_schedule"):
			self.set("rent_schedule", rent.build_schedule(self))
			return
		if self.is_new() or not terms_changed(self):
			return
		if rent.has_invoiced_lines(self):
			frappe.throw(_("Billing terms cannot change after invoices exist. Use a rent review or a new lease."))
		self.set("rent_schedule", rent.build_schedule(self))

	def validate_termination(self):
		if self.status != "Terminated":
			return
		if not self.termination_date:
			frappe.throw(_("Enter the termination date before terminating a lease."))
		if getdate(self.termination_date) < getdate(self.start_date):
			frappe.throw(_("Termination date cannot be before the start date."))
		rent.cancel_after(self, self.termination_date)

	def warn_unsupported_charges(self):
		skipped = [
			c.charge_type for c in self.get("lease_charges") or []
			if c.frequency not in rent.AUTO_CHARGE_FREQUENCIES
		]
		if skipped:
			frappe.msgprint(
				_("These charges are not invoiced automatically yet: {0}.").format(", ".join(skipped)),
				indicator="orange",
				alert=True,
			)

	def on_update(self):
		self.sync_unit_status()

	def sync_unit_status(self):
		unit_status = frappe.db.get_value("Unit", self.unit, "status")
		if unit_status not in LEASE_CONTROLLED_UNIT_STATUSES:
			return
		if self.status == "Active" and unit_status != "Occupied":
			frappe.db.set_value("Unit", self.unit, "status", "Occupied")
		elif self.status in FINAL_STATUSES and unit_status == "Occupied":
			other_active = frappe.db.exists("Lease", {"unit": self.unit, "status": "Active", "name": ["!=", self.name]})
			if not other_active:
				frappe.db.set_value("Unit", self.unit, "status", "Vacant")

	def on_trash(self):
		if self.status != "Draft":
			frappe.throw(_("Only draft leases can be deleted. Set the status to Terminated instead."))


def terms_changed(lease):
	old = frappe.db.get_value("Lease", lease.name, TERM_FIELDS, as_dict=True)
	return any(str(old[f]) != str(lease.get(f)) for f in TERM_FIELDS)
