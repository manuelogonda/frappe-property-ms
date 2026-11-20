# Copyright (c) 2026, mnorg and contributors
# For license information, please see license.txt

# import frappe
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today

CLOSED_STATUSES = ("Completed", "Closed", "Cancelled")
EDITABLE_BY_TENANT = False


class MaintenanceRequest(Document):
	def validate(self):
		self.validate_unit_belongs_to_property()
		self.validate_reporter()
		self.validate_tenant_lease()
		self.validate_closed_is_final()
		self.validate_feedback()

	def validate_unit_belongs_to_property(self):
		unit_property = frappe.db.get_value("Unit", self.unit, "property")
		if unit_property != self.property:
			frappe.throw(_("Unit {0} belongs to property {1}, not {2}.").format(self.unit, unit_property, self.property))

	def validate_reporter(self):
		# A request must come from a tenant on the unit, or from staff.
		if self.reported_by_staff:
			self.tenant = None
			return
		if not self.tenant:
			frappe.throw(_("Choose the tenant reporting the problem, or mark the request as reported by staff."))

	def validate_tenant_lease(self):
		# Rule: a tenant can raise a request only for a unit they hold an active lease on.
		if self.reported_by_staff or not self.tenant or self.is_new() is False and self.status == "Completed":
			return
		if not frappe.db.exists("Lease", {"tenant": self.tenant, "unit": self.unit, "status": "Active"}):
			frappe.throw(_("Tenant {0} has no active lease on unit {1}.").format(self.tenant, self.unit))

	def validate_closed_is_final(self):
		if self.is_new():
			return
		old_status = frappe.db.get_value("Maintenance Request", self.name, "status")
		if old_status in CLOSED_STATUSES and self.status != old_status:
			frappe.throw(_("Request {0} is {1} and cannot be changed.").format(self.name, old_status))

	def validate_feedback(self):
		# Feedback and rating are recorded only after the work is completed.
		if (self.tenant_rating or self.tenant_feedback) and self.status != "Completed":
			frappe.throw(_("Tenant feedback can be recorded only after the work is completed."))

	def on_update(self):
		self.notify_status_change()

	def on_trash(self):
		if self.status != "Open":
			frappe.throw(_("Only open requests can be deleted. Set the status to Cancelled instead."))

		def notify_status_change(self):
			if self.is_new() or not self.tenant:
				return  # Staff-reported requests have no tenant to update.

		old_status = frappe.db.get_value("Maintenance Request", self.name, "status")
		if old_status == self.status:
			return  # No change, so nothing to send.

		key = f"MU|{self.name}|{self.status}"
		if frappe.db.exists("Reminder Log", {"reminder_key": key}):
			return  # Already sent for this status.

		tenant = frappe.db.get_value("Tenant", self.tenant, ["tenant_name", "email"], as_dict=True)
		message = _("Dear {0}, your maintenance request {1} for unit {2} is now {3}.").format(
			tenant.tenant_name, self.name, self.unit, self.status)
		subject = _("Maintenance update: {0}").format(self.name)

		if tenant.email:
			frappe.sendmail(recipients=[tenant.email], subject=subject, message=message)

		log_notification(key, "Maintenance Update", self.name, self.tenant,
						 "Email", tenant.email, "Sent")


	def notify_status_change(self):
		if self.is_new() or not self.tenant:
			return  # Staff-reported requests have no tenant to update.

		old_status = frappe.db.get_value("Maintenance Request", self.name, "status")
		if old_status == self.status:
			return  # No change, so nothing to send.

		key = f"MU|{self.name}|{self.status}"
		if frappe.db.exists("Reminder Log", {"reminder_key": key}):
			return  # Already sent for this status.

		tenant = frappe.db.get_value("Tenant", self.tenant, ["tenant_name", "email"], as_dict=True)
		message = _("Dear {0}, your maintenance request {1} for unit {2} is now {3}.").format(
			tenant.tenant_name, self.name, self.unit, self.status)
		subject = _("Maintenance update: {0}").format(self.name)

		if tenant.email:
			frappe.sendmail(recipients=[tenant.email], subject=subject, message=message)

		log_notification(key, "Maintenance Update", self.name, self.tenant,
						 "Email", tenant.email, "Sent")
