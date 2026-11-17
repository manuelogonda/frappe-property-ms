// Copyright (c) 2026, mnorg and contributors
// For license information, please see license.txt

frappe.ui.form.on("Tenant", {
	refresh(frm) {
		const colours = { Pending: "orange", Verified: "green", Inactive: "gray" };
		frm.page.set_indicator(frm.doc.status, colours[frm.doc.status] || "gray");
		frm.trigger("set_id_label");

		if (frm.doc.customer) {
			frm.add_custom_button(__("ERPNext Customer"), () =>
				frappe.set_route("Form", "Customer", frm.doc.customer), __("View"));
		}
		if (!frm.is_new()) {
			frm.add_custom_button(__("Leases"), () =>
				frappe.set_route("List", "Lease", { tenant: frm.doc.name }), __("View"));
		}
		// Rule 30: the tenant type is locked once a customer exists.
		frm.set_df_property("tenant_type", "read_only", frm.doc.customer ? 1 : 0);
	},

	tenant_type(frm) {
		frm.trigger("set_id_label");
	},

	set_id_label(frm) {
		// Company shows a registration number. Individual, or no type yet, shows a national ID.
		const isCompany = (frm.doc.tenant_type || "").toLowerCase() === "company";

		const label = isCompany ? __("Registration Number") : __("National ID Number");
		const hint = isCompany
			? __("Enter the company's registration number.")
			: __("Enter the individual's national ID number.");

		frm.set_df_property("id_number_or_registration_number", "label", label);
		frm.set_df_property("id_number_or_registration_number", "description", hint);
		frm.refresh_field("id_number_or_registration_number");
	},

	// set_id_label(frm) {
	// 	const label = frm.doc.tenant_type === "Company" ? __("Registration Number") : __("National ID Number");
	// 	frm.set_df_property("id_number_or_registration_number", "label", label);
	// },

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

	email(frm) {
		if (frm.doc.email) {
			frm.set_value("email", frm.doc.email.trim().toLowerCase());
		}
	},

	status(frm) {
		// Rule 29: warning only. The server blocks the save.
		if (frm.doc.status === "Verified") {
			const missing = [];
			if (!frm.doc.kyc_documents) missing.push(__("KYC documents"));
			if (!frm.doc.kra_pin) missing.push(__("KRA PIN"));
			if (!frm.doc.consent_given) missing.push(__("consent"));
			if (!(frm.doc.emergency_contacts || []).length) missing.push(__("an emergency contact"));
			if (missing.length) {
				frappe.msgprint(__("Before this tenant can be Verified, add: {0}.", [missing.join(", ")]));
			}
		}
		if (frm.doc.status === "Inactive" && frm.doc.customer) {
			frappe.show_alert({
				message: __("The linked customer will be disabled when you save."),
				indicator: "orange",
			});
		}
	},
});
