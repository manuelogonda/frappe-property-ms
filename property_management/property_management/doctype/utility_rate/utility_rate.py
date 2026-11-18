# Copyright (c) 2026, mnorg and contributors
# For license information, please see license.txt

# import frappe
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate


class UtilityRate(Document):
	def validate(self):
		self.validate_amounts()
		self.validate_dates()
		self.validate_no_overlap()
		self.validate_not_used_on_bills()

	def validate_amounts(self):
		if flt(self.rate_per_unit) <= 0:
			frappe.throw(_("Rate per unit must be greater than zero."))
		if flt(self.fixed_charge) < 0:
			frappe.throw(_("Fixed charge cannot be negative."))

	def validate_dates(self):
		if self.effective_to and getdate(self.effective_to) < getdate(self.effective_from):
			frappe.throw(_("Effective To cannot be before Effective From."))

	def validate_no_overlap(self):
		# Two rates for one utility must never apply on the same day, or a bill would have two prices.
		start = getdate(self.effective_from)
		end = getdate(self.effective_to) if self.effective_to else getdate("9999-12-31")
		clash = frappe.db.sql(
			"""
			select name from `tabUtility Rate`
			where utility_type = %(utility)s
			  and name != %(name)s
			  and effective_from <= %(end)s
			  and (effective_to is null or effective_to >= %(start)s)
				limit 1
			""",
			{"utility": self.utility_type, "name": self.name or "", "start": start, "end": end},
		)
		if clash:
			frappe.throw(_("This overlaps the {0} rate {1}. Set the earlier rate's Effective To first.").format(
				self.utility_type, clash[0][0]))

	def validate_not_used_on_bills(self):
		# Once a bill has used this rate, the rate is part of that bill and cannot change.
		if self.is_new():
			return
		used = frappe.db.exists("Utility Bill", {"utility_rate": self.name, "docstatus": ["<", 2]})
		if not used:
			return
		old = frappe.db.get_value("Utility Rate", self.name,
								  ["rate_per_unit", "fixed_charge", "effective_from", "effective_to", "tax_treatment"], as_dict=True)
		changed = (
			flt(old.rate_per_unit) != flt(self.rate_per_unit)
			or flt(old.fixed_charge) != flt(self.fixed_charge)
			or getdate(old.effective_from) != getdate(self.effective_from)
			or str(old.effective_to) != str(self.effective_to)
			or old.tax_treatment != self.tax_treatment
		)
		if changed:
			frappe.throw(_("This rate has been used on a utility bill and cannot be changed. Create a new rate instead."))

	def on_trash(self):
		if frappe.db.exists("Utility Bill", {"utility_rate": self.name}):
			frappe.throw(_("Cannot delete this rate because a utility bill uses it. Set an Effective To date instead."))
