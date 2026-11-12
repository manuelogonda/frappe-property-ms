import frappe
from frappe.utils import today

from property_management import rent


def expire_ended_leases():
	leases = frappe.get_all(
		"Lease", filters={"status": "Active", "end_date": ["<", today()]}, pluck="name"
	)
	for name in leases:
		try:
			lease = frappe.get_doc("Lease", name)
			lease.status = "Expired"
			lease.save(ignore_permissions=True)
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			frappe.log_error(title=f"Lease expiry failed: {name}", message=frappe.get_traceback())


def generate_due_invoices():
	for name in frappe.get_all("Lease", filters={"status": "Active"}, pluck="name"):
		try:
			lease = frappe.get_doc("Lease", name)
			rent.invoice_due_lines(lease)
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			frappe.log_error(title=f"Rent invoicing failed: {name}", message=frappe.get_traceback())
