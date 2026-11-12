"""Smoke test on a throwaway site:  bench --site test.local execute revelry_workshop.tests.smoke.run
Never run this on the live site: it runs the setup wizard and creates test records."""

import frappe
from frappe.utils import now_datetime


def _setup_company():
	if frappe.db.get_single_value("System Settings", "setup_complete"):
		return
	from frappe.desk.page.setup_wizard.setup_wizard import setup_complete

	setup_complete(
		{
			"language": "English", "country": "Australia", "timezone": "Australia/Sydney", "currency": "AUD",
			"full_name": "Test User", "email": "test@example.com", "password": "test-only-1234",
			"company_name": "Test Motorcycles", "company_abbr": "TM", "chart_of_accounts": "Australia - Chart of Accounts with Account Numbers",
			"fy_start_date": "2026-07-01", "fy_end_date": "2027-06-30", "setup_demo": 0,
		}
	)


def run():
	frappe.set_user("Administrator")
	_setup_company()
	from revelry_workshop.install import after_install

	after_install()
	assert frappe.db.exists("Role", "Workshop Manager")
	company = frappe.db.get_value("Company", {}, "name")
	abbr = frappe.db.get_value("Company", company, "abbr")
	frappe.defaults.set_user_default("Company", company)

	if not frappe.db.exists("Item", "OILFILTER"):
		frappe.get_doc({"doctype": "Item", "item_code": "OILFILTER", "item_name": "Oil filter",
			"item_group": "Products", "stock_uom": "Nos", "is_stock_item": 1, "valuation_rate": 10}).insert()
	rec = frappe.get_doc({"doctype": "Stock Entry", "stock_entry_type": "Material Receipt", "company": company,
		"items": [{"item_code": "OILFILTER", "qty": 5, "t_warehouse": f"Stores - {abbr}", "basic_rate": 10}]})
	rec.insert(); rec.submit()
	s = frappe.get_doc("Workshop Settings")
	assert s.labour_item == "LABOUR" and s.wip_warehouse == f"Work In Progress - {abbr}", s.as_dict()
	assert s.sales_taxes_template == f"AU Sales - GST - {abbr}", s.sales_taxes_template

	cust = frappe.db.get_value("Customer", {"customer_name": "Smoke Rider"}) or frappe.get_doc(
		{"doctype": "Customer", "customer_name": "Smoke Rider", "customer_type": "Individual"}
	).insert().name

	bike = frappe.get_doc({"doctype": "Motorcycle", "vin": "me3cnegt6nk00SMK1", "make": "Royal Enfield",
		"model": "Continental GT 650", "year": 2022, "rego": "abc12", "customer": cust}).insert()
	assert bike.vin == "ME3CNEGT6NK00SMK1" and bike.title == "2022 Royal Enfield Continental GT 650 (ABC12)", bike.title

	tpl_code = "SMOKE FULL SERVICE"
	if not frappe.db.exists("Workshop Job Template", tpl_code):
		frappe.get_doc({"doctype": "Workshop Job Template", "template_code": tpl_code,
			"description": "RE 650 FULL SERVICE (.5,10,20)", "estimated_hours": 2.6, "labour_rate": 140,
			"checklist": [{"item_text": "ENGINE OIL (LEVEL CHECK / REPLACE)", "code": "R"}, {"item_text": "SPARK PLUG", "code": "C&A"}],
			"parts": [{"item_code": "OILFILTER", "qty": 1}]}).insert()
	w = frappe.get_doc({"doctype": "Workshop Job Template", "template_code": "WARRANTY RECALL X", "description": "Recall"})
	w.insert()
	assert w.job_type == "Warranty"

	from revelry_workshop.revelry_workshop.doctype.workshop_job.workshop_job import get_template

	t = get_template(tpl_code)
	job = frappe.get_doc({"doctype": "Workshop Job", "motorcycle": bike.name, "template": tpl_code,
		"description": t["description"], "labour_rate": 140, "status": "Booked",
		"checklist": t["checklist"], "labour": t["labour"],
		"parts": [dict(p, rate=25) for p in t["parts"]],
		"bookings": [{"technician": "Administrator", "start": now_datetime(), "minutes": 90}]})
	job.insert()
	assert job.customer == cust, "customer from bike"
	assert abs(job.labour_total - 364) < 0.01 and abs(job.grand_total - 389) < 0.01, (job.labour_total, job.grand_total)
	assert job.scheduled_start and job.bookings[0].end

	job.odometer_in = 15980
	job.status = "In Progress"
	job.checklist[0].result = "Done"
	job.save()
	assert job.checklist[0].completed_by == "Administrator"
	assert frappe.db.get_value("Motorcycle", bike.name, "odometer") == 15980

	# fitting the part moves it to WIP
	job.parts[0].part_status = "Fitted"
	job.save()
	job.reload()
	assert job.parts[0].stock_entry, "fitted part should have a stock entry"
	from erpnext.stock.utils import get_stock_balance
	assert get_stock_balance("OILFILTER", f"Work In Progress - {abbr}") == 1
	assert get_stock_balance("OILFILTER", f"Stores - {abbr}") == 4

	from revelry_workshop.revelry_workshop.deposits import take_deposit
	pe = take_deposit(job.name, 100, "Cash")
	job.reload()
	assert job.deposit_total == 100, job.deposit_total

	job.status = "Completed"; job.odometer_out = 15985; job.save()
	job.status = "Approved"; job.save()

	from revelry_workshop.revelry_workshop.invoicing import make_sales_invoice

	si_name = make_sales_invoice(job.name)
	si = frappe.get_doc("Sales Invoice", si_name)
	print("invoice", si.name, "grand_total", si.grand_total, "tax", si.total_taxes_and_charges)
	assert abs(si.grand_total - 389) < 0.01, si.grand_total
	assert abs(si.total_taxes_and_charges - 35.36) < 0.02, si.total_taxes_and_charges
	assert abs(si.outstanding_amount - 289) < 0.01, ("deposit applied", si.outstanding_amount, [a.allocated_amount for a in si.advances])
	si.submit()
	assert frappe.db.get_value("Workshop Job", job.name, "status") == "Invoiced"
	assert str(frappe.db.get_value("Workshop Job", job.name, "invoiced_on")) == str(si.posting_date)
	from frappe.desk.doctype.dashboard_chart.dashboard_chart import get as chart_get
	data = chart_get(chart_name="Workshop Revenue", refresh=1)
	assert abs(sum(data["datasets"][0]["values"]) - 389) < 0.01, data
	assert get_stock_balance("OILFILTER", f"Work In Progress - {abbr}") == 0, "invoice sells from WIP"
	si.cancel()
	assert frappe.db.get_value("Workshop Job", job.name, "status") == "Approved"
	# cancelling a job puts fitted parts back on the shelf
	job2 = frappe.get_doc({"doctype": "Workshop Job", "motorcycle": bike.name, "description": "Cancel test",
		"parts": [{"item_code": "OILFILTER", "qty": 1, "rate": 25, "part_status": "Fitted"}]}).insert()
	assert job2.status == "In Progress"
	assert get_stock_balance("OILFILTER", f"Stores - {abbr}") == 3
	job2.status = "Cancelled"; job2.save(); job2.reload()
	assert get_stock_balance("OILFILTER", f"Stores - {abbr}") == 4 and job2.parts[0].part_status == "Returned"

	# Request Parts: short stock + special order go on a Material Request, then follow the PO and receipt
	if not frappe.db.exists("Item", "BRAKEPADS"):
		frappe.get_doc({"doctype": "Item", "item_code": "BRAKEPADS", "item_name": "Brake pads",
			"item_group": "Products", "stock_uom": "Nos", "is_stock_item": 1, "valuation_rate": 30}).insert()
	job3 = frappe.get_doc({"doctype": "Workshop Job", "motorcycle": bike.name, "description": "Parts test",
		"parts": [{"item_code": "OILFILTER", "qty": 1, "rate": 25},
			{"item_code": "OILFILTER", "qty": 10, "rate": 25},
			{"item_code": "BRAKEPADS", "qty": 1, "rate": 60, "source": "Special Order"}]}).insert()
	from revelry_workshop.revelry_workshop.parts import request_parts
	mr = request_parts(job3.name)
	job3.reload()
	assert [r.part_status for r in job3.parts] == ["Booked", "Requested", "Requested"], [r.part_status for r in job3.parts]
	assert job3.parts_status == "Requested"
	assert request_parts(job3.name) is None, "second request is a no-op"
	from erpnext.stock.doctype.material_request.material_request import make_purchase_order
	if not frappe.db.exists("Supplier", "Smoke Supplier"):
		frappe.get_doc({"doctype": "Supplier", "supplier_name": "Smoke Supplier"}).insert()
	po = make_purchase_order(mr)
	po.supplier = "Smoke Supplier"
	for i in po.items:
		i.rate = 10
	po.insert(); po.submit()
	job3.reload()
	assert [r.part_status for r in job3.parts][1:] == ["On Order", "On Order"] and job3.parts[2].eta and job3.parts_status == "On Order"
	from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt
	pr = make_purchase_receipt(po.name)
	pr.insert(); pr.submit()
	job3.reload()
	assert [r.part_status for r in job3.parts][1:] == ["Arrived", "Arrived"] and job3.parts_status == "OK", job3.parts_status
	pr.cancel(); job3.reload()
	assert job3.parts[2].part_status == "On Order"
	frappe.db.rollback()
	print("SMOKE OK")
