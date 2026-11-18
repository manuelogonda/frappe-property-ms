// Copyright (c) 2026, mnorg and contributors
// For license information, please see license.txt

frappe.ui.form.on("Meter Reading", {
	setup(frm) {
		frm.set_query("meter", () => ({ filters: { status: "Active" } }));
	},

	refresh(frm) {
		const billed = frm.doc.billed;
		frm.page.set_indicator(billed ? "Billed" : "Unbilled", billed ? "green" : "orange");

		// A billed reading is locked on screen as well as on the server.
		if (billed) {
			frm.disable_form();
			frm.dashboard.set_headline(__("This reading has been billed and is locked."));
		}
		if (frm.doc.utility_bill) {
			frm.add_custom_button(__("Utility Bill"), () =>
				frappe.set_route("Form", "Utility Bill", frm.doc.utility_bill), __("View"));
		}
	},

	meter(frm) {
		// Show the previous reading as a preview, so the reader sees the baseline before typing.
		if (!frm.doc.meter) return;
		frappe.db.get_list("Meter Reading", {
			filters: { meter: frm.doc.meter },
			fields: ["reading_value", "reading_date"],
			order_by: "reading_date desc",
			limit: 1,
		}).then((rows) => {
			if (rows.length) {
				frm.set_df_property("reading_value", "description",
					__("Last reading: {0} on {1}", [rows[0].reading_value, rows[0].reading_date]));
			}
		});
	},

	reading_value(frm) {
		if (frm.doc.previous_reading !== undefined && frm.doc.reading_value < frm.doc.previous_reading) {
			frappe.show_alert({
				message: __("This is lower than the last reading. Check the value."),
				indicator: "orange",
			});
		}
	},

	reading_type(frm) {
		if (frm.doc.reading_type === "Estimated") {
			frappe.msgprint(__("Estimated readings cannot be billed. Take an actual reading before billing this period."));
		}
	},
});
