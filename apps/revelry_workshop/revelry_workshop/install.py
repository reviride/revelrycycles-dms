import frappe


def after_install():
	if not frappe.db.exists("Role", "Workshop Manager"):
		frappe.get_doc({"doctype": "Role", "role_name": "Workshop Manager", "desk_access": 1}).insert(
			ignore_permissions=True
		)
	set_default_settings()


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
