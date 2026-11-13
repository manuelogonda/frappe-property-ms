from collections import Counter

import frappe
from frappe import _
from frappe.utils import add_days, flt, getdate, today


def execute(filters=None):
	filters = frappe._dict(filters or {})
	from_date = getdate(filters.from_date or add_days(today(), -30))
	to_date = getdate(filters.to_date or today())

	entries = frappe.get_all(
		"Payment Entry",
		filters={
			"docstatus": 1,
			"payment_type": "Receive",
			"posting_date": ["between", [from_date, to_date]],
		},
		fields=["name", "posting_date", "party", "mode_of_payment", "reference_no", "paid_amount"],
		order_by="posting_date asc",
	)

	allocated = {}
	if entries:
		refs = frappe.get_all(
			"Payment Entry Reference",
			filters={"parenttype": "Payment Entry", "parent": ["in", [e.name for e in entries]]},
			fields=["parent", "allocated_amount"],
		)
		for ref in refs:
			allocated[ref.parent] = allocated.get(ref.parent, 0.0) + flt(ref.allocated_amount)

	reference_counts = Counter(e.reference_no for e in entries if e.reference_no)

	data, channel_totals = [], {}
	for e in entries:
		received = flt(e.paid_amount)
		used = allocated.get(e.name, 0.0)
		credit = received - used

		flags = []
		if reference_counts[e.reference_no] > 1:
			flags.append(_("Duplicate reference"))
		if credit > 0.005:
			flags.append(_("Credit on account"))

		channel = e.mode_of_payment or _("Unspecified")
		t = channel_totals.setdefault(channel, {"received": 0.0, "allocated": 0.0, "credit": 0.0})
		t["received"] += received
		t["allocated"] += used
		t["credit"] += credit

		data.append({
			"payment": e.name,
			"posting_date": e.posting_date,
			"customer": e.party,
			"channel": channel,
			"reference": e.reference_no or "",
			"received": received,
			"allocated": used,
			"credit": credit,
			"flags": ", ".join(flags),
		})

	# Each channel must reconcile: received = allocated + credit.
	for channel, t in channel_totals.items():
		data.append({
			"payment": "",
			"posting_date": None,
			"customer": "",
			"channel": _("Total: {0}").format(channel),
			"reference": "",
			"received": t["received"],
			"allocated": t["allocated"],
			"credit": t["credit"],
			"flags": "" if abs(t["received"] - t["allocated"] - t["credit"]) < 0.01 else _("Does not reconcile"),
		})

	columns = [
		{"label": _("Payment Entry"), "fieldname": "payment", "fieldtype": "Link", "options": "Payment Entry", "width": 150},
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 170},
		{"label": _("Channel"), "fieldname": "channel", "fieldtype": "Data", "width": 140},
		{"label": _("Reference"), "fieldname": "reference", "fieldtype": "Data", "width": 150},
		{"label": _("Received"), "fieldname": "received", "fieldtype": "Currency", "width": 120},
		{"label": _("Allocated"), "fieldname": "allocated", "fieldtype": "Currency", "width": 120},
		{"label": _("Credit"), "fieldname": "credit", "fieldtype": "Currency", "width": 110},
		{"label": _("Flags"), "fieldname": "flags", "fieldtype": "Data", "width": 190},
	]

	total_received = sum(t["received"] for t in channel_totals.values())
	total_allocated = sum(t["allocated"] for t in channel_totals.values())
	total_credit = sum(t["credit"] for t in channel_totals.values())
	summary = [
		{"value": total_received, "label": _("Received"), "datatype": "Currency"},
		{"value": total_allocated, "label": _("Allocated to invoices"), "datatype": "Currency"},
		{"value": total_credit, "label": _("Held as credit"), "datatype": "Currency"},
	]
	return columns, data, None, None, summary
