# Copyright (c) 2026, Revelry Cycles
# License: GPLv3
"""Turn approved workshop jobs into one ERPNext Sales Invoice, like EvoPOS 'recall jobs'."""

import frappe
from frappe import _
from frappe.utils import flt


def _settings():
	s = frappe.get_cached_doc("Workshop Settings")
	if not s.labour_item:
		frappe.throw(_("Set the Labour Item in Workshop Settings first."))
	return s


@frappe.whitelist()
def make_sales_invoice(job):
	first = frappe.get_doc("Workshop Job", job)
	first.check_permission("write")
	if first.status != "Approved":
		frappe.throw(_("Only Approved jobs can be invoiced."))
	if not first.customer:
		frappe.throw(_("Set the customer on the job first."))
	s = _settings()

	# every approved, uninvoiced job for this customer and bike goes on the same invoice
	filters = {"status": "Approved", "customer": first.customer, "sales_invoice": ["is", "not set"]}
	if first.motorcycle:
		filters["motorcycle"] = first.motorcycle
	names = frappe.get_all("Workshop Job", filters=filters, pluck="name", order_by="creation asc")
	jobs = [frappe.get_doc("Workshop Job", n) for n in names]

	si = frappe.new_doc("Sales Invoice")
	si.customer = first.customer
	si.company = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value(
		"Global Defaults", "default_company"
	)
	update_stock = False
	for jb in jobs:
		heading = jb.description if jb.show_description else _("Workshop job")
		bike = f" - {jb.bike}" if jb.bike else ""
		for row in jb.labour:
			desc = row.description or heading
			if jb.show_details and jb.work_done:
				desc += "\n" + jb.work_done
			si.append(
				"items",
				{
					"item_code": s.labour_item,
					"item_name": f"{heading}{bike}"[:140],
					"description": f"{desc}\n{_('Job')} {jb.name}",
					"qty": flt(row.hours) if jb.show_hours else 1,
					"rate": flt(row.amount) / flt(row.hours) if jb.show_hours and flt(row.hours) else flt(row.amount),
					"uom": frappe.db.get_value("Item", s.labour_item, "stock_uom"),
				},
			)
		if not jb.labour and jb.pricing != "Hourly" and flt(jb.labour_total):
			si.append(
				"items",
				{
					"item_code": s.labour_item,
					"item_name": f"{heading}{bike}"[:140],
					"description": f"{heading}\n{_('Job')} {jb.name}",
					"qty": 1,
					"rate": flt(jb.labour_total),
				},
			)
		if jb.pricing == "Fixed Price Including Parts":
			continue
		for p in jb.parts:
			if p.source == "Customer Supplied" or not p.item_code:
				continue
			is_stock = frappe.db.get_value("Item", p.item_code, "is_stock_item")
			row = {
				"item_code": p.item_code,
				"item_name": p.item_name,
				"qty": p.qty,
				"rate": p.rate,
				"description": f"{p.item_name}\n{_('Job')} {jb.name}",
			}
			if is_stock:
				update_stock = True
				row["warehouse"] = s.wip_warehouse if p.stock_entry and s.wip_warehouse else s.shop_warehouse
			si.append("items", row)
	if not si.items:
		frappe.throw(_("Nothing to invoice on these jobs."))
	si.update_stock = 1 if update_stock else 0
	si.set_missing_values()
	if s.sales_taxes_template:
		si.taxes_and_charges = s.sales_taxes_template
		si.set("taxes", [])
		si.set_taxes()
	if not si.get("taxes"):
		from erpnext.controllers.accounts_controller import get_default_taxes_and_charges

		default = get_default_taxes_and_charges("Sales Taxes and Charges Template", company=si.company)
		if default.get("taxes_and_charges"):
			si.taxes_and_charges = default["taxes_and_charges"]
			si.set_taxes()
	if not si.get("taxes"):
		frappe.throw(_("No default sales tax (GST) template found for {0}.").format(si.company))
	# workshop prices are entered including GST
	for tax in si.get("taxes") or []:
		if tax.charge_type == "On Net Total":
			tax.included_in_print_rate = 1
	si.calculate_taxes_and_totals()
	si.insert()
	for jb in jobs:
		frappe.db.set_value("Workshop Job", jb.name, "sales_invoice", si.name)
	return si.name


def on_sales_invoice_submit(doc, method=None):
	for name in frappe.get_all("Workshop Job", {"sales_invoice": doc.name}, pluck="name"):
		frappe.db.set_value("Workshop Job", name, "status", "Invoiced")


def on_sales_invoice_cancel(doc, method=None):
	for name in frappe.get_all("Workshop Job", {"sales_invoice": doc.name}, pluck="name"):
		frappe.db.set_value("Workshop Job", name, {"status": "Approved", "sales_invoice": None})
