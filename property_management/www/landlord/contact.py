import frappe
from property_management.portal import current_landlord, request_contact_change

FIELDS = ("phone", "email", "address", "mpesa_phone_number", "bank_name",
		  "bank_branch", "bank_account_name", "bank_account_number")


def get_context(context):
	current_landlord()
	context.no_cache = 1
	context.error = None
	context.created = None
	if frappe.request.method == "POST":
		form = frappe.form_dict
		changes = {f: form.get(f) for f in FIELDS if form.get(f)}
		try:
			context.created = request_contact_change(changes, reason=form.get("reason"))
		except Exception as exc:
			context.error = str(exc)
