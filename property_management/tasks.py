import frappe
from frappe.utils import today

from frappe.utils import add_days, getdate, now_datetime, today

from property_management import rent


ALERT_WINDOWS = (90, 60, 30)


def alert_expiring_property_documents():
	today_date = getdate(today())
	for window in ALERT_WINDOWS:
		target = add_days(today_date, window)
		rows = frappe.db.sql(
			"""
			select d.parent as property, d.document_type, d.expiry_date
			from `tabProperty Document` d
			where d.expiry_date = %(target)s
			""",
			{"target": target},
			as_dict=True,
		)
		for row in rows:
			send_expiry_alert(row, window)


def send_expiry_alert(row, window):
	key = f"PD|{row.property}|{row.document_type}|{row.expiry_date}|{window}"
	if frappe.db.exists("Reminder Log", {"reminder_key": key}):
		return  # Already sent for this window.

	recipients = frappe.get_all(
		"User Permission",
		filters={"allow": "Property", "for_value": row.property, "user": ["!=", "Administrator"]},
		pluck="user",
	)
	recipients = list({r for r in recipients if frappe.db.get_value("User", r, "enabled")})
	if not recipients:
		recipients = frappe.get_all("Has Role", filters={"role": "Property Manager"}, pluck="parent")

	subject = _("{0} for {1} expires in {2} days").format(row.document_type, row.property, window)
	message = _("The {0} for property {1} expires on {2}. Renew it before then.").format(
		row.document_type, row.property, row.expiry_date)
	for user in recipients:
		frappe.sendmail(recipients=[user], subject=subject, message=message)

	frappe.get_doc({
		"doctype": "Reminder Log",
		"reminder_key": key,
		"reminder_type": "Overdue Notice",
		"notice_number": window,
		"status": "Sent",
		"sent_at": now_datetime(),
		"channel": "Email",
		"recipient": ", ".join(recipients),
	}).insert(ignore_permissions=True)


def expire_ended_leases():
	leases = frappe.get_all(
		"Lease", filters={"status": "Active", "end_date": ["<", today()]}, pluck="name"
	)
	for name in leases:
		try:
			lease = frappe.get_doc("Lease", name)
			lease.status = "Expired"
			lease.save(ignore_permissions=True)
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			frappe.log_error(title=f"Lease expiry failed: {name}", message=frappe.get_traceback())


def generate_due_invoices():
	for name in frappe.get_all("Lease", filters={"status": "Active"}, pluck="name"):
		try:
			lease = frappe.get_doc("Lease", name)
			rent.invoice_due_lines(lease)
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			frappe.log_error(title=f"Rent invoicing failed: {name}", message=frappe.get_traceback())
