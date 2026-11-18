# Copyright (c) 2026, mnorg and contributors
# For license information, please see license.txt

# import frappe
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, today


class MeterReading(Document):
	def validate(self):
		self.validate_meter_active()
		self.validate_not_billed()
		self.validate_not_future()
		self.validate_one_per_day()
		self.set_previous_and_consumption()
		self.validate_consumption()

	def validate_meter_active(self):
		status = frappe.db.get_value("Meter", self.meter, "status")
		if status != "Active":
			frappe.throw(_("Meter {0} is {1}. Readings can be taken only from active meters.").format(self.meter, status))

	def validate_not_billed(self):
		# A billed reading is part of a bill. Changing it would change a bill.
		if self.is_new():
			return
		if frappe.db.get_value("Meter Reading", self.name, "billed"):
			frappe.throw(_("This reading has been billed and cannot be changed."))

	def validate_not_future(self):
		if getdate(self.reading_date) > getdate(today()):
			frappe.throw(_("The reading date cannot be in the future."))

	def validate_one_per_day(self):
		# Two readings on the same day make consumption ambiguous.
		clash = frappe.db.get_value(
			"Meter Reading",
			{"meter": self.meter, "reading_date": self.reading_date, "name": ["!=", self.name or ""]},
			"name",
		)
		if clash:
			frappe.throw(_("Meter {0} already has a reading on {1}: {2}.").format(self.meter, self.reading_date, clash))

	def set_previous_and_consumption(self):
		# The previous reading is the latest reading before this date, for the same meter.
		previous = frappe.db.get_value(
			"Meter Reading",
			{"meter": self.meter, "reading_date": ["<", self.reading_date]},
			["reading_value", "reading_date"],
			order_by="reading_date desc",
			as_dict=True,
		)
		self.previous_reading = flt(previous.reading_value) if previous else None
		self.consumed_units = flt(self.reading_value) - flt(self.previous_reading) if previous else 0

	def validate_consumption(self):
		if self.previous_reading is None:
			return  # The first reading of a meter sets the baseline. There is nothing to compare.
		if flt(self.reading_value) < flt(self.previous_reading):
			# A lower value means a meter reset, a fault, or a keying error. Refuse it unless
			# the meter was replaced, which is recorded on the Meter itself.
			if frappe.db.get_value("Meter", self.meter, "status") != "Replaced":
				frappe.throw(_("Reading {0} is lower than the previous reading {1}. Check the value, or replace the meter.").format(
					self.reading_value, self.previous_reading))

	def on_trash(self):
		if frappe.db.get_value("Meter Reading", self.name, "billed"):
			frappe.throw(_("A billed reading cannot be deleted."))
		# Later readings depend on this one, so only the most recent reading may be removed.
		later = frappe.db.exists("Meter Reading", {"meter": self.meter, "reading_date": [">", self.reading_date]})
		if later:
			frappe.throw(_("A later reading exists for this meter. Delete the later readings first."))

	def before_save(self):
		frappe.db.set_value("Meter", self.meter, "last_reading_date", self.reading_date, update_modified=False)
