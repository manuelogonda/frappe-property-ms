frappe.query_reports["Owner Statement"] = {
	filters: [
		{ fieldname: "property", label: __("Property"), fieldtype: "Link", options: "Property", reqd: 1 },
		{ fieldname: "from_date", label: __("From"), fieldtype: "Date", default: frappe.datetime.month_start(), reqd: 1 },
		{ fieldname: "to_date", label: __("To"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1 },
	],
};
