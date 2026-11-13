frappe.query_reports["Occupancy Report"] = {
	filters: [
		{ fieldname: "property", label: __("Property"), fieldtype: "Link", options: "Property" },
	],
};
