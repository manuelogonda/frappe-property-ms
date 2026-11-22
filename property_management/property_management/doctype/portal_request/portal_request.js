// Copyright (c) 2026, mnorg and contributors
// For license information, please see license.txt

frappe.ui.form.on("Portal Request", {
	refresh(frm) {
		const colours = { Pending: "orange", Approved: "blue", Rejected: "red", Applied: "green" };
		frm.page.set_indicator(frm.doc.status, colours[frm.doc.status] || "gray");

		// Only the next allowed action is offered, so people don't try to skip a step.
		const roles = frappe.user_roles;
		if (frm.doc.status === "Pending" && roles.includes("Property Manager")) {
			frm.add_custom_button(__("Approve"), () => frm.set_value("status", "Approved").then(() => frm.save()));
			frm.add_custom_button(__("Reject"), () => frm.set_value("status", "Rejected").then(() => frm.save()));
		}
		if (frm.doc.status === "Approved" && roles.includes("Accounts Manager")) {
			frm.add_custom_button(__("Apply Change"), () =>
				frappe.confirm(__("Apply these details to the landlord record?"),
					() => frm.set_value("status", "Applied").then(() => frm.save())));
		}
	},

	status(frm) {
		frm.trigger("refresh");
	},
});
