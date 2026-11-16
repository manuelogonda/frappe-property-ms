import frappe
from frappe import _
from frappe.utils import add_days, cint, date_diff, flt, getdate, now_datetime, today

from property_management import messaging

MAX_ATTEMPTS = 3


def get_settings():
	return frappe.get_single("Reminder Settings")


def issue_lead_days(frequency, settings=None):
	"""Days before the due date when an invoice is issued and its rent reminder goes out.

	Returns None where timing is not decided yet (Annually), so nothing is billed for them.
	"""
	settings = settings or get_settings()
	if frequency in (None, "", "Monthly"):
		return cint(settings.monthly_lead_days)
	if frequency == "Quarterly":
		return cint(settings.quarterly_lead_days)
	return None


def overdue_notice_number(days_overdue, settings):
	"""The highest overdue notice whose day has been reached, or 0.

	If the job was down for a week, the tenant gets the current notice, not every missed one.
	"""
	reached = [
		n for n, day in ((1, settings.notice_1_day), (2, settings.notice_2_day), (3, settings.notice_3_day))
		if days_overdue >= cint(day)
	]
	return max(reached) if reached else 0


def within_send_window(settings):
	# Uses the site timezone. Set System Settings > Time Zone to Africa/Nairobi.
	hour = now_datetime().hour
	return cint(settings.quiet_start_hour) <= hour < cint(settings.quiet_end_hour)


def send_due_reminders():
	settings = get_settings()
	if not settings.enabled or not within_send_window(settings):
		return

	today_date = getdate(today())
	for inv in open_lease_invoices():
		try:
			process_invoice(inv, settings, today_date)
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			frappe.log_error(title=f"Reminder failed: {inv.name}", message=frappe.get_traceback())


def open_lease_invoices():
	return frappe.get_all(
		"Sales Invoice",
		filters={"docstatus": 1, "outstanding_amount": [">", 0], "lease": ["is", "set"]},
		fields=["name", "customer", "lease", "due_date", "outstanding_amount"],
	)


def process_invoice(inv, settings, today_date):
	lease = frappe.db.get_value("Lease", inv.lease, ["tenant", "unit", "status", "payment_frequency"], as_dict=True)
	tenant = frappe.db.get_value("Tenant", lease.tenant, ["tenant_name", "email", "phone_number"], as_dict=True)
	due = getdate(inv.due_date)
	days_overdue = date_diff(today_date, due)
	lead = issue_lead_days(lease.payment_frequency, settings)

	if days_overdue < 0:
		# Rent reminder: sent from the day the invoice is issued until the due date.
		if lease.status == "Active" and lead is not None and date_diff(due, today_date) <= lead:
			message = _(
				"Dear {0}, rent for unit {1} of KES {2} is due {3}. "
				"Pay Paybill {4}, account {1}. Balance KES {5}."
			).format(tenant.tenant_name, lease.unit, _money(inv.outstanding_amount),
					 due.strftime("%d %b %Y"), settings.paybill_number, _money(inv.outstanding_amount))
			subject = _("Rent reminder: unit {0}").format(lease.unit)
			queue(inv, lease, tenant, "Rent Reminder", 0, subject, message, settings)

	elif days_overdue > 0:
		notice = overdue_notice_number(days_overdue, settings)
		if notice:
			message = _(
				"Dear {0}, rent for unit {1} was due {2} and is overdue. "
				"Balance KES {3}. Pay Paybill {4}, account {1}. Notice {5} of 3."
			).format(tenant.tenant_name, lease.unit, due.strftime("%d %b %Y"),
					 _money(inv.outstanding_amount), settings.paybill_number, notice)
			subject = _("Overdue rent: unit {0}").format(lease.unit)
			queue(inv, lease, tenant, "Overdue Notice", notice, subject, message, settings)


def queue(inv, lease, tenant, reminder_type, notice_number, subject, message, settings):
	channels = [("Email", tenant.email)]
	if settings.sms_enabled:
		channels.append(("SMS", tenant.phone_number))

	for channel, address in channels:
		if address:
			dispatch(inv, lease, reminder_type, notice_number, channel, address, subject, message)


def dispatch(inv, lease_doc, reminder_type, notice_number, channel, address, subject, message):
	# Claim the reminder before sending, so a second run cannot send it again.
	key = f"{inv.name}|{reminder_type}|{notice_number}|{channel}"
	row = frappe.db.get_value("Reminder Log", {"reminder_key": key}, ["name", "status", "attempts"], as_dict=True)

	if row:
		if row.status == "Sent" or row.attempts >= MAX_ATTEMPTS:
			return
		log = frappe.get_doc("Reminder Log", row.name)
	else:
		log = frappe.get_doc({
			"doctype": "Reminder Log",
			"reminder_key": key,
			"reminder_type": reminder_type,
			"notice_number": notice_number,
			"sales_invoice": inv.name,
			"lease": inv.lease,
			"tenant": lease_doc.tenant,
			"channel": channel,
			"recipient": address,
			"status": "Pending",
			"attempts": 0,
		}).insert(ignore_permissions=True)

	log.attempts += 1
	try:
		if channel == "Email":
			reference = messaging.send_email(address, subject, message, "Sales Invoice", inv.name)
		else:
			reference = messaging.send_sms(address, message)
		log.status = "Sent"
		log.sent_at = now_datetime()
		log.provider_reference = reference or ""
		log.error = ""
	except Exception as exc:
		log.status = "Failed"
		log.error = str(exc)[:500]
	log.save(ignore_permissions=True)


def _money(value):
	return f"{flt(value):,.2f}"
