// Copyright (c) 2026, mnorg and contributors
// For license information, please see license.txt

frappe.ui.form.on("Work Order", {
	setup(frm) {
		frm.set_query("unit", () => ({ filters: { property: frm.doc.property } }));
		frm.set_query("maintenance_request", () => ({
			filters: { property: frm.doc.property, status: ["not in", ["Completed", "Closed", "Cancelled"]] },
		}));
	},

	refresh(frm) {
		const colours = { "Estimate Pending": "orange", Approved: "blue", "In Progress": "blue", Completed: "green", Cancelled: "gray" };
		frm.page.set_indicator(frm.doc.status, colours[frm.doc.status] || "gray");

		if (frm.doc.purchase_invoice) {
			frm.add_custom_button(__("Purchase Invoice"), () =>
				frappe.set_route("Form", "Purchase Invoice", frm.doc.purchase_invoice), __("View"));
		}
		if (frm.doc.maintenance_request) {
			frm.add_custom_button(__("Maintenance Request"), () =>
				frappe.set_route("Form", "Maintenance Request", frm.doc.maintenance_request), __("View"));
		}
	},

	assigned_to_type(frm) {
		// Clear the assignee that no longer applies.
		if (frm.doc.assigned_to_type === "Internal Staff") frm.set_value("contractor", null);
		if (frm.doc.assigned_to_type === "Contractor") frm.set_value("staff_user", null);
	},

	materials_add(frm) {
		frm.trigger("recalculate");
	},

	materials_remove(frm) {
		frm.trigger("recalculate");
	},

	labour_cost(frm) {
		frm.trigger("recalculate");
	},

	recalculate(frm) {
		const materials = (frm.doc.materials || []).reduce((sum, m) => sum + (m.quantity || 0) * (m.unit_cost || 0), 0);
		frm.set_value("total_cost", materials + (frm.doc.labour_cost || 0));
	},

	status(frm) {
		if (frm.doc.status === "In Progress" && frm.doc.estimate > 50000 && frm.doc.approval_status !== "Approved") {
			frappe.msgprint(__("Estimates above 50,000 must be approved before work starts."));
		}
		if (frm.doc.status === "Completed" && !frm.doc.cost_bearer) {
			frappe.msgprint(__("Choose who pays for this work before completing it."));
		}
	},
});

frappe.ui.form.on("Work Order Material", {
	quantity(frm, cdt, cdn) {
		frm.trigger("recalculate");
	},
	unit_cost(frm, cdt, cdn) {
		frm.trigger("recalculate");
	},
});
