import frappe


def after_install():
	if not frappe.db.exists("Role", "Workshop Manager"):
		frappe.get_doc({"doctype": "Role", "role_name": "Workshop Manager", "desk_access": 1}).insert(
			ignore_permissions=True
		)
	set_default_settings()
	setup_views()


def set_default_settings():
	"""Fill Workshop Settings with sensible defaults for the first company, if they're empty."""
	company = frappe.db.get_single_value("Global Defaults", "default_company") or frappe.db.get_value(
		"Company", {}, "name"
	)
	if not company:
		return  # setup wizard not finished yet; settings can be filled in later
	abbr = frappe.db.get_value("Company", company, "abbr")
	s = frappe.get_doc("Workshop Settings")

	if not s.labour_item:
		if not frappe.db.exists("Item", "LABOUR"):
			group = "Services" if frappe.db.exists("Item Group", "Services") else frappe.db.get_value(
				"Item Group", {"is_group": 0}, "name"
			)
			uom = "Hour" if frappe.db.exists("UOM", "Hour") else "Nos"
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": "LABOUR",
					"item_name": "Workshop labour",
					"item_group": group,
					"stock_uom": uom,
					"is_stock_item": 0,
					"include_item_in_manufacturing": 0,
				}
			).insert(ignore_permissions=True)
		s.labour_item = "LABOUR"
	for field, name in (("shop_warehouse", "Stores"), ("wip_warehouse", "Work In Progress")):
		if not s.get(field) and frappe.db.exists("Warehouse", f"{name} - {abbr}"):
			s.set(field, f"{name} - {abbr}")
	if not s.sales_taxes_template and frappe.db.exists("Sales Taxes and Charges Template", f"AU Sales - GST - {abbr}"):
		s.sales_taxes_template = f"AU Sales - GST - {abbr}"
	s.flags.ignore_permissions = True
	s.save()


BOARD_COLUMNS = [
	("Booked", "Gray"), ("Available", "Blue"), ("In Progress", "Green"), ("Hold", "Orange"),
	("Completed", "Cyan"), ("Approved", "Purple"),
]


def setup_views():
	"""Job board, printed job card and Workshop workspace. Safe to run again."""
	import os

	if not frappe.db.exists("Kanban Board", "Workshop Board"):
		frappe.get_doc(
			{
				"doctype": "Kanban Board",
				"kanban_board_name": "Workshop Board",
				"reference_doctype": "Workshop Job",
				"field_name": "status",
				"private": 0,
				"show_labels": 1,
				"fields": '["customer_name", "bike", "technician", "parts_status", "priority", "scheduled_start"]',
				"columns": [{"column_name": c, "status": "Active", "indicator": i} for c, i in BOARD_COLUMNS],
				"filters": '[["Workshop Job", "status", "not in", ["Invoiced", "Cancelled"]]]',
			}
		).insert(ignore_permissions=True)

	html = open(os.path.join(os.path.dirname(__file__), "setup_assets", "job_card.html")).read()
	if frappe.db.exists("Print Format", "Workshop Job Card"):
		frappe.db.set_value("Print Format", "Workshop Job Card", "html", html)
	else:
		frappe.get_doc(
			{
				"doctype": "Print Format",
				"name": "Workshop Job Card",
				"doc_type": "Workshop Job",
				"module": "Revelry Workshop",
				"standard": "No",
				"custom_format": 1,
				"print_format_type": "Jinja",
				"html": html,
				"disabled": 0,
			}
		).insert(ignore_permissions=True)
	frappe.make_property_setter(
		{"doctype": "Workshop Job", "doctype_or_field": "DocType", "property": "default_print_format",
		 "value": "Workshop Job Card", "property_type": "Data"},
		validate_fields_for_doctype=False,
	)

	cards = [
		("Workshop: In Progress", [["Workshop Job", "status", "=", "In Progress"]]),
		("Workshop: Waiting on Parts", [["Workshop Job", "parts_status", "in", ["Requested", "To Order", "On Order"]],
										["Workshop Job", "status", "not in", ["Invoiced", "Cancelled"]]]),
		("Workshop: Awaiting Approval", [["Workshop Job", "status", "=", "Completed"]]),
		("Workshop: Ready to Invoice", [["Workshop Job", "status", "=", "Approved"]]),
	]
	import json

	for label, filters in cards:
		if not frappe.db.exists("Number Card", label):
			frappe.get_doc(
				{
					"doctype": "Number Card", "label": label, "name": label, "type": "Document Type",
					"document_type": "Workshop Job", "function": "Count", "is_public": 1,
					"filters_json": json.dumps(filters), "module": "Revelry Workshop", "is_standard": 0,
				}
			).insert(ignore_permissions=True)

	if not frappe.db.exists("Dashboard Chart", "Workshop Revenue"):
		frappe.get_doc(
			{
				"doctype": "Dashboard Chart", "chart_name": "Workshop Revenue", "name": "Workshop Revenue",
				"chart_type": "Sum", "document_type": "Workshop Job", "based_on": "invoiced_on",
				"value_based_on": "grand_total", "timeseries": 1, "time_interval": "Monthly",
				"timespan": "Last Year", "type": "Bar", "is_public": 1, "module": "Revelry Workshop",
				"filters_json": json.dumps([["Workshop Job", "status", "=", "Invoiced"]]), "is_standard": 0,
			}
		).insert(ignore_permissions=True)

	if frappe.db.exists("Workspace", "Workshop"):
		frappe.delete_doc("Workspace", "Workshop", ignore_permissions=True, force=True)
	if True:
		ws = frappe.get_doc(
			{
				"doctype": "Workspace", "name": "Workshop", "label": "Workshop", "title": "Workshop",
				"module": "Revelry Workshop", "public": 1, "icon": "tool", "sequence_id": 1.5,
				"charts": [{"chart_name": "Workshop Revenue", "label": "Workshop Revenue (inc GST)"}],
				"number_cards": [{"number_card_name": l, "label": l.replace("Workshop: ", "")} for l, _ in cards],
				"shortcuts": [
					{"type": "URL", "label": "Job Board", "url": "/app/workshop-job/view/kanban/Workshop Board", "color": "Blue"},
					{"type": "URL", "label": "Calendar", "url": "/app/workshop-job/view/calendar/default", "color": "Green"},
					{"type": "DocType", "link_to": "Workshop Job", "label": "Workshop Jobs", "doc_view": "List"},
					{"type": "DocType", "link_to": "Motorcycle", "label": "Motorcycles", "doc_view": "List"},
					{"type": "DocType", "link_to": "Workshop Job Template", "label": "Job Templates", "doc_view": "List"},
					{"type": "DocType", "link_to": "Workshop Settings", "label": "Workshop Settings"},
				],
			}
		)
		blocks = [{"id": f"h{i}", "type": "number_card", "data": {"number_card_name": l.replace("Workshop: ", ""), "col": 3}} for i, (l, _) in enumerate(cards)]
		blocks.append({"id": "ch", "type": "chart", "data": {"chart_name": "Workshop Revenue (inc GST)", "col": 12}})
		blocks.append({"id": "sp", "type": "spacer", "data": {"col": 12}})
		blocks += [{"id": f"s{i}", "type": "shortcut", "data": {"shortcut_name": sc.label, "col": 3}} for i, sc in enumerate(ws.shortcuts)]
		ws.content = json.dumps(blocks)
		ws.insert(ignore_permissions=True)
