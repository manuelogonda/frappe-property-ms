// Copyright (c) 2026, mnorg and contributors
// For license information, please see license.txt

frappe.ui.form.on("Building", {
	refresh(frm) {
		const colours = { Active: "green", Inactive: "gray" };
		frm.page.set_indicator(frm.doc.status, colours[frm.doc.status] || "gray");

		if (!frm.is_new()) {
			frm.add_custom_button(__("Units"), () =>
				frappe.set_route("List", "Unit", { building: frm.doc.name }), __("View"));
			frm.add_custom_button(__("Property"), () =>
				frappe.set_route("Form", "Property", frm.doc.property), __("View"));

			// Lock the fields that unit names depend on, once units exist.
			frappe.db.count("Unit", { building: frm.doc.name }).then((count) => {
				if (count > 0) {
					frm.set_df_property("property", "read_only", 1);
					frm.set_df_property("building_code", "read_only", 1);
					frm.dashboard.set_headline(
						__("This building has {0} unit(s). Its property and building code are locked.", [count])
					);
				}
			});
		}
	},

	building_code(frm) {
		const code = (frm.doc.building_code || "").trim().toUpperCase();
		if (code !== frm.doc.building_code) {
			frm.set_value("building_code", code);
		}
	},

	number_of_floors(frm) {
		if (frm.doc.number_of_floors !== null && frm.doc.number_of_floors !== undefined && frm.doc.number_of_floors < 1) {
			frappe.show_alert({ message: __("Number of floors must be at least 1."), indicator: "red" });
		}
	},

	status(frm) {
		if (frm.doc.status === "Inactive" && !frm.is_new()) {
			frappe.show_alert({
				message: __("Inactive buildings stay linked to their units. Units keep their own status."),
				indicator: "orange",
			});
		}
	},
});
