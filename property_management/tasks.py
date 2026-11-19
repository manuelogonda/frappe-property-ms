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

LEASE_ALERT_WINDOWS = (90, 60, 30)


def alert_lease_expiries():
	today_date = getdate(today())
	for window in LEASE_ALERT_WINDOWS:
		target = add_days(today_date, window)
		leases = frappe.get_all(
			"Lease",
			filters={"status": "Active", "end_date": target},
			fields=["name", "tenant", "unit", "property", "end_date"],
		)
		for lease in leases:
			send_lease_alert(lease, window, "Lease Expiry")


def alert_notice_deadlines():
	today_date = getdate(today())
	for window in LEASE_ALERT_WINDOWS:
		target = add_days(today_date, window)
		leases = frappe.get_all(
			"Lease",
			filters={"status": "Active", "notice_effective_date": target},
			fields=["name", "tenant", "unit", "property", "notice_effective_date"],
		)
		for lease in leases:
			send_lease_alert(lease, window, "Notice Deadline")


def send_lease_alert(lease, window, reminder_type):
	key = f"{reminder_type}|{lease.name}|{window}"
	if frappe.db.exists("Reminder Log", {"reminder_key": key}):
		return  # Sent for this window already.

	date_value = lease.end_date if reminder_type == "Lease Expiry" else lease.notice_effective_date
	recipients = property_manager_emails(lease.property)
	if not recipients:
		return  # Nobody to tell. The gap should be visible, so leave it unlogged.

	subject = _("{0} in {1} days: unit {2}").format(reminder_type, window, lease.unit)
	message = _("Lease {0} for unit {1} at {2} reaches {3} on {4}.").format(
		lease.name, lease.unit, lease.property, reminder_type.lower(), date_value)
	for user in recipients:
		frappe.sendmail(recipients=[user], subject=subject, message=message)

	log_notification(key, reminder_type, lease.name, lease.tenant, "Email",
					 ", ".join(recipients), "Sent", notice_number=window)


def property_manager_emails(property_name):
	users = frappe.get_all(
		"User Permission",
		filters={"allow": "Property", "for_value": property_name},
		pluck="user",
	)
	active = [u for u in set(users) if frappe.db.get_value("User", u, "enabled")]
	return [u for u in active if "Property Manager" in frappe.get_roles(u)]
