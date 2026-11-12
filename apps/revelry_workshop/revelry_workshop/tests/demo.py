"""Demo records for a throwaway site (screenshots): bench --site test.local execute revelry_workshop.tests.demo.run"""
import frappe
from frappe.utils import add_to_date, now_datetime


def run():
	frappe.set_user("Administrator")
	cust = frappe.db.get_value("Customer", {"customer_name": "Demo Rider"}) or frappe.get_doc(
		{"doctype": "Customer", "customer_name": "Demo Rider", "customer_type": "Individual"}).insert().name
	bike = frappe.db.get_value("Motorcycle", {"vin": "ME3CNEGT6NK00DEMO"}) or frappe.get_doc(
		{"doctype": "Motorcycle", "vin": "ME3CNEGT6NK00DEMO", "make": "Royal Enfield", "model": "Interceptor 650",
		 "year": 2023, "rego": "DEMO1", "customer": cust}).insert().name
	if not frappe.db.exists("Workshop Job Template", "RE 650 FULL SERVICE"):
		frappe.get_doc({"doctype": "Workshop Job Template", "template_code": "RE 650 FULL SERVICE",
			"description": "RE 650 FULL SERVICE (.5,10,20)", "estimated_hours": 2.6, "labour_rate": 140,
			"checklist": [{"item_text": t, "code": c} for t, c in [("ENGINE OIL (LEVEL CHECK / REPLACE)", "R"),
				("ENGINE OIL FILTER ELEMENT", "R"), ("SPARK PLUG", "C&A"), ("BRAKE PADS FRONT AND REAR", "I")]]}).insert()
	from revelry_workshop.revelry_workshop.doctype.workshop_job.workshop_job import get_template
	t = get_template("RE 650 FULL SERVICE")
	names = []
	for i, (desc, status) in enumerate([("RE 650 FULL SERVICE (.5,10,20)", "In Progress"), ("REPLACE CHAIN AND REAR DISC", "Booked"),
			("REPAIR ACCIDENT DAMAGE", "Hold"), ("PDI - 650", "Completed"), ("LOG BOOK SERVICE", "Approved")]):
		j = frappe.get_doc({"doctype": "Workshop Job", "motorcycle": bike, "description": desc, "status": status,
			"technician": "Administrator", "labour_rate": 140, "odometer_in": 15980,
			"details": "- ADDITIONAL ITEMS / CUSTOMER CONCERNS:\n- Check rear brake squeal",
			"checklist": t["checklist"] if i == 0 else [], "labour": t["labour"],
			"bookings": [{"technician": "Administrator", "start": add_to_date(now_datetime(), hours=i * 2), "minutes": 90}]}).insert()
		names.append(j.name)
	frappe.db.commit()
	html = frappe.get_print("Workshop Job", names[0], "Workshop Job Card")
	open("/tmp/jobcard.html", "w").write(html)
	print(names)
