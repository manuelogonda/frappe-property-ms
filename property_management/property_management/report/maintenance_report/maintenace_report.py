import frappe
from frappe import _
from frappe.utils import add_days, flt, get_datetime, getdate, today


def execute(filters=None):
	filters = frappe._dict(filters or {})
	from_date = getdate(filters.from_date or add_days(today(), -30))
	to_date = getdate(filters.to_date or today())

	req_filters = {"creation": ["between", [from_date, add_days(to_date, 1)]]}
	if filters.property:
		req_filters["property"] = filters.property

	requests = frappe.get_all(
		"Maintenance Request",
		filters=req_filters,
		fields=["name", "property", "unit", "category", "priority", "status", "creation", "work_order"],
		order_by="creation asc",
	)

	order_names = [r.work_order for r in requests if r.work_order]
	orders = {}
	if order_names:
		orders = {
			w.name: w
			for w in frappe.get_all(
				"Work Order",
				filters={"name": ["in", order_names]},
				fields=["name", "started_on", "completed_on", "total_cost", "cost_bearer"],
			)
		}

	data, durations, open_count, total_cost = [], [], 0, 0.0
	for r in requests:
		wo = orders.get(r.work_order) or frappe._dict()
		days = None
		if wo.get("completed_on"):
			days = round((get_datetime(wo.completed_on) - get_datetime(r.creation)).total_seconds() / 86400, 1)
			durations.append(days)
		if r.status not in ("Completed", "Closed", "Cancelled"):
			open_count += 1
		total_cost += flt(wo.get("total_cost"))
		data.append({
			"request": r.name,
			"property": r.property,
			"unit": r.unit,
			"category": r.category,
			"priority": r.priority,
			"status": r.status,
			"reported_on": getdate(r.creation),
			"days_to_complete": days,
			"work_order": r.work_order or "",
			"total_cost": flt(wo.get("total_cost")),
			"cost_bearer": wo.get("cost_bearer") or "",
		})

	columns = [
		{"label": _("Request"), "fieldname": "request", "fieldtype": "Link", "options": "Maintenance Request", "width": 150},
		{"label": _("Property"), "fieldname": "property", "fieldtype": "Link", "options": "Property", "width": 120},
		{"label": _("Unit"), "fieldname": "unit", "fieldtype": "Link", "options": "Unit", "width": 130},
		{"label": _("Category"), "fieldname": "category", "fieldtype": "Data", "width": 110},
		{"label": _("Priority"), "fieldname": "priority", "fieldtype": "Data", "width": 90},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 110},
		{"label": _("Reported On"), "fieldname": "reported_on", "fieldtype": "Date", "width": 100},
		{"label": _("Days to Complete"), "fieldname": "days_to_complete", "fieldtype": "Float", "width": 120},
		{"label": _("Work Order"), "fieldname": "work_order", "fieldtype": "Link", "options": "Work Order", "width": 140},
		{"label": _("Cost"), "fieldname": "total_cost", "fieldtype": "Currency", "width": 110},
		{"label": _("Cost Bearer"), "fieldname": "cost_bearer", "fieldtype": "Data", "width": 110},
	]

	summary = [
		{"value": len(data), "label": _("Requests"), "datatype": "Int"},
		{"value": open_count, "label": _("Open"), "datatype": "Int"},
		{"value": (sum(durations) / len(durations)) if durations else 0, "label": _("Avg days to complete"), "datatype": "Float"},
		{"value": total_cost, "label": _("Total maintenance cost"), "datatype": "Currency"},
	]
	return columns, data, None, None, summary
