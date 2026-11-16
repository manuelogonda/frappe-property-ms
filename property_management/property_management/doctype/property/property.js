// Copyright (c) 2026, mnorg and contributors
// For license information, please see license.txt

frappe.ui.form.on("Property", {
	refresh(frm) {
		const colours = { Draft: "orange", Active: "green", Inactive: "gray" };
		frm.page.set_indicator(frm.doc.status, colours[frm.doc.status] || "gray");

		if (!frm.is_new()) {
			// Rule 3: the code is locked once the property exists.
			frm.set_df_property("property_code", "read_only", 1);

			frm.add_custom_button(__("Buildings"), () =>
				frappe.set_route("List", "Building", { property: frm.doc.name }), __("View"));
			frm.add_custom_button(__("Units"), () =>
				frappe.set_route("List", "Unit", { property: frm.doc.name }), __("View"));
			frm.add_custom_button(__("Management Agreements"), () =>
				frappe.set_route("List", "Management Agreement", { property: frm.doc.name }), __("View"));
		}
		frm.trigger("show_share_summary");
	},

	property_code(frm) {
		const code = (frm.doc.property_code || "").trim().toUpperCase();
		if (code !== frm.doc.property_code) {
			frm.set_value("property_code", code);
		}
	},

	status(frm) {
		// Rule 7: Active needs a landlord. The server also checks the agreement.
		if (frm.doc.status === "Active" && !(frm.doc.landlords || []).length) {
			frappe.msgprint(__("Add at least one landlord before setting this property to Active."));
		}
	},

	landlords_add(frm, cdt, cdn) {
		// The first landlord becomes the primary contact by default.
		if ((frm.doc.landlords || []).length === 1) {
			frappe.model.set_value(cdt, cdn, "is_primary_contact", 1);
		}
		frm.trigger("show_share_summary");
	},

	landlords_remove(frm) {
		frm.trigger("show_share_summary");
	},

	show_share_summary(frm) {
		const rows = frm.doc.landlords || [];
		if (!rows.length) {
			frm.dashboard.clear_headline();
			return;
		}
		const total = rows.reduce((sum, r) => sum + (parseFloat(r.share_percentage) || 0), 0);
		const primaries = rows.filter((r) => r.is_primary_contact).length;
		const ok = Math.abs(total - 100) < 0.001 && primaries === 1;
		frm.dashboard.set_headline(
			ok
				? __("Shares total 100%, one primary contact.")
				: __("Shares total {0}%, primary contacts: {1}. Fix before saving.", [total.toFixed(2), primaries])
		);
	},

	validate(frm) {
		const rows = frm.doc.landlords || [];
		if (!rows.length) return;
		const total = rows.reduce((sum, r) => sum + (parseFloat(r.share_percentage) || 0), 0);
		if (Math.abs(total - 100) > 0.001) {
			frappe.throw(__("Landlord shares must total 100%. Current total is {0}%.", [total.toFixed(2)]));
		}
	},
});

frappe.ui.form.on("Property Landlord", {
	is_primary_contact(frm, cdt, cdn) {
		// Only one primary contact at a time.
		const row = locals[cdt][cdn];
		if (!row.is_primary_contact) return;
		(frm.doc.landlords || []).forEach((r) => {
			if (r.name !== row.name) r.is_primary_contact = 0;
		});
		frm.refresh_field("landlords");
		frm.trigger("show_share_summary");
	},

	share_percentage(frm) {
		frm.trigger("show_share_summary");
	},

	async landlord(frm, cdt, cdn) {
		// Rule 6 warning only. The child controller blocks the save.
		const row = locals[cdt][cdn];
		if (!row.landlord) return;
		const { message } = await frappe.db.get_value("Landlord", row.landlord, "status");
		if (message && ["Rejected", "Inactive"].includes(message.status)) {
			frappe.msgprint(__("Landlord {0} is {1} and cannot be linked to a property.", [row.landlord, message.status]));
		}
	},
});
