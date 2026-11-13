import frappe
from frappe import _
from frappe.utils import date_diff, flt, get_first_day, getdate, today


def bucket_for(days_overdue):
	if days_overdue <= 0:
		return "current"
	if days_overdue <= 30:
		return "d1_30"
	if days_overdue <= 60:
		return "d31_60"
	if days_overdue <= 90:
		return "d61_90"
	return "d90"


def execute(filters=None):
	filters = frappe._dict(filters or {})
	as_of = getdate(filters.as_of or today())
	from_date = getdate(filters.from_date or get_first_day(as_of))
	to_date = getdate(filters.to_date or as_of)
	prop = {"property": filters.property} if filters.property else {}

	tenants = {
		t.customer: t
		for t in frappe.get_all("Tenant", fields=["name", "tenant_name", "customer"])
		if t.customer
	}

	# Ageing: every open invoice, measured against as_of.
	open_invoices = frappe.get_all(
		"Sales Invoice",
		filters={"docstatus": 1, "outstanding_amount": [">", 0], **prop},
		fields=["customer", "outstanding_amount", "due_date"],
	)
	aged = {}
	for inv in open_invoices:
		row = aged.setdefault(inv.customer, {
			"current": 0.0, "d1_30": 0.0, "d31_60": 0.0, "d61_90": 0.0, "d90": 0.0, "total": 0.0,
		})
		days = date_diff(as_of, inv.due_date) if inv.due_date else 0
		row[bucket_for(days)] += flt(inv.outstanding_amount)
		row["total"] += flt(inv.outstanding_amount)

	data = []
	for customer, buckets in aged.items():
		tenant = tenants.get(customer, {})
		data.append({
			"tenant": tenant.get("name", ""),
			"customer": customer,
			"tenant_name": tenant.get("tenant_name", ""),
			**buckets,
		})
	data.sort(key=lambda r: r["total"], reverse=True)

	# Collection rate: invoices issued in the period, and how much of them is paid as at as_of.
	# Older debt collected in the period is not counted here, so this measures the period's billing.
	issued = frappe.get_all(
		"Sales Invoice",
		filters={
			"docstatus": 1,
			"lease": ["is", "set"],
			"posting_date": ["between", [from_date, to_date]],
			**prop,
		},
		fields=["grand_total", "outstanding_amount"],
	)
	billed = sum(flt(i.grand_total) for i in issued)
	collected = sum(flt(i.grand_total) - flt(i.outstanding_amount) for i in issued)
	rate = (collected / billed * 100) if billed else 0

	total_outstanding = sum(r["total"] for r in data)
	overdue = sum(r["total"] - r["current"] for r in data)

	columns = [
		{"label": _("Tenant"), "fieldname": "tenant", "fieldtype": "Link", "options": "Tenant", "width": 110},
		{"label": _("Tenant Name"), "fieldname": "tenant_name", "fieldtype": "Data", "width": 180},
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 180},
		{"label": _("Not Yet Due"), "fieldname": "current", "fieldtype": "Currency", "width": 120},
		{"label": _("1-30 Days"), "fieldname": "d1_30", "fieldtype": "Currency", "width": 120},
		{"label": _("31-60 Days"), "fieldname": "d31_60", "fieldtype": "Currency", "width": 120},
		{"label": _("61-90 Days"), "fieldname": "d61_90", "fieldtype": "Currency", "width": 120},
		{"label": _("Over 90 Days"), "fieldname": "d90", "fieldtype": "Currency", "width": 120},
		{"label": _("Total"), "fieldname": "total", "fieldtype": "Currency", "width": 130},
	]

	summary = [
		{"value": total_outstanding, "label": _("Total outstanding"), "datatype": "Currency"},
		{"value": overdue, "label": _("Overdue"), "datatype": "Currency"},
		{"value": billed, "label": _("Billed in period"), "datatype": "Currency"},
		{"value": collected, "label": _("Collected on period invoices"), "datatype": "Currency"},
		{"value": rate, "label": _("Rent collection rate"), "datatype": "Percent"},
	]
	return columns, data, None, None, summary
