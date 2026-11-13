import frappe
from frappe import _
from frappe.utils import flt, getdate, today


def execute(filters=None):
	filters = frappe._dict(filters or {})
	from_date = getdate(filters.from_date or getdate(today()).replace(month=1, day=1))
	to_date = getdate(filters.to_date or today())

	params = {"from": from_date, "to": to_date}
	prop_clause = ""
	if filters.property:
		prop_clause = "AND gl.property = %(property)s"
		params["property"] = filters.property

	# Only Income and Expense accounts. Liabilities such as Owner Payables and Tenant Deposits
	# are excluded, so owners' money is not counted as your income.
	rows = frappe.db.sql(
		f"""
		SELECT gl.property AS property, acc.root_type AS root_type,
		       SUM(gl.credit - gl.debit) AS amount
		FROM `tabGL Entry` gl
		INNER JOIN `tabAccount` acc ON acc.name = gl.account
		WHERE gl.is_cancelled = 0
		  AND gl.posting_date BETWEEN %(from)s AND %(to)s
		  AND acc.root_type IN ('Income', 'Expense')
		  AND IFNULL(gl.property, '') != ''
		  {prop_clause}
		GROUP BY gl.property, acc.root_type
		""",
		params,
		as_dict=True,
	)

	perf = {}
	for r in rows:
		p = perf.setdefault(r.property, {"income": 0.0, "expense": 0.0})
		if r.root_type == "Income":
			p["income"] += flt(r.amount)
		else:
			p["expense"] += -flt(r.amount)  # Expense accounts net to a debit balance, so flip the sign.

	data = []
	for prop, p in sorted(perf.items()):
		net = p["income"] - p["expense"]
		data.append({
			"property": prop,
			"income": p["income"],
			"expense": p["expense"],
			"net": net,
			"margin": (net / p["income"] * 100) if p["income"] else 0,
		})

	total_income = sum(r["income"] for r in data)
	total_expense = sum(r["expense"] for r in data)
	total_net = total_income - total_expense

	columns = [
		{"label": _("Property"), "fieldname": "property", "fieldtype": "Link", "options": "Property", "width": 180},
		{"label": _("Income"), "fieldname": "income", "fieldtype": "Currency", "width": 140},
		{"label": _("Expenses"), "fieldname": "expense", "fieldtype": "Currency", "width": 140},
		{"label": _("Net Operating Income"), "fieldname": "net", "fieldtype": "Currency", "width": 170},
		{"label": _("Margin %"), "fieldname": "margin", "fieldtype": "Percent", "width": 110},
	]

	summary = [
		{"value": total_income, "label": _("Income"), "datatype": "Currency"},
		{"value": total_expense, "label": _("Expenses"), "datatype": "Currency"},
		{"value": total_net, "label": _("Net operating income"), "datatype": "Currency"},
	]
	return columns, data, None, None, summary
