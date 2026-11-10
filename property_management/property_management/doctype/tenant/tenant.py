# Copyright (c) 2026, mnorg and contributors
# For license information, please see license.txt

# import frappe
import re

import frappe
from frappe import _
from frappe.model.document import Document

KRA_PIN_PATTERN = re.compile(r"^[A-Z]\d{9}[A-Z]$")


class Tenant(Document):
	def autoname(self):
		# Naming rule is Expression: TN-00001, TN-00002, ...
		pass

	def validate(self):
		self.clean_fields()
		self.validate_kra_pin()
		self.validate_id_number()
		self.validate_email_unique()
		self.validate_verification()
		self.validate_tenant_type_change()

	def clean_fields(self):
		self.tenant_name = (self.tenant_name or "").strip()
		self.id_number_or_registration_number = (self.id_number_or_registration_number or "").strip()
		if self.email:
			self.email = self.email.strip().lower()

	def validate_kra_pin(self):
		if not self.kra_pin:
			return
		self.kra_pin = self.kra_pin.strip().upper()
		if not KRA_PIN_PATTERN.match(self.kra_pin):
			frappe.throw(_("KRA PIN must be one letter, nine digits, and one letter."))

	def validate_id_number(self):
		# The same person or company cannot be registered twice.
		existing = frappe.db.get_value(
			"Tenant",
			{"id_number_or_registration_number": self.id_number_or_registration_number, "name": ["!=", self.name or ""]},
			"name",
		)
		if existing:
			frappe.throw(_("A tenant with this ID or registration number already exists: {0}").format(existing))

	def validate_email_unique(self):
		# Email is optional, so only check when one is entered.
		if not self.email:
			return
		existing = frappe.db.get_value("Tenant", {"email": self.email, "name": ["!=", self.name or ""]}, "name")
		if existing:
			frappe.throw(_("A tenant with this email already exists: {0}").format(existing))

	def validate_verification(self):
		if self.status != "Verified":
			return
		if not self.kyc_documents:
			frappe.throw(_("Attach the KYC documents before marking this tenant as Verified."))
		if not self.kra_pin:
			frappe.throw(_("Enter the KRA PIN before marking this tenant as Verified."))

	def validate_tenant_type_change(self):
		# The linked customer's type is set once, so the tenant type cannot change afterwards.
		if self.is_new() or not self.customer:
			return
		old_type = frappe.db.get_value("Tenant", self.name, "tenant_type")
		if old_type != self.tenant_type:
			frappe.throw(_("Tenant type cannot be changed once a customer has been created."))

	def on_update(self):
		if self.status == "Verified":
			self.ensure_customer()
		self.sync_customer()

	def ensure_customer(self):
		if self.customer and frappe.db.exists("Customer", self.customer):
			return

		selling = frappe.get_single("Selling Settings")
		customer = frappe.get_doc({
			"doctype": "Customer",
			# Customer names must be unique in ERPNext, and two tenants can share a name.
			"customer_name": f"{self.tenant_name} [{self.name}]",
			"customer_type": self.tenant_type,
			"customer_group": selling.get("customer_group") or "Individual",
			"territory": selling.get("territory") or "All Territories",
			"tax_id": self.kra_pin,
			"mobile_no": self.phone_number,
			"email_id": self.email,
		}).insert(ignore_permissions=True)

		self.db_set("customer", customer.name, update_modified=False)

	def sync_customer(self):
		# Keeps the customer in step with the tenant record and blocks new invoices for inactive tenants.
		if not self.customer or not frappe.db.exists("Customer", self.customer):
			return
		frappe.db.set_value(
			"Customer",
			self.customer,
			{
				"mobile_no": self.phone_number,
				"email_id": self.email,
				"tax_id": self.kra_pin,
				"disabled": 1 if self.status == "Inactive" else 0,
			},
			update_modified=False,
		)

	def on_trash(self):
		if frappe.db.exists("DocType", "Lease") and frappe.db.exists("Lease", {"tenant": self.name}):
			frappe.throw(_("Cannot delete this tenant because it has leases. Set the status to Inactive instead."))
		if self.customer and frappe.db.exists("Sales Invoice", {"customer": self.customer}):
			frappe.throw(_("Cannot delete this tenant because its customer has invoices. Set the status to Inactive instead."))
