# Copyright (c) 2026, mnorg and contributors
# For license information, please see license.txt

# import frappe
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate

INVOICE_ITEM_PREFIX = "Utility"  # The invoice line uses the utility's item, set below.
UTILITY_ITEMS = {"Electricity": "Electricity", "Water": "Water"}
LOCKED = ("Invoiced", "Cancelled")


class UtilityBill(Document):
	def autoname(self):
		pass  # Named from the series in the JSON.

	def validate(self):
		self.validate_period()
		self.validate_locked()
		if self.status == "Draft":
			self.calculate()
		self.validate_allocations()

	def validate_period(self):
		if getdate(self.billing_end_date) <= getdate(self.billing_start_date):
			frappe.throw(_("Billing end date must be after the start date."))
		if getdate(self.billing_end_date) > getdate(frappe.utils.today()):
			frappe.throw(_("A bill cannot run past today. Wait for the period to end."))

		# The same meter and period must not be billed twice.
		clash = frappe.db.sql(
			"""
			select name from `tabUtility Bill`
			where meter = %(meter)s and name != %(name)s and status != 'Cancelled'
			  and billing_start_date <= %(end)s and billing_end_date >= %(start)s
				limit 1
			""",
			{"meter": self.meter, "name": self.name or "", "start": self.billing_start_date, "end": self.billing_end_date},
		)
		if clash:
			frappe.throw(_("This meter is already billed for an overlapping period in {0}.").format(clash[0][0]))

	def validate_locked(self):
		# Once invoiced, the bill cannot change. A cancelled bill is kept but not editable either.
		if self.is_new():
			return
		old_status = frappe.db.get_value("Utility Bill", self.name, "status")
		if old_status in LOCKED and self.status != old_status:
			frappe.throw(_("Bill {0} is {1} and cannot change.").format(self.name, old_status))

	def calculate(self):
		self.meter_status_check()
		opening, closing = self.find_readings()
		self.opening_reading = opening.name
		self.closing_reading = closing.name
		self.units_consumed = flt(closing.reading_value) - flt(opening.reading_value)

		periods = self.split_by_rate()
		self.set("periods", [])
		utility_charge = 0.0
		for p in periods:
			self.append("periods", p)
			utility_charge += flt(p["amount"])

		self.utility_charge = flt(utility_charge, 2)
		self.fixed_charge = flt(periods[0]["fixed"]) if periods else 0
		self.tax_treatment = periods[0]["tax"] if periods else None
		self.total = flt(self.utility_charge + self.fixed_charge, 2)
		self.status = "Calculated"

		self.resolve_tenancy()

	def meter_status_check(self):
		meter = frappe.db.get_value("Meter", self.meter, ["status", "property", "unit", "meter_type", "utility_type"], as_dict=True)
		if meter.status != "Active":
			frappe.throw(_("Meter {0} is {1}. Only active meters are billed.").format(self.meter, meter.status))
		self.property = meter.property
		self.unit = meter.unit
		self._utility = meter.utility_type
		self._meter_type = meter.meter_type

	def find_readings(self):
		# The opening reading is the last reading on or before the start; the closing is the last on or before the end.
		opening = frappe.db.get_value(
			"Meter Reading",
			{"meter": self.meter, "reading_date": ["<=", self.billing_start_date], "reading_type": "Actual"},
			["name", "reading_value", "reading_date", "billed"],
			order_by="reading_date desc",
			as_dict=True,
		)
		closing = frappe.db.get_value(
			"Meter Reading",
			{"meter": self.meter, "reading_date": ["<=", self.billing_end_date], "reading_type": "Actual"},
			["name", "reading_value", "reading_date"],
			order_by="reading_date desc",
			as_dict=True,
		)
		if not opening or not closing or opening.name == closing.name:
			frappe.throw(_("No actual readings cover this period. Take readings at both ends first."))
		if getdate(closing.reading_date) <= getdate(opening.reading_date):
			frappe.throw(_("The closing reading must be after the opening reading."))
		if flt(closing.reading_value) < flt(opening.reading_value):
			frappe.throw(_("The closing reading is lower than the opening reading. Check the readings."))
		return opening, closing

	def split_by_rate(self):
		# Each rate applies only to the days it is in force. A bill crossing a change is split by day.
		rates = frappe.get_all(
			"Utility Rate",
			filters={"utility_type": self._utility, "effective_from": ["<=", self.billing_end_date]},
			fields=["name", "effective_from", "effective_to", "rate_per_unit", "fixed_charge", "tax_treatment"],
			order_by="effective_from asc",
		)
		rates = [r for r in rates if not r.effective_to or getdate(r.effective_to) >= getdate(self.billing_start_date)]
		if not rates:
			frappe.throw(_("No {0} rate covers this period.").format(self._utility))

		total_days = (getdate(self.billing_end_date) - getdate(self.billing_start_date)).days + 1
		consumption = flt(self.units_consumed)
		periods = []
		for r in rates:
			start = max(getdate(r.effective_from), getdate(self.billing_start_date))
			end = min(getdate(r.effective_to) if r.effective_to else getdate(self.billing_end_date), getdate(self.billing_end_date))
			days = (end - start).days + 1
			share = days / total_days
			units = flt(consumption * share, 4)  # DECISION: consumption spread by day across the periods.
			periods.append({
				"period_start": start,
				"period_end": end,
				"utility_rate": r.name,
				"units": units,
				"rate_per_unit": flt(r.rate_per_unit),
				"amount": flt(units * flt(r.rate_per_unit), 2),
				"fixed": flt(r.fixed_charge) * share,
				"tax": r.tax_treatment,
			})
		return periods

	def resolve_tenancy(self):
		lease = frappe.db.get_value(
			"Lease",
			{"unit": self.unit, "status": "Active", "start_date": ["<=", self.billing_end_date]},
			["name", "tenant"],
			as_dict=True,
		)
		self.lease = lease.name if lease else None
		self.tenant = lease.tenant if lease else None

	def validate_allocations(self):
		if not self.get("allocations"):
			return
		total = sum(flt(a.share) for a in self.allocations)
		if abs(total - 100) > 0.001:
			frappe.throw(_("Allocation shares must total 100%. Current total is {0}%.").format(round(total, 2)))
		for a in self.allocations:
			a.amount = flt(self.total * flt(a.share) / 100, 2)
		# Rounding difference goes to the first allocation, so the total is exact.
		diff = flt(self.total) - sum(flt(a.amount) for a in self.allocations)
		if diff:
			self.allocations[0].amount = flt(self.allocations[0].amount + diff, 2)

	def on_submit(self):
		pass

	def create_invoice(self):
		"""Create one Sales Invoice for this bill. Called from a button or a scheduled job."""
		if self.sales_invoice:
			return self.sales_invoice
		if self.status != "Calculated":
			frappe.throw(_("Only a calculated bill can be invoiced."))
		if not self.tenant:
			frappe.throw(_("No active lease covers this unit, so there is no tenant to invoice."))

		customer = frappe.db.get_value("Tenant", self.tenant, "customer")
		if not customer:
			frappe.throw(_("Tenant {0} has no ERPNext customer.").format(self.tenant))

		item = UTILITY_ITEMS[self._utility]
		if not frappe.db.exists("Item", item):
			frappe.throw(_("Create the item {0} before invoicing utilities.").format(item))

		inv = frappe.get_doc({
			"doctype": "Sales Invoice",
			"customer": customer,
			"company": frappe.defaults.get_global_default("company"),
			"posting_date": getdate(frappe.utils.today()),
			"due_date": getdate(frappe.utils.today()),
			"property": self.property,
			"lease": self.lease,
			"lease_period_key": f"UB|{self.name}",
			"items": [{
				"item_code": item,
				"qty": 1,
				"rate": flt(self.total),
				"description": _("{0} {1} to {2}, meter {3}").format(
					self._utility, self.billing_start_date, self.billing_end_date, self.meter),
			}],
		})
		inv.insert(ignore_permissions=True)
		inv.submit()

		self.db_set({"sales_invoice": inv.name, "status": "Invoiced"}, update_modified=False)
		self.lock_readings()
		return inv.name

	def lock_readings(self):
		for name in (self.opening_reading, self.closing_reading):
			frappe.db.set_value("Meter Reading", name, {"billed": 1, "utility_bill": self.name}, update_modified=False)

	def on_cancel_invoice(self):
		# Called when the linked invoice is cancelled: release the readings so the period can be billed again.
		frappe.db.set_value("Utility Bill", self.name, "status", "Cancelled", update_modified=False)
		for name in (self.opening_reading, self.closing_reading):
			frappe.db.set_value("Meter Reading", name, {"billed": 0, "utility_bill": None}, update_modified=False)

	def on_trash(self):
		if self.status in LOCKED:
			frappe.throw(_("A bill that has been invoiced or cancelled cannot be deleted."))
