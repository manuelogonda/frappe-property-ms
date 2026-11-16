// Copyright (c) 2026, mnorg and contributors
// For license information, please see license.txt

frappe.ui.form.on("Landlord", {
	refresh(frm) {
		const colours = { Pending: "orange", Verified: "green", Rejected: "red", Inactive: "gray" };
		frm.page.set_indicator(frm.doc.status, colours[frm.doc.status] || "gray");
		frm.trigger("set_id_label");
		frm.trigger("set_payout_fields");
	},

	landlord_type(frm) {
		frm.trigger("set_id_label");
	},

	set_id_label(frm) {
		const label = frm.doc.landlord_type === "Company" ? __("Registration Number") : __("National ID Number");
		frm.set_df_property("id_number_or_registration_number", "label", label);
	},

	preferred_payment_method(frm) {
		frm.trigger("set_payout_fields");
	},

	set_payout_fields(frm) {
		// Show only the detail for the chosen method, to keep the form clear.
		const isMpesa = frm.doc.preferred_payment_method === "M-Pesa";
		const isBank = frm.doc.preferred_payment_method === "Bank Transfer";
		frm.set_df_property("mpesa_phone_number", "hidden", isBank ? 1 : 0);
		["bank_name", "bank_branch", "bank_account_name", "bank_account_number"].forEach((f) =>
			frm.set_df_property(f, "hidden", isMpesa ? 1 : 0)
		);
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
		// Rule 24: warning only. The server blocks the save.
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
