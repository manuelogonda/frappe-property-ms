import frappe
from frappe import _
from property_management.portal import current_landlord, acknowledge_rent_review


def get_context(context):
	current_landlord()
	context.no_cache = 1
	context.error = None
	context.done = None
	if frappe.request.method == "POST":
		try:
			context.done = acknowledge_rent_review(frappe.form_dict.get("review"))
		except Exception as exc:
			context.error = str(exc)

	context.reviews = []
	for lease in frappe.get_list("Lease", fields=["name", "unit"]):
		doc = frappe.get_doc("Lease", lease.name)
		for r in doc.get("rent_reviews") or []:
			if r.approved_status == "Pending" and not r.acknowledged_on:
				context.reviews.append({
					"name": r.name, "lease": doc.name, "unit": doc.unit,
					"review_date": r.review_date, "current_rent": r.current_rent,
					"proposed_rent": r.proposed_rent, "reason": r.reason,
				})
