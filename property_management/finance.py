"""Read-only views over ERPNext results. Nothing here writes to the ledger."""

import frappe
from frappe import _
from frappe.utils import flt, today

from erpnext.accounts.utils import get_balance_on
from property_management.rent import default_company


def customer_for_tenant(tenant):
	customer = frappe.db.get_value("Tenant", tenant, "customer")
	if not customer:
		frappe.throw(_("Tenant {0} has no ERPNext customer.").format(tenant))
	return customer


def lease_invoices(lease_name):
	"""Invoices raised for a lease, with ERPNext's own outstanding figure."""
	return frappe.get_all(
		"Sales Invoice",
		filters={"lease": lease_name, "docstatus": 1},
		fields=["name", "posting_date", "due_date", "grand_total", "outstanding_amount", "status"],
		order_by="due_date asc",
	)


def tenant_position(tenant, as_of=None):
	"""Compare open invoices with the customer's receivable balance from the ledger.

	invoices_outstanding: sum of ERPNext's outstanding figure on open invoices.
	ledger_balance: ERPNext's receivable balance for the customer on the date.
	difference: what is left over. A negative figure is credit held on account
	(unallocated payments or advances), so it should match the Payment Ledger.
	"""
	customer = customer_for_tenant(tenant)
	when = as_of or today()

	open_invoices = frappe.get_all(
		"Sales Invoice",
		filters={"customer": customer, "docstatus": 1, "outstanding_amount": [">", 0]},
		fields=["outstanding_amount"],
	)
	invoices_outstanding = sum(flt(i.outstanding_amount) for i in open_invoices)

	ledger_balance = flt(get_balance_on(
		date=when,
		party_type="Customer",
		party=customer,
		company=default_company(),
	))

	return {
		"customer": customer,
		"invoices_outstanding": invoices_outstanding,
		"ledger_balance": ledger_balance,
		"difference": ledger_balance - invoices_outstanding,
	}


def lease_outstanding(lease_name):
	return sum(flt(i.outstanding_amount) for i in lease_invoices(lease_name))
