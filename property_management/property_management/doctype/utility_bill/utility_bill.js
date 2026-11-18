// Copyright (c) 2026, mnorg and contributors
// For license information, please see license.txt

frappe.ui.form.on("Utility Bill", {
	refresh(frm) {
		const colours = { Draft: "gray", Calculated: "blue", Invoiced: "green", Cancelled: "red" };
		frm.page.set_indicator(frm.doc.status, colours[frm.doc.status] || "gray");

		if (frm.doc.status === "Calculated" && !frm.doc.sales_invoice) {
			frm.add_custom_button(__("Create Invoice"), () => {
				frappe.confirm(
					__("Invoice {0} to the tenant? The readings will be locked.", [frm.doc.total]),
					() => frm.call("create_invoice").then(() => frm.reload_doc())
				);
			});
		}
		if (frm.doc.sales_invoice) {
			frm.add_custom_button(__("Sales Invoice"), () =>
				frappe.set_route("Form", "Sales Invoice", frm.doc.sales_invoice), __("View"));
		}
		if (frm.doc.status === "Invoiced" || frm.doc.status === "Cancelled") {
			frm.disable_form();
		}
	},

	meter(frm) {
		frm.set_df_property("billing_end_date", "description", __("Choose a period that both ends have readings for."));
	},
});
