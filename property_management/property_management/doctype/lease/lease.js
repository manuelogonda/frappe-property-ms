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
			if (frm.doc.tenant) {
				frm.add_custom_button(__("Tenant"), () => frappe.set_route("Form", "Tenant", frm.doc.tenant), __("View"));
			}
			if (frm.doc.unit) {
				frm.add_custom_button(__("Unit"), () => frappe.set_route("Form", "Unit", frm.doc.unit), __("View"));
			}
		}
	},

	property(frm) {
		// A different property means a different unit and agreement.
		frm.set_value("unit", null);
		frm.set_value("management_agreement", null);
	},

	async unit(frm) {
		if (!frm.doc.unit) return;
		const { message: unit } = await frappe.db.get_value(
			"Unit", frm.doc.unit, ["monthly_rent", "security_deposit", "status"]
		);
		if (!unit) return;

		// Fill rent and deposit from the unit only when they are empty, so a negotiated figure is not overwritten.
		if (!frm.doc.monthly_rent) frm.set_value("monthly_rent", unit.monthly_rent);
		if (!frm.doc.security_deposit) frm.set_value("security_deposit", unit.security_deposit);

		if (unit.status === "Occupied" && frm.doc.status !== "Active") {
			frappe.show_alert({
				message: __("This unit is currently occupied. Check its existing lease before continuing."),
				indicator: "orange",
			});
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
			frappe.show_alert({
				message: __("End date must be later than the start date."),
				indicator: "red",
			});
		}
	},

	payment_due_day(frm) {
		const day = cint(frm.doc.payment_due_day);
		if (frm.doc.payment_due_day && (day < 1 || day > 28)) {
			frappe.show_alert({
				message: __("Payment due day must be between 1 and 28."),
				indicator: "red",
			});
		}
	},

	monthly_rent(frm) {
		if (frm.doc.monthly_rent !== undefined && frm.doc.monthly_rent <= 0) {
			frappe.show_alert({ message: __("Monthly rent must be greater than zero."), indicator: "red" });
		}
	},

	async status(frm) {
		if (frm.doc.status !== "Active") return;

		const missing = [];
		if (!frm.doc.lease_document) missing.push(__("signed lease"));

		const { message: tenant } = await frappe.db.get_value("Tenant", frm.doc.tenant, "status");
		if (!tenant || tenant.status !== "Verified") missing.push(__("a Verified tenant"));

		if (missing.length) {
			frappe.msgprint(__("Before this lease can be Active, add: {0}.", [missing.join(", ")]));
		}
	},
});
