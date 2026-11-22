def portal_request_query(user):
	if is_portal_user(user):
		s = portal_scope(user)
		return _any(_cond("`tabPortal Request`.`landlord`", [s.landlord] if s.landlord else []))
	return ""
