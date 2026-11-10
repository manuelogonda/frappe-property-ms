// Copyright (c) 2026, mnorg and contributors
// For license information, please see license.txt

frappe.ui.form.on("Landlord", {
	refresh(frm) {
		const colours = { Pending: "orange", Verified: "green", Rejected: "red", Inactive: "gray" };
		frm.page.set_indicator(frm.doc.status, colours[frm.doc.status] || "gray");
		frm.trigger("set_id_label");
	},

	landlord_type(frm) {
		frm.trigger("set_id_label");
	},

	set_id_label(frm) {
		const label = frm.doc.landlord_type === "Company" ? __("Registration Number") : __("National ID Number");
		frm.set_df_property("id_number_or_registration_number", "label", label);
	},

	kra_pin(frm) {
		const pin = (frm.doc.kra_pin || "").trim().toUpperCase();
		if (pin !== frm.doc.kra_pin) {
			frm.set_value("kra_pin", pin);
		}
		if (pin && !/^[A-Z]\d{9}[A-Z]$/.test(pin)) {
			frappe.show_alert({
				message: __("KRA PIN should be one letter, nine digits, and one letter."),
				indicator: "orange",
			});
		}
	},

	status(frm) {
		if (frm.doc.status === "Verified") {
			const missing = [];
			if (!frm.doc.kyc_documents) missing.push(__("KYC documents"));
			if (!frm.doc.kra_pin) missing.push(__("KRA PIN"));
			if (missing.length) {
				frappe.msgprint(__("Before this landlord can be Verified, add: {0}.", [missing.join(", ")]));
			}
		}
		if (["Rejected", "Inactive"].includes(frm.doc.status)) {
			frappe.show_alert({
				message: __("This landlord cannot be linked to new properties."),
				indicator: "orange",
			});
		}
	},
});
