import frappe


def after_install():
	if not frappe.db.exists("Role", "Workshop Manager"):
		frappe.get_doc({"doctype": "Role", "role_name": "Workshop Manager", "desk_access": 1}).insert(
			ignore_permissions=True
		)
