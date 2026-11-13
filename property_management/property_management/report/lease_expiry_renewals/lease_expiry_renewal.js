frappe.query_reports["Lease Expiry and Renewals"] = {
	filters: [
		{ fieldname: "days", label: __("Days Ahead"), fieldtype: "Int", default: 90, reqd: 1 },
		{ fieldname: "property", label: __("Property"), fieldtype: "Link", options: "Property" },
	],
};
