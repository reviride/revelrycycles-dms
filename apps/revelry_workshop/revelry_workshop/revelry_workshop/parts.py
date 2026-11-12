# Copyright (c) 2026, Revelry Cycles
# License: GPLv3
"""Request Parts, as in EvoPOS: parts a job needs that aren't on the shelf go onto a Material Request
(Purchase) for the buyer. The part lines then follow the paperwork: Requested -> On Order when a
Purchase Order is submitted -> Arrived when the Purchase Receipt is submitted. Cancelling any of those
steps puts the lines back one step."""

import frappe
from frappe import _
from frappe.utils import add_days, flt, nowdate


def _shop_qty(item_code, warehouse):
	return flt(frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": warehouse}, "actual_qty"))


def needs_ordering(row, warehouse):
	if row.part_status != "Booked" or not row.item_code or row.material_request:
		return False
	if row.source == "Special Order":
		return True
	if row.source == "Stock" and frappe.db.get_value("Item", row.item_code, "is_stock_item"):
		return _shop_qty(row.item_code, warehouse) < flt(row.qty)
	return False


@frappe.whitelist()
def request_parts(job):
	job = frappe.get_doc("Workshop Job", job)
	job.check_permission("write")
	if job.status in ("Invoiced", "Cancelled"):
		frappe.throw(_("Job {0} is {1}.").format(job.name, job.status))
	s = frappe.get_cached_doc("Workshop Settings")
	if not s.shop_warehouse:
		frappe.throw(_("Set the Shop Warehouse in Workshop Settings first."))

	rows = [r for r in job.parts if needs_ordering(r, s.shop_warehouse)]
	if not rows:
		frappe.msgprint(_("Nothing to request: every booked part is in stock or already requested."))
		return None

	required_by = job.required_by or add_days(nowdate(), 3)
	if str(required_by) < nowdate():
		required_by = nowdate()
	mr = frappe.new_doc("Material Request")
	mr.material_request_type = "Purchase"
	mr.company = frappe.db.get_value("Warehouse", s.shop_warehouse, "company")
	mr.transaction_date = nowdate()
	mr.schedule_date = required_by
	who = job.customer_name or job.customer or ""
	mr.set("title", f"{job.name} {who}".strip()[:140]) if mr.meta.has_field("title") else None
	for r in rows:
		mr.append(
			"items",
			{
				"item_code": r.item_code,
				"qty": r.qty,
				"schedule_date": required_by,
				"warehouse": s.shop_warehouse,
				"description": f"{r.item_name or r.item_code} for {job.name} {who}".strip(),
			},
		)
	mr.insert()
	mr.submit()

	for r in rows:
		r.part_status = "Requested"
		r.material_request = mr.name
	job.save()
	frappe.msgprint(_("Requested {0} part line(s) on {1}.").format(len(rows), mr.name), indicator="green")
	return mr.name


def _jobs_with(field, value):
	return frappe.get_all("Workshop Job Part", filters={field: value, "parenttype": "Workshop Job"},
		pluck="parent", distinct=True)


def _update_lines(field, value, items, from_status, to_status, extra=None):
	"""Move job part lines linked by `field`=`value` (and an item_code in `items`) between statuses."""
	for name in _jobs_with(field, value):
		job = frappe.get_doc("Workshop Job", name)
		changed = False
		for r in job.parts:
			if r.get(field) == value and r.item_code in items and r.part_status == from_status:
				r.part_status = to_status
				for k, v in (extra or {}).get(r.item_code, {}).items():
					r.set(k, v)
				changed = True
		if changed:
			job.flags.ignore_permissions = True
			job.save()


def on_material_request_cancel(doc, method=None):
	for name in _jobs_with("material_request", doc.name):
		job = frappe.get_doc("Workshop Job", name)
		for r in job.parts:
			if r.material_request == doc.name and r.part_status == "Requested":
				r.part_status = "Booked"
				r.material_request = None
		job.flags.ignore_permissions = True
		job.save()


def on_purchase_order_submit(doc, method=None):
	by_mr = {}
	for i in doc.items:
		if i.material_request:
			by_mr.setdefault(i.material_request, {})[i.item_code] = {
				"purchase_order": doc.name,
				"eta": i.schedule_date or doc.schedule_date,
			}
	for mr, items in by_mr.items():
		_update_lines("material_request", mr, set(items), "Requested", "On Order", items)


def on_purchase_order_cancel(doc, method=None):
	items = {i.item_code for i in doc.items}
	_update_lines("purchase_order", doc.name, items, "On Order", "Requested",
		{c: {"purchase_order": None} for c in items})


def on_purchase_receipt_submit(doc, method=None):
	by_po = {}
	for i in doc.items:
		if i.purchase_order:
			by_po.setdefault(i.purchase_order, set()).add(i.item_code)
	for po, items in by_po.items():
		_update_lines("purchase_order", po, items, "On Order", "Arrived")


def on_purchase_receipt_cancel(doc, method=None):
	by_po = {}
	for i in doc.items:
		if i.purchase_order:
			by_po.setdefault(i.purchase_order, set()).add(i.item_code)
	for po, items in by_po.items():
		_update_lines("purchase_order", po, items, "Arrived", "On Order")
