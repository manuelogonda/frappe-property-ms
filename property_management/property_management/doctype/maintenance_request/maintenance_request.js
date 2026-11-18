// Copyright (c) 2026, mnorg and contributors
// For license information, please see license.txt

frappe.ui.form.on("Maintenance Request", {
	setup(frm) {
		frm.set_query("unit", () => ({ filters: { property: frm.doc.property } }));
		frm.set_query("tenant", () => ({
			filters: { status: "Verified" },
		}));
	},

	refresh(frm) {
		const colours = { Open: "orange", Assigned: "blue", "In Progress": "blue", Completed: "green", Closed: "gray", Cancelled: "gray" };
		frm.page.set_indicator(frm.doc.status, colours[frm.doc.status] || "gray");

		if (!frm.is_new() && frm.doc.work_order) {
			frm.add_custom_button(__("Work Order"), () =>
				frappe.set_route("Form", "Work Order", frm.doc.work_order), __("View"));
		}
		frm.toggle_display("tenant", !frm.doc.reported_by_staff);
	},

	reported_by_staff(frm) {
		frm.toggle_display("tenant", !frm.doc.reported_by_staff);
		if (frm.doc.reported_by_staff) frm.set_value("tenant", null);
	},

	unit(frm) {
		// Filter the tenant to those who hold an active lease on this unit.
		frm.set_query("tenant", () => ({
			filters: { name: ["in", frm.doc.unit ? [] : []] },
		}));
	},

	priority(frm) {
		if (frm.doc.priority === "Emergency") {
			frappe.msgprint(__("Emergency requests are sent for immediate attention. Confirm the property manager has been told."));
		}
	},
});
