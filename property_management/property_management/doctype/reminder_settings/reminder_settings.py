# Copyright (c) 2026, mnorg and contributors
# For license information, please see license.txt

# import frappe
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint


class ReminderSettings(Document):
	def validate(self):
		grace = cint(self.grace_period_days)
		notices = [cint(self.notice_1_day), cint(self.notice_2_day), cint(self.notice_3_day)]
		if not (grace < notices[0] < notices[1] < notices[2]):
			frappe.throw(_("Notice days must come after the grace period and increase from notice 1 to notice 3."))
		if not 0 <= cint(self.quiet_start_hour) < cint(self.quiet_end_hour) <= 24:
			frappe.throw(_("Quiet hours must start before they end, between 0 and 24."))
		if not self.paybill_number:
			frappe.throw(_("Enter the M-Pesa Paybill number that tenants pay into."))
