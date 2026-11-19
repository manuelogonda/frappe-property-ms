# Copyright (c) 2026, mnorg and contributors
# For license information, please see license.txt

# import frappe
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today

CONDITION_RANK = {"Good": 1, "Fair": 2, "Poor": 3}


class Inspection(Document):
	def validate(self):
		self.set_unit_and_tenant()
		self.validate_items()
		self.set_overall_condition()
		self.validate_signoff()
		self.validate_locked()

	def set_unit_and_tenant(self):
		lease = frappe.db.get_value("Lease", self.lease, ["unit", "tenant", "status"], as_dict=True)
		if not lease:
			frappe.throw(_("Choose a lease."))
		self.unit = lease.unit
		self.tenant = lease.tenant

	def validate_items(self):
		items = self.get("items") or []
		if not items:
			frappe.throw(_("Add at least one checklist item."))
		for row in items:
			if row.condition == "Poor" and not row.photo:
				frappe.throw(_("Attach a photo for every item in Poor condition ({0}).").format(row.item))

	def set_overall_condition(self):
		ratings = [CONDITION_RANK[r.condition] for r in self.get("items") or [] if r.condition in CONDITION_RANK]
		if not ratings:
			self.overall_condition = None
			return
		worst = max(ratings)
		self.overall_condition = {1: "Good", 2: "Fair", 3: "Poor"}[worst]

	def validate_signoff(self):
		if self.tenant_signed and not self.tenant_signed_on:
			self.tenant_signed_on = frappe.utils.now_datetime()
		if self.tenant_signed:
			self.status = "Signed"

	def validate_locked(self):
		# A signed inspection is evidence. Changes after signing require a new inspection.
		if self.is_new():
			return
		old = frappe.db.get_value("Inspection", self.name, "status")
		if old == "Signed" and self.status != "Signed":
			frappe.throw(_("A signed inspection cannot be changed. Create a new inspection instead."))
