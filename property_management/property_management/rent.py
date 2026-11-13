"""Rent schedules, invoices, receipts and deposits.

Constants marked DECISION are working defaults. Confirm them before go-live.
"""

import calendar
from datetime import date

import frappe
from frappe import _
from frappe.utils import add_days, add_months, cint, date_diff, flt, get_last_day, getdate, today
from property_management.reminders import issue_lead_days

RENT_ITEM = "Monthly Rent"  # DECISION: item used for rent lines. Must exist with an income account.
HORIZON_MONTHS = 12  # DECISION: how far ahead a lease with no end date is scheduled.
FREQUENCY_MONTHS = {"Monthly": 1, "Quarterly": 3, "Annually": 12}
# Lease charges invoiced automatically in this release. Other frequencies are flagged, not billed.
AUTO_CHARGE_FREQUENCIES = ("Monthly", "One-Time")
ALLOWED_CHANNELS = ("Cash", "Bank Transfer", "M-Pesa", "Cheque")
AGING = [
	("Current", 0, 0),
	("1-30 days", 1, 30),
	("31-60 days", 31, 60),
	("61-90 days", 61, 90),
	("Over 90 days", 91, None),
]


def default_company():
	company = frappe.db.get_single_value("Global Defaults", "default_company")
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
	"""Return schedule rows for a lease. Partial first period, then full periods."""
	start = getdate(from_date or lease.start_date)
	rent = flt(lease.rent_amount)
	due_day = cint(lease.payment_due_day)
	end = getdate(lease.end_date) if lease.end_date else add_days(add_months(start, HORIZON_MONTHS), -1)
	step = FREQUENCY_MONTHS.get(lease.payment_frequency or "Monthly", 1)

	lines = []
	anchor = first_due_on_or_after(start, due_day)
	if anchor > start:
		# DECISION: partial first period is invoiced on the start date.
		lines.append(make_line(start, min(add_days(anchor, -1), end), start, rent))

	cursor = anchor
	while cursor <= end:
		nm = add_months(cursor.replace(day=1), step)
		next_anchor = due_date_in_month(nm.year, nm.month, due_day)
		period_end = min(add_days(next_anchor, -1), end)
		# DECISION: each invoice is raised and due on the period's first day, with no grace period.
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
	"""Re-price pending periods from the effective date of an approved rent change.

	If the effective date falls inside a pending period, pricing changes from the start
	of that period, so no period is split between two rents.
	"""
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

	try:
		invoice = frappe.get_doc({
			"doctype": "Sales Invoice",
			"customer": customer,
			"company": default_company(),
			"posting_date": getdate(today()),
			"due_date": getdate(line.due_date),
			"lease": lease.name,
			"lease_period_key": key,
			"items": items,
		}).insert(ignore_permissions=True)
		invoice.submit()
	except frappe.DuplicateEntryError:
		# Another run created it first. The unique key guarantees only one invoice exists.
		return frappe.db.get_value("Sales Invoice", {"lease_period_key": key}, "name")
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

def record_receipt(tenant, amount, channel, reference, received_on, bank_account, mode_of_payment):
	"""Record one receipt and allocate it to open invoices, oldest first.

	Any amount left after the open invoices are cleared stays on the customer as credit.
	"""
	amount = flt(amount)
	if amount <= 0:
		frappe.throw(_("Receipt amount must be greater than zero."))
	if channel not in ALLOWED_CHANNELS:
		frappe.throw(_("Unknown payment channel: {0}.").format(channel))
	if not reference:
		frappe.throw(_("Every receipt needs a reference, such as an M-Pesa code or cheque number."))
	# Duplicate protection: the same reference cannot be recorded twice.
	if frappe.db.exists("Payment Entry", {"reference_no": reference, "docstatus": 1}):
		frappe.throw(_("Reference {0} has already been recorded.").format(reference))
	# Phase 5 will require a matching Safaricom confirmation before an M-Pesa receipt is accepted.

	customer = frappe.db.get_value("Tenant", tenant, "customer")
	if not customer:
		frappe.throw(_("Tenant {0} has no ERPNext customer.").format(tenant))

	company = default_company()
	receivable = frappe.get_cached_value("Company", company, "default_receivable_account")
	open_invoices = frappe.get_all(
		"Sales Invoice",
		filters={"customer": customer, "docstatus": 1, "outstanding_amount": [">", 0]},
		fields=["name", "outstanding_amount"],
		order_by="due_date asc, posting_date asc, name asc",
	)

	pe = frappe.new_doc("Payment Entry")
	pe.payment_type = "Receive"
	pe.party_type = "Customer"
	pe.party = customer
	pe.company = company
	pe.posting_date = getdate(received_on)
	pe.mode_of_payment = mode_of_payment
	pe.paid_from = receivable
	pe.paid_to = bank_account
	pe.paid_amount = amount
	pe.received_amount = amount
	pe.reference_no = reference
	pe.reference_date = getdate(received_on)

	remaining = amount
	for invoice in open_invoices:
		if remaining <= 0:
			break
		allocated = min(remaining, flt(invoice.outstanding_amount))
		pe.append("references", {
			"reference_doctype": "Sales Invoice",
			"reference_name": invoice.name,
			"allocated_amount": allocated,
		})
		remaining -= allocated

	pe.insert(ignore_permissions=True)
	pe.submit()
	return pe.name


# ---------------------------------------------------------------- deposits

def record_deposit(lease_name, amount, bank_account, received_on, reference):
	"""Receive a security deposit. It is a liability, never income."""
	lease = frappe.get_doc("Lease", lease_name)
	company = default_company()
	deposit_account = frappe.db.get_value(
		"Account", {"account_name": "Tenant Deposits", "company": company, "is_group": 0}, "name"
	)
	if not deposit_account:
		frappe.throw(_("Create a 'Tenant Deposits' liability account for {0}.").format(company))

	je = frappe.new_doc("Journal Entry")
	je.voucher_type = "Bank Entry"
	je.company = company
	je.posting_date = getdate(received_on)
	je.cheque_no = reference
	je.cheque_date = getdate(received_on)
	je.user_remark = f"Security deposit for lease {lease.name}"
	je.append("accounts", {"account": bank_account, "debit_in_account_currency": flt(amount)})
	je.append("accounts", {"account": deposit_account, "credit_in_account_currency": flt(amount)})
	je.insert(ignore_permissions=True)
	je.submit()
	return je.name


# ---------------------------------------------------------------- arrears

def arrears_by_tenant(as_of=None):
	"""Outstanding balance per ERPNext customer, split by how overdue each invoice is."""
	as_of = getdate(as_of or today())
	invoices = frappe.get_all(
		"Sales Invoice",
		filters={"docstatus": 1, "outstanding_amount": [">", 0]},
		fields=["customer", "outstanding_amount", "due_date"],
	)

	summary = {}
	for inv in invoices:
		days = max(0, date_diff(as_of, getdate(inv.due_date))) if inv.due_date else 0
		label = next(
			lbl for lbl, low, high in AGING if days >= low and (high is None or days <= high)
		)
		row = summary.setdefault(inv.customer, {"total": 0.0, **{lbl: 0.0 for lbl, _low, _high in AGING}})
		row[label] += flt(inv.outstanding_amount)
		row["total"] += flt(inv.outstanding_amount)
	return summary
