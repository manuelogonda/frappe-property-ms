// Copyright (c) 2026, mnorg and contributors
// For license information, please see license.txt

frappe.ui.form.on("Lease", {
	setup(frm) {
		frm.set_query("tenant", () => ({ filters: { status: "Verified" } }));
		frm.set_query("unit", () => ({ filters: { property: frm.doc.property } }));
		frm.set_query("management_agreement", () => ({
			filters: { property: frm.doc.property, status: "Active" },
		}));
	},

	refresh(frm) {
		const colours = { Draft: "gray", "Pending Approval": "orange", Active: "green", Expired: "gray", Terminated: "red" };
		frm.page.set_indicator(frm.doc.status, colours[frm.doc.status] || "gray");

		if (!frm.is_new()) {
			frm.add_custom_button(__("Tenant"), () => frappe.set_route("Form", "Tenant", frm.doc.tenant), __("View"));
			frm.add_custom_button(__("Unit"), () => frappe.set_route("Form", "Unit", frm.doc.unit), __("View"));
			frm.add_custom_button(__("Rent Schedule"), () => frm.scroll_to_field("rent_schedule"), __("View"));
		}
	},

	property(frm) {
		// A different property means a different unit and agreement.
		frm.set_value("unit", null);
		frm.set_value("management_agreement", null);
	},

	async unit(frm) {
		// Fill rent and deposit from the unit only when empty, so an agreed figure is not overwritten.
		if (!frm.doc.unit) return;
		const { message: unit } = await frappe.db.get_value("Unit", frm.doc.unit, ["monthly_rent", "security_deposit", "status"]);
		if (!unit) return;
		if (!frm.doc.rent_amount) frm.set_value("rent_amount", unit.monthly_rent);
		if (!frm.doc.security_deposit) frm.set_value("security_deposit", unit.security_deposit);
		if (unit.status === "Occupied" && frm.doc.status !== "Active") {
			frappe.show_alert({ message: __("This unit is occupied. Check its existing lease first."), indicator: "orange" });
		}
	},

	start_date(frm) {
		frm.trigger("check_dates");
	},

	end_date(frm) {
		frm.trigger("check_dates");
	},

	check_dates(frm) {
		// Rule 41: only when an end date is entered.
		if (frm.doc.start_date && frm.doc.end_date && frm.doc.end_date <= frm.doc.start_date) {
			frappe.show_alert({ message: __("End date must be later than the start date."), indicator: "red" });
		}
	},

	payment_due_day(frm) {
		// Rule 42: warning only.
		const day = parseInt(frm.doc.payment_due_day, 10);
		if (frm.doc.payment_due_day && (day < 1 || day > 28)) {
			frappe.show_alert({ message: __("Payment due day must be between 1 and 28."), indicator: "red" });
		}
	},

	rent_amount(frm) {
		if (frm.doc.rent_amount !== undefined && frm.doc.rent_amount <= 0) {
			frappe.show_alert({ message: __("Rent amount must be greater than zero."), indicator: "red" });
		}
	},

	notice_served_date(frm) {
		// The effective date is calculated, so it follows the served date and notice period.
		if (frm.doc.notice_served_date && frm.doc.notice_period) {
			const effective = frappe.datetime.add_days(frm.doc.notice_served_date, frm.doc.notice_period);
			frm.set_value("notice_effective_date", effective);
		}
	},

	status(frm) {
		// Rule 46: warnings only. The server blocks the save.
		if (frm.doc.status === "Active") {
			const missing = [];
			if (!frm.doc.lease_document) missing.push(__("signed lease"));
			if (missing.length) {
				frappe.msgprint(__("Before this lease can be Active, add: {0}.", [missing.join(", ")]));
			}
		}
	},
});
