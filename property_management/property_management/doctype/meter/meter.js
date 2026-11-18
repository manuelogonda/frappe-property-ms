// Copyright (c) 2026, mnorg and contributors
// For license information, please see license.txt

frappe.ui.form.on("Meter", {
	setup(frm) {
		frm.set_query("unit", () => ({ filters: { property: frm.doc.property } }));
		frm.set_query("replaced_by", () => ({
			filters: { property: frm.doc.property, utility_type: frm.doc.utility_type, status: "Active" },
		}));
	},

	refresh(frm) {
		const colours = { Active: "green", Replaced: "orange", Inactive: "gray" };
		frm.page.set_indicator(frm.doc.status, colours[frm.doc.status] || "gray");

		if (!frm.is_new()) {
			frm.add_custom_button(__("Readings"), () =>
				frappe.set_route("List", "Meter Reading", { meter: frm.doc.name }), __("View"));
		}
		frm.trigger("apply_meter_type");
	},

	meter_number(frm) {
		const number = (frm.doc.meter_number || "").trim().toUpperCase();
		if (number !== frm.doc.meter_number) {
			frm.set_value("meter_number", number);
		}
	},

	meter_type(frm) {
		frm.trigger("apply_meter_type");
	},

	apply_meter_type(frm) {
		// A bulk meter has no unit. An individual or sub-meter must have one.
		const isBulk = frm.doc.meter_type === "Bulk";
		frm.set_df_property("unit", "reqd", isBulk ? 0 : 1);
		frm.set_df_property("unit", "hidden", isBulk ? 1 : 0);
		if (isBulk && frm.doc.unit) frm.set_value("unit", null);
	},

	property(frm) {
		frm.set_value("unit", null);
	},

	status(frm) {
		frm.toggle_display("section_replacement", frm.doc.status === "Replaced");
		if (frm.doc.status === "Replaced") {
			frappe.msgprint(__("Choose the meter that replaced this one."));
		}
	},
});
