// Copyright (c) 2026, mnorg and contributors
// For license information, please see license.txt

frappe.ui.form.on("Inspection", {
	setup(frm) {
		frm.set_query("lease", () => ({
			filters: { status: "Active" },
		}));
	},

	refresh(frm) {
		const colours = { Draft: "orange", Signed: "green", Disputed: "red" };
		frm.page.set_indicator(frm.doc.status, colours[frm.doc.status] || "gray");

		if (frm.doc.status === "Signed") {
			frm.disable_form();
			frm.dashboard.set_headline(__("This inspection is signed and locked. Create a new inspection to record changes."));
		}

		if (frm.doc.lease) {
			frm.add_custom_button(__("Lease"), () =>
				frappe.set_route("Form", "Lease", frm.doc.lease), __("View"));
		}
		if (frm.doc.unit) {
			frm.add_custom_button(__("Unit"), () =>
				frappe.set_route("Form", "Unit", frm.doc.unit), __("View"));
		}
		if (!frm.is_new() && frm.doc.status === "Draft") {
			frm.add_custom_button(__("Mark as Disputed"), () => {
				frappe.prompt(
					{ fieldname: "reason", label: __("Reason"), fieldtype: "Small Text", reqd: 1 },
					(values) => {
						frm.set_value("tenant_comments", values.reason);
						frm.set_value("status", "Disputed");
						frm.save();
					},
					__("Dispute this inspection")
				);
			});
		}
	},

	lease(frm) {
		frm.set_value("unit", null);
		frm.set_value("tenant", null);
	},

	tenant_signed(frm) {
		if (frm.doc.tenant_signed) {
			frappe.confirm(
				__("By signing, the tenant agrees this condition report is accurate. The inspection will be locked. Continue?"),
				() => {},
				() => frm.set_value("tenant_signed", 0)
			);
		}
	},

	validate(frm) {
		const items = frm.doc.items || [];
		if (!items.length) {
			frappe.throw(__("Add at least one checklist item."));
		}
		const poorWithoutPhoto = items.filter((r) => r.condition === "Poor" && !r.photo);
		if (poorWithoutPhoto.length) {
			frappe.throw(__("Attach a photo for every item in Poor condition ({0}).",
				[poorWithoutPhoto.map((r) => r.item).join(", ")]));
		}
	},
});

frappe.ui.form.on("Inspection Item", {
	condition(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (row.condition === "Poor" && !row.photo) {
			frappe.show_alert({
				message: __("Poor condition needs a photo before the inspection can be saved."),
				indicator: "orange",
			});
		}
		frm.trigger("preview_overall");
	},

	items_remove(frm) {
		frm.trigger("preview_overall");
	},

	photo(frm) {
		frm.trigger("preview_overall");
	},
});

frappe.ui.form.on("Inspection", {
	preview_overall(frm) {
		// Show the worst rating as a preview. The server sets the final value on save.
		const rank = { Good: 1, Fair: 2, Poor: 3 };
		const ratings = (frm.doc.items || []).map((r) => rank[r.condition]).filter(Boolean);
		if (!ratings.length) {
			frm.dashboard.clear_headline();
			return;
		}
		const worst = Object.keys(rank).find((k) => rank[k] === Math.max(...ratings));
		frm.dashboard.set_headline(__("Overall condition so far: {0}", [worst]));
	},
});
