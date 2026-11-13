import frappe
from frappe import _
from frappe.utils import add_days, cint, date_diff, getdate, today


def renewal_label(lease):
	if not lease.renewal_allowed:
		return _("Not allowed")
	status = lease.renewal_status or "Not Applicable"
	return {
		"Not Applicable": _("Due"),
		"Pending": _("In progress"),
		"Approved": _("Approved"),
		"Rejected": _("Rejected"),
	}.get(status, status)


def execute(filters=None):
	filters = frappe._dict(filters or {})
	start = getdate(today())
	end = add_days(start, cint(filters.days or 90))

	conditions = {"status": "Active", "end_date": ["between", [start, end]]}
	if filters.property:
		conditions["property"] = filters.property

	leases = frappe.get_all(
		"Lease",
		filters=conditions,
		fields=[
			"name", "tenant", "property", "unit", "end_date", "renewal_allowed",
			"renewal_status", "notice_served_date", "notice_effective_date",
		],
		order_by="end_date asc",
	)

	tenant_names = dict(frappe.get_all("Tenant", fields=["name", "tenant_name"], as_list=True))
	data = [
		{
			"lease": lease.name,
			"tenant": lease.tenant,
			"tenant_name": tenant_names.get(lease.tenant, ""),
			"property": lease.property,
			"unit": lease.unit,
			"end_date": lease.end_date,
			"days_left": date_diff(lease.end_date, start),
			"renewal": renewal_label(lease),
			"notice_effective_date": lease.notice_effective_date,
		}
		for lease in leases
	]

	# Periodic leases have no end date, so they never appear above. Count them so they are not forgotten.
	periodic_filters = {"status": "Active", "end_date": ["is", "not set"]}
	if filters.property:
		periodic_filters["property"] = filters.property
	periodic = frappe.db.count("Lease", periodic_filters)

	columns = [
		{"label": _("Lease"), "fieldname": "lease", "fieldtype": "Link", "options": "Lease", "width": 140},
		{"label": _("Tenant"), "fieldname": "tenant", "fieldtype": "Link", "options": "Tenant", "width": 110},
		{"label": _("Tenant Name"), "fieldname": "tenant_name", "fieldtype": "Data", "width": 170},
		{"label": _("Property"), "fieldname": "property", "fieldtype": "Link", "options": "Property", "width": 130},
		{"label": _("Unit"), "fieldname": "unit", "fieldtype": "Link", "options": "Unit", "width": 130},
		{"label": _("End Date"), "fieldname": "end_date", "fieldtype": "Date", "width": 110},
		{"label": _("Days Left"), "fieldname": "days_left", "fieldtype": "Int", "width": 90},
		{"label": _("Renewal"), "fieldname": "renewal", "fieldtype": "Data", "width": 120},
		{"label": _("Notice Effective"), "fieldname": "notice_effective_date", "fieldtype": "Date", "width": 130},
	]

	summary = [
		{"value": len(data), "label": _("Ending in window"), "datatype": "Int"},
		{"value": sum(1 for r in data if r["renewal"] == _("Due")), "label": _("Renewals due"), "datatype": "Int"},
		{"value": periodic, "label": _("Periodic leases (no end date)"), "datatype": "Int"},
	]
	return columns, data, None, None, summary
