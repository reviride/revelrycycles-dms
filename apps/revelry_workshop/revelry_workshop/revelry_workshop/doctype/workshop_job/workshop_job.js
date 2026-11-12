// Copyright (c) 2026, Revelry Cycles
// License: GPLv3

frappe.ui.form.on("Workshop Job", {
	refresh(frm) {
		if (!frm.is_new() && frm.doc.status === "Approved" && !frm.doc.sales_invoice) {
			frm.add_custom_button(__("Invoice"), () => {
				frappe.call({
					method: "revelry_workshop.revelry_workshop.invoicing.make_sales_invoice",
					args: { job: frm.doc.name },
					freeze: true,
					callback: (r) => r.message && frappe.set_route("Form", "Sales Invoice", r.message),
				});
			}).addClass("btn-primary");
		}
		if (!frm.is_new() && !["Invoiced", "Cancelled"].includes(frm.doc.status)) {
			frm.add_custom_button(__("Take Deposit"), () => {
				const d = new frappe.ui.Dialog({
					title: __("Take Deposit"),
					fields: [
						{ fieldname: "amount", fieldtype: "Currency", label: __("Amount"), reqd: 1 },
						{ fieldname: "mode_of_payment", fieldtype: "Link", options: "Mode of Payment", label: __("Paid By"), reqd: 1, default: "Cash" },
					],
					primary_action_label: __("Record Deposit"),
					primary_action(values) {
						frappe.call({
							method: "revelry_workshop.revelry_workshop.deposits.take_deposit",
							args: { job: frm.doc.name, ...values },
							freeze: true,
							callback(r) {
								d.hide();
								frappe.show_alert({ message: __("Deposit {0} recorded", [r.message]), indicator: "green" });
								frm.reload_doc();
							},
						});
					},
				});
				d.show();
			});
		}
		if (frm.doc.sales_invoice) {
			frm.add_custom_button(__("Open Invoice"), () =>
				frappe.set_route("Form", "Sales Invoice", frm.doc.sales_invoice)
			);
		}
	},
	template(frm) {
		if (!frm.doc.template) return;
		frappe.call({
			method: "revelry_workshop.revelry_workshop.doctype.workshop_job.workshop_job.get_template",
			args: { template: frm.doc.template },
			callback(r) {
				const t = r.message;
				if (!t) return;
				[
					"description", "details", "job_type", "skill_level", "estimated_hours", "labour_rate",
					"pricing", "tax_inclusive", "show_hours", "show_description", "show_details",
				].forEach((f) => frm.set_value(f, t[f]));
				["checklist", "parts", "labour"].forEach((table) => {
					frm.clear_table(table);
					(t[table] || []).forEach((row) => {
						const child = frm.add_child(table);
						Object.assign(child, row);
					});
					frm.refresh_field(table);
				});
			},
		});
	},
	motorcycle(frm) {
		if (!frm.doc.motorcycle || frm.doc.customer) return;
		frappe.db.get_value("Motorcycle", frm.doc.motorcycle, "customer").then((r) => {
			if (r.message && r.message.customer) frm.set_value("customer", r.message.customer);
		});
	},
});

frappe.ui.form.on("Workshop Job Labour", {
	labour_add(frm, cdt, cdn) {
		frappe.model.set_value(cdt, cdn, "rate", frm.doc.labour_rate);
	},
});
