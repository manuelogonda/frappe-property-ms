import frappe
from frappe import _
from property_management.portal import current_landlord


def get_context(context):
	current_landlord()
	context.no_cache = 1
	context.properties = frappe.get_list(
		"Property", fields=["name", "property_name", "town_area", "status"], order_by="property_name asc",
	)
	context.invoices = frappe.get_list(
		"Sales Invoice",
		fields=["name", "property", "grand_total", "outstanding_amount", "posting_date", "due_date"],
		filters={"docstatus": 1}, order_by="posting_date desc", limit=50,
	)
	context.collected = sum(float(i.grand_total or 0) - float(i.outstanding_amount or 0) for i in context.invoices)
	context.outstanding = sum(float(i.outstanding_amount or 0) for i in context.invoices)
	context.work_orders = frappe.get_list(
		"Work Order",
		fields=["name", "property", "unit", "status", "total_cost", "completed_on"],
		filters={"cost_bearer": "Owner"}, order_by="creation desc", limit=50,
	)
