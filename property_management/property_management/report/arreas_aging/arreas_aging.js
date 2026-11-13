frappe.query_reports["Arrears Ageing"] = {
	filters: [
		{ fieldname: "as_of", label: __("As Of"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1 },
		{ fieldname: "from_date", label: __("Collection Period From"), fieldtype: "Date", default: frappe.datetime.month_start() },
		{ fieldname: "to_date", label: __("Collection Period To"), fieldtype: "Date", default: frappe.datetime.get_today() },
		{ fieldname: "property", label: __("Property"), fieldtype: "Link", options: "Property" },
	],
};
