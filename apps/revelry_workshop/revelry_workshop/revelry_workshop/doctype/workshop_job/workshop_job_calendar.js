frappe.views.calendar["Workshop Job"] = {
	field_map: {
		start: "scheduled_start",
		end: "scheduled_end",
		id: "name",
		title: "description",
		allDay: "all_day",
	},
	gantt: true,
	filters: [
		{ fieldtype: "Link", fieldname: "technician", options: "User", label: __("Technician") },
		{ fieldtype: "Select", fieldname: "status", options: "\nBooked\nAvailable\nIn Progress\nHold\nCompleted\nApproved", label: __("Status") },
	],
	get_events_method: "frappe.desk.calendar.get_events",
};
