import frappe


class SMSNotConfigured(Exception):
	pass


def send_email(recipient, subject, message, reference_doctype, reference_name):
	# Queued by Frappe. "Sent" here means handed to the email queue, not delivered.
	frappe.sendmail(
		recipients=[recipient],
		subject=subject,
		message=message,
		reference_doctype=reference_doctype,
		reference_name=reference_name,
	)
	return ""


def send_sms(phone, message):
	# Interface only. Connect the chosen provider here and return its message reference.
	raise SMSNotConfigured("No SMS provider is connected.")
