# Copyright (c) 2026, mnorg and contributors
# For license information, please see license.txt

# import frappe
import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

KRA_PIN_PATTERN = re.compile(r"^[A-Z]\d{9}[A-Z]$")


class Tenant(Document):
	def validate(self):
		self.clean_fields()
		self.validate_kra_pin()                 # Rule 29 supporting check
		self.validate_unique_identifier()       # Rule 27
		self.validate_unique_email()            # Rule 28
		self.validate_emergency_contacts()
		self.validate_verification()            # Rule 29
		self.validate_tenant_type_change()      # Rule 30

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

	def validate_unique_identifier(self):
		existing = frappe.db.get_value(
			"Tenant",
			{"id_number_or_registration_number": self.id_number_or_registration_number, "name": ["!=", self.name or ""]},
			"name",
		)
		if existing:
			frappe.throw(_("A tenant with this ID or registration number already exists: {0}.").format(existing))

	def validate_unique_email(self):
		# Rule 28: checked only when an email is entered, so blank emails never collide.
		if not self.email:
			return
		existing = frappe.db.get_value("Tenant", {"email": self.email, "name": ["!=", self.name or ""]}, "name")
		if existing:
			frappe.throw(_("A tenant with this email already exists: {0}.").format(existing))

	def validate_emergency_contacts(self):
		# At least one emergency contact is needed before verification, checked there.
		# Here, only check each row is complete, which the required fields already do.
		pass

	def validate_verification(self):
		if self.status != "Verified":
			return
		missing = []
		if not self.kyc_documents:
			missing.append(_("KYC documents"))
		if not self.kra_pin:
			missing.append(_("KRA PIN"))
		if not self.consent_given:
			missing.append(_("consent"))
		if not self.get("emergency_contacts"):
			missing.append(_("an emergency contact"))
		if missing:
			frappe.throw(_("Before a tenant can be Verified, add: {0}.").format(", ".join(missing)))

	def validate_tenant_type_change(self):
		# Rule 30: the customer's type is set when it is created, so it cannot change afterwards.
		if self.is_new() or not self.customer:
			return
		old_type = frappe.db.get_value("Tenant", self.name, "tenant_type")
		if old_type != self.tenant_type:
			frappe.throw(_("Tenant type cannot be changed once a customer has been created."))

	def on_update(self):
		# Rule 29: creating the customer on verification.
		if self.status == "Verified":
			self.ensure_customer()
		# Rule 31: keep the customer in step with the tenant.
		self.sync_customer()

	def ensure_customer(self):
		if self.customer and frappe.db.exists("Customer", self.customer):
			return

		selling = frappe.get_single("Selling Settings")
		customer = frappe.get_doc({
			"doctype": "Customer",
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
		# Rule 32: a tenant with leases cannot be deleted.
		if frappe.db.exists("Lease", {"tenant": self.name}):
			frappe.throw(_("Cannot delete this tenant because it has leases. Set the status to Inactive instead."))
		if self.customer and frappe.db.exists("Sales Invoice", {"customer": self.customer}):
			frappe.throw(_("Cannot delete this tenant because its customer has invoices. Set the status to Inactive instead."))
