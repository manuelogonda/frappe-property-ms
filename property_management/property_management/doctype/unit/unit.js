// Copyright (c) 2026, mnorg and contributors
// For license information, please see license.txt

frappe.ui.form.on("Unit", {
	setup(frm) {
		frm.set_query("building", () => ({
			filters: { property: frm.doc.property, status: "Active" },
		}));
	},

	refresh(frm) {
		const colours = { Vacant: "green", Occupied: "blue", Reserved: "orange", Maintenance: "orange", Inactive: "gray" };
		frm.page.set_indicator(frm.doc.status, colours[frm.doc.status] || "gray");

		if (frm.is_new()) return;

		frm.add_custom_button(__("Leases"), () =>
			frappe.set_route("List", "Lease", { unit: frm.doc.name }), __("View"));
		if (frm.doc.building) {
			frm.add_custom_button(__("Building"), () =>
				frappe.set_route("Form", "Building", frm.doc.building), __("View"));
		}
	},

	async building(frm) {
		// Rule 16: choosing a building sets the property to match it.
		if (!frm.doc.building) return;
		const { message } = await frappe.db.get_value("Building", frm.doc.building, "property");
		if (message && message.property && frm.doc.property !== message.property) {
			frm.set_value("property", message.property);
		}
	},

	async property(frm) {
		// If the chosen building belongs to another property, clear it.
		if (!frm.doc.building || !frm.doc.property) return;
		const { message } = await frappe.db.get_value("Building", frm.doc.building, "property");
		if (message && message.property !== frm.doc.property) {
			frm.set_value("building", null);
		}
	},

	unit_code(frm) {
		const code = (frm.doc.unit_code || "").trim().toUpperCase();
		if (code !== frm.doc.unit_code) {
			frm.set_value("unit_code", code);
		}
	},

	monthly_rent(frm) {
		// Rule 18: warning only.
		if (frm.doc.monthly_rent !== undefined && frm.doc.monthly_rent <= 0) {
			frappe.show_alert({ message: __("Monthly rent must be greater than zero."), indicator: "red" });
		}
	},

	status(frm) {
		// Rule 19: Occupied is set through the lease, not by hand.
		if (frm.doc.status === "Occupied") {
			frappe.msgprint(__("Occupied is set automatically when a lease becomes Active. Choose another status."));
		}
	},
});
