"""Rent schedules and invoices.

This module creates ERPNext documents. It does not calculate balances, allocate
payments, or post to the ledger. ERPNext does those. Constants marked DECISION are
working defaults to confirm before go-live.
"""

import calendar
from datetime import date

import frappe
from frappe import _
from frappe.utils import add_days, add_months, cint, date_diff, flt, get_last_day, getdate, today

from property_management.reminders import issue_lead_days

RENT_ITEM = "Monthly Rent"  # DECISION: must exist as an Item with an income account.
HORIZON_MONTHS = 12  # DECISION: how far ahead a lease with no end date is scheduled.
FREQUENCY_MONTHS = {"Monthly": 1, "Quarterly": 3, "Annually": 12}
# Lease charges invoiced automatically in this release. Other frequencies are flagged, not billed.
AUTO_CHARGE_FREQUENCIES = ("Monthly", "One-Time")
ALLOWED_CHANNELS = ("Cash", "Bank Transfer", "M-Pesa", "Cheque")


def default_company():
	company = frappe.defaults.get_global_default("company") or frappe.db.get_single_value(
		"Global Defaults", "default_company"
	)
	if not company:
		frappe.throw(_("Set a default company in Global Defaults before invoicing."))
	return company


# ---------------------------------------------------------------- schedule

def due_date_in_month(year, month, due_day):
	last = calendar.monthrange(year, month)[1]
	return date(year, month, min(due_day, last))


def first_due_on_or_after(start, due_day):
	candidate = due_date_in_month(start.year, start.month, due_day)
	if candidate < start:
		nxt = add_months(start.replace(day=1), 1)
		candidate = due_date_in_month(nxt.year, nxt.month, due_day)
	return candidate


def period_amount(rent, start, end):
	"""Rent for a period, prorated by day within each calendar month it touches.

	DECISION: daily proration against the actual days in each month.
	"""
	total = 0.0
	cursor = start
	while cursor <= end:
		month_end = get_last_day(cursor)
		segment_end = min(month_end, end)
		days = date_diff(segment_end, cursor) + 1
		total += rent * days / month_end.day
		cursor = add_days(segment_end, 1)
	return flt(total, 2)


def make_line(start, end, due, rent):
	return {
		"period_start": start,
		"period_end": end,
		"due_date": due,
		"amount": period_amount(rent, start, end),
		"status": "Pending",
	}


def build_schedule(lease, from_date=None):
	"""Schedule rows for a lease: a partial first period, then full periods."""
	start = getdate(from_date or lease.start_date)
	rent = flt(lease.rent_amount)
	due_day = cint(lease.payment_due_day)
	end = getdate(lease.end_date) if lease.end_date else add_days(add_months(start, HORIZON_MONTHS), -1)
	step = FREQUENCY_MONTHS.get(lease.payment_frequency or "Monthly", 1)

	lines = []
	anchor = first_due_on_or_after(start, due_day)
	if anchor > start:
		# DECISION: the partial first period is invoiced on the start date.
		lines.append(make_line(start, min(add_days(anchor, -1), end), start, rent))

	cursor = anchor
	while cursor <= end:
		nm = add_months(cursor.replace(day=1), step)
		next_anchor = due_date_in_month(nm.year, nm.month, due_day)
		period_end = min(add_days(next_anchor, -1), end)
		# DECISION: each period is due on its first day, with no grace period.
		lines.append(make_line(cursor, period_end, cursor, rent))
		cursor = next_anchor
	return lines


def has_invoiced_lines(lease):
	return any(line.status == "Invoiced" for line in lease.get("rent_schedule") or [])


def cancel_after(lease, termination_date):
	cutoff = getdate(termination_date)
	for line in lease.get("rent_schedule") or []:
		if line.status == "Pending" and getdate(line.due_date) > cutoff:
			line.status = "Cancelled"


def rebuild_from(lease, effective):
	"""Re-price pending periods from an approved rent change's effective date."""
	effective = getdate(effective)
	rows = lease.get("rent_schedule") or []
	if any(l.status == "Invoiced" and getdate(l.period_end) >= effective for l in rows):
		frappe.throw(
			_("Rent cannot change from {0}: that period is already invoiced. "
			  "Choose a later effective date.").format(effective)
		)

	pending_starts = [
		getdate(l.period_start) for l in rows if l.status == "Pending" and getdate(l.period_end) >= effective
	]
	from_date = min(pending_starts + [effective])
	kept = [l for l in rows if l.status != "Pending" or getdate(l.period_end) < from_date]
	lease.set("rent_schedule", kept)
	for line in build_schedule(lease, from_date):
		lease.append("rent_schedule", line)


# ---------------------------------------------------------------- invoices

def months_in(line):
	start, end = getdate(line.period_start), getdate(line.period_end)
	return (end.year - start.year) * 12 + end.month - start.month + 1


def charge_items(lease, line, is_first):
	items = []
	for charge in lease.get("lease_charges") or []:
		if charge.frequency == "Monthly":
			amount = flt(charge.amount) * months_in(line)  # DECISION: flat monthly, not prorated.
		elif charge.frequency == "One-Time" and is_first:
			amount = flt(charge.amount)
		else:
			continue
		if not amount:
			continue
		items.append({
			"item_code": charge.charge_type,
			"qty": 1,
			"rate": flt(amount),
			"description": charge.description or charge.charge_type,
		})
	return items


def ensure_items_exist(item_codes):
	missing = [code for code in set(item_codes) if not frappe.db.exists("Item", code)]
	if missing:
		frappe.throw(_("Create these items in ERPNext before invoicing: {0}").format(", ".join(sorted(missing))))


def invoice_line(lease, line, is_first):
	"""Create one submitted Sales Invoice for a schedule line. Safe to call twice."""
	key = f"{lease.name}|{getdate(line.period_start)}"
	existing = frappe.db.get_value("Sales Invoice", {"lease_period_key": key}, "name")
	if existing:
		return existing

	customer = frappe.db.get_value("Tenant", lease.tenant, "customer")
	if not customer:
		frappe.throw(_("Tenant {0} has no ERPNext customer. Verify the tenant first.").format(lease.tenant))

	items = [{
		"item_code": RENT_ITEM,
		"qty": 1,
		"rate": flt(line.amount),
		"description": _("Rent {0} to {1}").format(line.period_start, line.period_end),
	}]
	items += charge_items(lease, line, is_first)
	ensure_items_exist([i["item_code"] for i in items])

	invoice = frappe.get_doc({
		"doctype": "Sales Invoice",
		"customer": customer,
		"company": default_company(),
		"posting_date": getdate(today()),  # DECISION: issue date, confirmed with the accountant.
		"due_date": getdate(line.due_date),
		"property": lease.property,  # Property dimension: carries the property onto every GL row.
		"lease": lease.name,
		"lease_period_key": key,
		"items": items,
	})

	try:
		invoice.insert(ignore_permissions=True)
	except frappe.DuplicateEntryError:
		# Another run created it first. The unique key guarantees only one invoice exists.
		frappe.clear_messages()
		return frappe.db.get_value("Sales Invoice", {"lease_period_key": key}, "name")

	invoice.submit()  # ERPNext posts the GL entries here.
	return invoice.name


def invoice_due_lines(lease):
	if lease.status != "Active":
		return  # Rule 10: no invoices for expired or terminated leases.

	lead = issue_lead_days(lease.payment_frequency)
	if lead is None:
		return  # Annually: timing not yet decided, so nothing is billed.

	today_date = getdate(today())
	for idx, line in enumerate(lease.get("rent_schedule") or []):
		if line.status != "Pending":
			continue
		if today_date < add_days(getdate(line.due_date), -lead):
			continue  # Too early to issue.
		invoice_name = invoice_line(lease, line, is_first=(idx == 0))
		frappe.db.set_value(
			"Lease Rent Schedule", line.name,
			{"sales_invoice": invoice_name, "status": "Invoiced"},
			update_modified=False,
		)


# ---------------------------------------------------------------- receipts

def create_receipt_draft(tenant, amount, channel, reference, received_on, mode_of_payment, paid_to=None):
	"""Create a draft Payment Entry for a receipt.

	ERPNext fills the receivable account, and the bank account from the mode of payment
	when paid_to is left blank. Allocation to invoices is done in ERPNext: open the draft
	and use "Get Outstanding Invoices", then submit.
	"""
	amount = flt(amount)
	if amount <= 0:
		frappe.throw(_("Receipt amount must be greater than zero."))
	if channel not in ALLOWED_CHANNELS:
		frappe.throw(_("Unknown payment channel: {0}.").format(channel))
	if not reference:
		frappe.throw(_("Every receipt needs a reference, such as an M-Pesa code or cheque number."))
	# A reference cannot be recorded twice, whether draft or submitted.
	if frappe.db.exists("Payment Entry", {"reference_no": reference, "docstatus": ["<", 2]}):
		frappe.throw(_("Reference {0} has already been recorded.").format(reference))

	customer = frappe.db.get_value("Tenant", tenant, "customer")
	if not customer:
		frappe.throw(_("Tenant {0} has no ERPNext customer.").format(tenant))

	pe = frappe.new_doc("Payment Entry")
	pe.payment_type = "Receive"
	pe.party_type = "Customer"
	pe.party = customer
	pe.company = default_company()
	pe.posting_date = getdate(received_on)
	pe.mode_of_payment = mode_of_payment
	if paid_to:
		pe.paid_to = paid_to
	pe.paid_amount = amount
	pe.received_amount = amount
	pe.reference_no = reference
	pe.reference_date = getdate(received_on)
	pe.insert(ignore_permissions=True)  # Draft only. Not submitted, so no ledger effect yet.
	return pe.name
