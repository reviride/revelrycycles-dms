frappe.listview_settings["Workshop Job"] = {
	add_fields: ["status", "priority"],
	get_indicator(doc) {
		const colours = {
			Booked: "gray", Available: "blue", "In Progress": "green", Hold: "orange",
			Completed: "cyan", Approved: "purple", Invoiced: "darkgrey", Cancelled: "red",
		};
		return [__(doc.status), colours[doc.status] || "gray", "status,=," + doc.status];
	},
};
