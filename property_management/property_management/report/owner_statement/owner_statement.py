import frappe
from frappe import _
from frappe.utils import add_days, flt, getdate, today

FEE_BASE = "Rent Collected"  # DECISION: fee base. Change to a rent-due calculation only after agreeing it.


def months_between(start, end):
	return (end.year - start.year) * 12 + end.month - start.month + 1


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if not filters.property:
		frappe.throw(_("Select a property."))
	from_date = getdate(filters.from_date or add_days(today(), -30))
	to_date = getdate(filters.to_date or today())

	# Rent received: receipts allocated to this property's lease invoices, dated in the period.
	leases = frappe.get_all("Lease", filters={"property": filters.property}, pluck="name")
	invoices = frappe.get_all(
		"Sales Invoice", filters={"lease": ["in", leases or [""]], "docstatus": 1}, pluck="name"
	)
	rent_received = 0.0
	if invoices:
		refs = frappe.get_all(
			"Payment Entry Reference",
			filters={"reference_doctype": "Sales Invoice", "reference_name": ["in", invoices], "parenttype": "Payment Entry"},
			fields=["parent", "allocated_amount"],
		)
		payments = {
			p.name: p.posting_date
			for p in frappe.get_all(
				"Payment Entry",
				filters={"name": ["in", [r.parent for r in refs] or [""]], "docstatus": 1},
				fields=["name", "posting_date"],
			)
		}
		rent_received = sum(
			flt(r.allocated_amount) for r in refs
			if r.parent in payments and from_date <= getdate(payments[r.parent]) <= to_date
		)

	# Approved expenses: completed work orders charged to owners, on this property, in the period.
	expenses = sum(
		flt(w.total_cost)
		for w in frappe.get_all(
			"Work Order",
			filters={
				"property": filters.property,
				"status": "Completed",
				"cost_bearer": "Owner",
				"completed_on": ["between", [from_date, add_days(to_date, 1)]],
			},
			fields=["total_cost"],
		)
	)

	# Management fee from the active agreement.
	agreement = frappe.db.get_value(
		"Management Agreement",
		{"property": filters.property, "status": "Active"},
		["fee_structure", "management_fee_percent", "fixed_management_fee"],
		as_dict=True,
	)
	if not agreement:
		frappe.throw(_("No active management agreement for {0}.").format(filters.property))
	if agreement.fee_structure == "Percentage":
		fee = rent_received * flt(agreement.management_fee_percent) / 100  # FEE_BASE: rent collected
	else:
		# DECISION: a fixed fee is charged per calendar month in the period.
		fee = flt(agreement.fixed_management_fee) * months_between(from_date, to_date)

	# Split across owners by share.
	owners = frappe.get_all(
		"Property Landlord",
		filters={"parenttype": "Property", "parent": filters.property},
		fields=["landlord", "share_percentage"],
	)
	names = {
		l.name: l.landlord_name
		for l in frappe.get_all("Landlord", filters={"name": ["in", [o.landlord for o in owners] or [""]]}, fields=["name", "landlord_name"])
	}

	data = []
	for o in owners:
		share = flt(o.share_percentage) / 100
		rent = round(rent_received * share, 2)
		exp = round(expenses * share, 2)
		owner_fee = round(fee * share, 2)
		data.append({
			"owner": o.landlord,
			"owner_name": names.get(o.landlord, ""),
			"share": flt(o.share_percentage),
			"rent_received": rent,
			"expenses": exp,
			"fee": owner_fee,
			"net": round(rent - exp - owner_fee, 2),
		})

	columns = [
		{"label": _("Owner"), "fieldname": "owner", "fieldtype": "Link", "options": "Landlord", "width": 130},
		{"label": _("Owner Name"), "fieldname": "owner_name", "fieldtype": "Data", "width": 180},
		{"label": _("Share %"), "fieldname": "share", "fieldtype": "Percent", "width": 90},
		{"label": _("Rent Received"), "fieldname": "rent_received", "fieldtype": "Currency", "width": 130},
		{"label": _("Approved Expenses"), "fieldname": "expenses", "fieldtype": "Currency", "width": 140},
		{"label": _("Management Fee"), "fieldname": "fee", "fieldtype": "Currency", "width": 130},
		{"label": _("Net Settlement"), "fieldname": "net", "fieldtype": "Currency", "width": 140},
	]

	summary = [
		{"value": rent_received, "label": _("Rent received (property)"), "datatype": "Currency"},
		{"value": expenses, "label": _("Owner-borne expenses (property)"), "datatype": "Currency"},
		{"value": fee, "label": _("Management fee (property)"), "datatype": "Currency"},
	]
	return columns, data, None, None, summary
