# Copyright (c) 2026, mnorg and contributors
# For license information, please see license.txt

# import frappe
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime

APPROVAL_THRESHOLD = 50000  # DECISION: estimates above this need approval. Placeholder until confirmed.
LOCKED_STATUSES = ("Completed", "Cancelled")
MAINTENANCE_EXPENSE = "Maintenance Expense"


class WorkOrder(Document):
	def autoname(self):
		# The name is the work order number.
		self.name = frappe.generate_hash(length=0) if False else None  # placeholder replaced below

	def validate(self):
		self.validate_request_link()
		self.validate_assignment()
		self.validate_locked_after_completion()
		self.calculate_total()
		self.validate_approval()
		self.validate_cost_bearer()
		self.validate_status_flow()

	def validate_request_link(self):
		if not self.maintenance_request:
			return
		req = frappe.db.get_value("Maintenance Request", self.maintenance_request,
								  ["property", "unit", "status"], as_dict=True)
		if req.status in ("Completed", "Closed", "Cancelled"):
			frappe.throw(_("Maintenance request {0} is {1} and cannot take new work.").format(
				self.maintenance_request, req.status))
		if req.property != self.property or req.unit != self.unit:
			frappe.throw(_("The property and unit must match the maintenance request."))

	def validate_assignment(self):
		if self.assigned_to_type == "Internal Staff" and not self.staff_user:
			frappe.throw(_("Choose the staff member assigned to this work."))
		if self.assigned_to_type == "Contractor" and not self.contractor:
			frappe.throw(_("Choose the contractor assigned to this work."))
		if flt(self.estimate) <= 0:
			frappe.throw(_("Enter an estimate before the work is assigned."))

	def validate_locked_after_completion(self):
		if self.is_new():
			return
		old = frappe.db.get_value("Work Order", self.name, ["status", "total_cost", "cost_bearer"], as_dict=True)
		if old.status in LOCKED_STATUSES and self.status != old.status:
			frappe.throw(_("Work order {0} is {1} and cannot change.").format(self.name, old.status))
		if old.status == "Completed" and (flt(old.total_cost) != flt(self.total_cost) or old.cost_bearer != self.cost_bearer):
			frappe.throw(_("Costs and cost bearer cannot change after completion."))

	def calculate_total(self):
		materials = sum(flt(m.quantity) * flt(m.unit_cost) for m in self.get("materials") or [])
		for m in self.get("materials") or []:
			m.amount = flt(m.quantity) * flt(m.unit_cost)
		self.total_cost = flt(materials) + flt(self.labour_cost)

	def validate_approval(self):
		# Estimates above the threshold need an approved estimate before work starts.
		if self.status in ("Approved", "In Progress", "Completed") and flt(self.estimate) > APPROVAL_THRESHOLD:
			if self.approval_status != "Approved":
				frappe.throw(_("An estimate above {0} must be approved before work starts.").format(APPROVAL_THRESHOLD))
		if self.approval_status == "Approved" and not self.approved_by:
			frappe.throw(_("An approval needs an approver."))

	def validate_cost_bearer(self):
		if self.status == "Completed" and not self.cost_bearer:
			frappe.throw(_("Choose who pays for this work before completing it."))

	def validate_status_flow(self):
		if self.is_new():
			return
		old_status = frappe.db.get_value("Work Order", self.name, "status")
		allowed = {
			"Estimate Pending": ["Approved", "Cancelled"],
			"Approved": ["In Progress", "Cancelled"],
			"In Progress": ["Completed", "Cancelled"],
		}
		if old_status != self.status and self.status not in allowed.get(old_status, []):
			frappe.throw(_("Work order cannot move from {0} to {1}.").format(old_status, self.status))

	def on_update(self):
		if self.status == "In Progress" and not self.started_on:
			frappe.db.set_value("Work Order", self.name, "started_on", now_datetime(), update_modified=False)
		if self.status == "In Progress":
			self.sync_unit("Maintenance")
		if self.status == "Completed":
			self.complete_work()
		if self.status in ("Completed", "Cancelled"):
			self.release_unit_if_idle()

	def sync_unit(self, status):
		if frappe.db.get_value("Unit", self.unit, "status") in ("Vacant", "Occupied", "Reserved", "Maintenance"):
			frappe.db.set_value("Unit", self.unit, "status", status)

	def release_unit_if_idle(self):
		# Return the unit to the lease's state once no other work is open on it.
		open_work = frappe.db.exists("Work Order", {
			"unit": self.unit, "name": ["!=", self.name], "status": ["in", ["Estimate Pending", "Approved", "In Progress"]],
		})
		if open_work:
			return
		has_active = frappe.db.exists("Lease", {"unit": self.unit, "status": "Active"})
		self.sync_unit("Occupied" if has_active else "Vacant")

	def complete_work(self):
		if self.purchase_invoice:
			return  # Already posted. Never create a second Purchase Invoice.
		if self.assigned_to_type != "Contractor" or flt(self.total_cost) <= 0:
			# Internal staff and zero-cost work create no supplier bill.
			frappe.db.set_value("Work Order", self.name, "completed_on", now_datetime(), update_modified=False)
			return

		pi = self.create_purchase_invoice()
		frappe.db.set_value("Work Order", self.name, {
			"purchase_invoice": pi,
			"completed_on": now_datetime(),
		}, update_modified=False)

	def create_purchase_invoice(self):
		company = frappe.defaults.get_global_default("company")
		pi = frappe.get_doc({
			"doctype": "Purchase Invoice",
			"supplier": self.contractor,
			"company": company,
			"posting_date": frappe.utils.getdate(frappe.utils.today()),
			"bill_no": f"WO-{self.name}",
			"property": self.property,  # Property dimension carries the cost to the owner statement.
			"items": [{
				"item_code": self.get_expense_item(),
				"qty": 1,
				"rate": flt(self.total_cost),
				"expense_account": frappe.db.get_value("Account", {"account_name": MAINTENANCE_EXPENSE, "company": company}, "name"),
				"description": f"Work order {self.name}: {self.description[:120]}",
			}],
		})
		pi.insert(ignore_permissions=True)
		pi.submit()  # ERPNext posts the payable and expense.
		return pi.name

	def get_expense_item(self):
		item = "Maintenance Work"
		if not frappe.db.exists("Item", item):
			frappe.throw(_("Create an Item named '{0}' for maintenance costs before completing work orders.").format(item))
		return item


def clean_name(doc):
	pass
