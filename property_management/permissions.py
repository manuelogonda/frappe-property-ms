def portal_request_query(user):
	if is_portal_user(user):
		s = portal_scope(user)
		return _any(_cond("`tabPortal Request`.`landlord`", [s.landlord] if s.landlord else []))
	return ""

def landlord_query(user):
	if is_portal_user(user):
		s = portal_scope(user)
		return _any(_cond("`tabLandlord`.`name`", [s.landlord] if s.landlord else []))
	return ""

def lease_query(user):
	if is_portal_user(user):
		s = portal_scope(user)
		return _any(
			_cond("`tabLease`.`tenant`", [s.tenant] if s.tenant else []),
			_cond("`tabLease`.`property`", s.properties),
		)
	return ""


def tenant_query(user):
	if is_portal_user(user):
		s = portal_scope(user)
		return _any(_cond("`tabTenant`.`name`", [s.tenant] if s.tenant else []))
	return ""


def property_query(user):
	if is_portal_user(user):
		s = portal_scope(user)
		return _any(_cond("`tabProperty`.`name`", s.properties))
	return ""


def maintenance_request_query(user):
	if is_portal_user(user):
		s = portal_scope(user)
		return _any(
			_cond("`tabMaintenance Request`.`tenant`", [s.tenant] if s.tenant else []),
			_cond("`tabMaintenance Request`.`property`", s.properties),
		)
	return ""


def work_order_query(user):
	if is_portal_user(user):
		s = portal_scope(user)
		return _any(_cond("`tabWork Order`.`property`", s.properties))
	return ""


def sales_invoice_query(user):
	if is_portal_user(user):
		s = portal_scope(user)
		return _any(_cond("`tabSales Invoice`.`customer`", [s.customer] if s.customer else []))
	return ""


def payment_entry_query(user):
	if is_portal_user(user):
		s = portal_scope(user)
		return _any(_cond("`tabPayment Entry`.`party`", [s.customer] if s.customer else []))
	return ""

import frappe
from frappe import _


def is_portal_user(user):
	return frappe.get_cached_value("User", user, "user_type") == "Website User"


def portal_scope(user):
	"""The tenant, landlord, properties and customer linked to this portal login."""
	tenant = frappe.db.get_value("Tenant", {"user": user}, ["name", "customer"], as_dict=True)
	landlord = frappe.db.get_value("Landlord", {"user": user}, "name")
	properties = []
	if landlord:
		properties = frappe.get_all("Property Landlord", filters={"landlord": landlord}, pluck="parent")
	return frappe._dict(
		tenant=tenant.name if tenant else None,
		customer=tenant.customer if tenant else None,
		landlord=landlord,
		properties=properties,
	)


def _sql_in(values):
	return ", ".join(frappe.db.escape(v) for v in values)


def _cond(column, values):
	return f"{column} in ({_sql_in(values)})" if values else None


def _any(*clauses):
	clauses = [c for c in clauses if c]
	return f"({' or '.join(clauses)})" if clauses else "1=0"
