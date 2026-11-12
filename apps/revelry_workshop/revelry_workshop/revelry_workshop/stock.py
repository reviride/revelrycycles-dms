# Copyright (c) 2026, Revelry Cycles
# License: GPLv3
"""Parts come off the shelf when they're fitted: a Material Transfer moves them to the Workshop WIP
warehouse, so stock on hand (and the WooCommerce stock level) drops straight away. The invoice then
sells them from WIP. Un-fitting a part, or cancelling the job, moves it back."""

import frappe
from frappe import _
from frappe.utils import now_datetime

MOVABLE_SOURCES = ("Stock", "Special Order")


def _transfer(job, row, from_wh, to_wh, remark):
	se = frappe.new_doc("Stock Entry")
	se.stock_entry_type = "Material Transfer"
	se.purpose = "Material Transfer"
	se.company = frappe.db.get_value("Warehouse", to_wh, "company")
	se.remarks = f"{remark} {job.name}: {row.item_name or row.item_code}"
	se.append(
		"items",
		{"item_code": row.item_code, "qty": row.qty, "s_warehouse": from_wh, "t_warehouse": to_wh},
	)
	se.insert(ignore_permissions=True)
	se.submit()
	return se.name


def sync_fitted_parts(job):
	s = frappe.get_cached_doc("Workshop Settings")
	if not (s.shop_warehouse and s.wip_warehouse):
		return
	cancelled = job.status == "Cancelled"
	for row in job.parts:
		if not row.item_code or row.source not in MOVABLE_SOURCES:
			continue
		if not frappe.db.get_value("Item", row.item_code, "is_stock_item"):
			continue
		fitted = row.part_status == "Fitted" and not cancelled
		if fitted and not row.stock_entry:
			name = _transfer(job, row, s.shop_warehouse, s.wip_warehouse, _("Fitted on job"))
			row.db_set({"stock_entry": name, "fitted_on": now_datetime()})
		elif not fitted and row.stock_entry and not job.sales_invoice:
			_transfer(job, row, s.wip_warehouse, s.shop_warehouse, _("Returned from job"))
			row.db_set({"stock_entry": None, "fitted_on": None})
			if cancelled and row.part_status == "Fitted":
				row.db_set("part_status", "Returned")
