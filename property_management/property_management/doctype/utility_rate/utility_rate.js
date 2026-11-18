// Copyright (c) 2026, mnorg and contributors
// For license information, please see license.txt

frappe.ui.form.on("Utility Rate", {
	refresh(frm) {
		const colours = { Electricity: "blue", Water: "teal" };
		frm.page.set_indicator(frm.doc.utility_type || __("Utility"), colours[frm.doc.utility_type] || "gray");

		if (!frm.is_new()) {
			frm.add_custom_button(__("Utility Bills"), () =>
				frappe.set_route("List", "Utility Bill", { utility_rate: frm.doc.name }), __("View"));
		}
		frm.trigger("explain_tax");
	},

	effective_to(frm) {
		if (frm.doc.effective_to && frm.doc.effective_from && frm.doc.effective_to < frm.doc.effective_from) {
			frappe.show_alert({ message: __("Effective To cannot be before Effective From."), indicator: "red" });
		}
	},

	rate_per_unit(frm) {
		if (frm.doc.rate_per_unit !== undefined && frm.doc.rate_per_unit <= 0) {
			frappe.show_alert({ message: __("Rate per unit must be greater than zero."), indicator: "red" });
		}
	},

	tax_treatment(frm) {
		frm.trigger("explain_tax");
	},

	explain_tax(frm) {
		const notes = {
			Excluded: __("The rate is before tax. Tax is added on the bill as set by the accountant."),
			Included: __("The rate already includes tax. The bill will show the tax portion, not add it."),
			"Added on top": __("Tax is added to the rate on each bill."),
		};
		frm.set_df_property("tax_treatment", "description", notes[frm.doc.tax_treatment] || "");
	},
});
