// Copyright (c) 2026, mnorg and contributors
// For license information, please see license.txt

frappe.ui.form.on("Management Agreement", {
	refresh(frm) {
		const colours = { Draft: "gray", Active: "green", Expired: "orange", Terminated: "red" };
		frm.page.set_indicator(frm.doc.status, colours[frm.doc.status] || "gray");

		if (!frm.is_new()) {
			frm.add_custom_button(__("Property"), () =>
				frappe.set_route("Form", "Property", frm.doc.property), __("View"));
			frm.add_custom_button(__("Leases"), () =>
				frappe.set_route("List", "Lease", { management_agreement: frm.doc.name }), __("View"));
		}
	},

	agreement_number(frm) {
		const number = (frm.doc.agreement_number || "").trim().toUpperCase();
		if (number !== frm.doc.agreement_number) {
			frm.set_value("agreement_number", number);
		}
	},

	fee_structure(frm) {
		// Clear the fee that does not apply, so the record holds one fee only.
		if (frm.doc.fee_structure === "Percentage") {
			frm.set_value("fixed_management_fee", 0);
		} else if (frm.doc.fee_structure === "Fixed Amount") {
			frm.set_value("management_fee_percent", 0);
		}
	},

	management_fee_percent(frm) {
		if (frm.doc.management_fee_percent && (frm.doc.management_fee_percent <= 0 || frm.doc.management_fee_percent > 100)) {
			frappe.show_alert({ message: __("Management fee must be above 0% and at most 100%."), indicator: "red" });
		}
	},

	fixed_management_fee(frm) {
		if (frm.doc.fixed_management_fee !== undefined && frm.doc.fixed_management_fee <= 0 && frm.doc.fee_structure === "Fixed Amount") {
			frappe.show_alert({ message: __("Fixed management fee must be greater than zero."), indicator: "red" });
		}
	},

	start_date(frm) {
		frm.trigger("check_dates");
	},

	end_date(frm) {
		frm.trigger("check_dates");
	},

	check_dates(frm) {
		if (frm.doc.start_date && frm.doc.end_date && frm.doc.end_date <= frm.doc.start_date) {
			frappe.show_alert({ message: __("End date must be later than the start date."), indicator: "red" });
		}
	},

	status(frm) {
		if (frm.doc.status !== "Active") return;

		if (!frm.doc.agreement_document) {
			frappe.msgprint(__("Attach the signed agreement before setting the status to Active."));
		}
		if (frm.doc.end_date && frm.doc.end_date < frappe.datetime.get_today()) {
			frappe.msgprint(__("The end date has passed. This agreement should be Expired, not Active."));
		}
	},
});
