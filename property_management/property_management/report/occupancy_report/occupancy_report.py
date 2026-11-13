import frappe
from frappe import _

STATUSES = ["Vacant", "Occupied", "Reserved", "Maintenance", "Inactive"]
# DECISION: Reserved and Maintenance units stay in the denominator, because they are rentable stock.
# Inactive units are excluded. Change this here if the owner-facing definition differs.


def execute(filters=None):
	filters = frappe._dict(filters or {})
	conditions = {"property": filters.property} if filters.property else {}

	units = frappe.get_all("Unit", filters=conditions, fields=["property", "building", "status"])

	groups = {}
	for unit in units:
		key = (unit.property, unit.building or "")
		counts = groups.setdefault(key, {s: 0 for s in STATUSES})
		counts[unit.status] = counts.get(unit.status, 0) + 1

	columns = [
		{"label": _("Property"), "fieldname": "property", "fieldtype": "Link", "options": "Property", "width": 150},
		{"label": _("Building"), "fieldname": "building", "fieldtype": "Data", "width": 150},
	]
	columns += [{"label": _(s), "fieldname": s.lower(), "fieldtype": "Int", "width": 100} for s in STATUSES]
	columns += [
		{"label": _("Total"), "fieldname": "total", "fieldtype": "Int", "width": 90},
		{"label": _("Occupancy %"), "fieldname": "occupancy", "fieldtype": "Percent", "width": 120},
	]

	data = []
	totals = {s: 0 for s in STATUSES}
	for (prop, building), counts in sorted(groups.items()):
		for s in STATUSES:
			totals[s] += counts[s]
		rentable = sum(counts.values()) - counts["Inactive"]
		row = {"property": prop, "building": building or _("(no building)"), "total": sum(counts.values())}
		row.update({s.lower(): counts[s] for s in STATUSES})
		row["occupancy"] = (counts["Occupied"] / rentable * 100) if rentable else 0
		data.append(row)

	rentable_total = sum(totals.values()) - totals["Inactive"]
	rate = (totals["Occupied"] / rentable_total * 100) if rentable_total else 0
	summary = [
		{"value": totals["Occupied"], "label": _("Occupied"), "datatype": "Int"},
		{"value": totals["Vacant"], "label": _("Vacant"), "datatype": "Int"},
		{"value": rate, "label": _("Occupancy rate"), "datatype": "Percent"},
	]
	return columns, data, None, None, summary
