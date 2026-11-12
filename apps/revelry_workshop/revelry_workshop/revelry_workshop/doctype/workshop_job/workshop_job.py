# Copyright (c) 2026, Revelry Cycles
# License: GPLv3

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_to_date, cint, flt, now_datetime

OPEN_STATUSES = ("Booked", "Available", "In Progress", "Hold", "Completed", "Approved")


class WorkshopJob(Document):
	def validate(self):
		self.set_bike_label()
		self.set_booking_ends()
		self.stamp_checklist()
		self.calculate_totals()
		self.validate_status()
		self.set_parts_status()

	def on_update(self):
		self.update_motorcycle()
		from revelry_workshop.revelry_workshop.stock import sync_fitted_parts

		sync_fitted_parts(self)

	# ---------- helpers ----------
	def set_bike_label(self):
		self.bike = frappe.db.get_value("Motorcycle", self.motorcycle, "title") if self.motorcycle else None
		if self.motorcycle and not self.customer:
			self.customer = frappe.db.get_value("Motorcycle", self.motorcycle, "customer")

	def set_booking_ends(self):
		for b in self.bookings:
			if b.start:
				b.end = add_to_date(b.start, minutes=cint(b.minutes) or 60)
		if self.bookings and not self.scheduled_start:
			first = min(self.bookings, key=lambda b: b.start)
			self.scheduled_start = first.start
			self.scheduled_end = first.end
			self.technician = self.technician or first.technician

	def stamp_checklist(self):
		for row in self.checklist:
			if row.result and not row.completed_by:
				row.completed_by = frappe.session.user
				row.completed_on = now_datetime()
			elif not row.result:
				row.completed_by = None
				row.completed_on = None

	def calculate_totals(self):
		labour_total = 0
		for row in self.labour:
			if row.rate is None or row.rate == "":
				row.rate = self.labour_rate
			row.amount = flt(row.hours) * flt(row.rate) * (1 - flt(row.discount_percentage) / 100)
			labour_total += flt(row.amount)
		parts_total = 0
		for row in self.parts:
			row.amount = flt(row.qty) * flt(row.rate)
			if row.source != "Customer Supplied":
				parts_total += flt(row.amount)
		if self.pricing in ("Fixed Price", "Fixed Price Including Parts") and not self.labour:
			labour_total = flt(self.labour_rate)
		if self.pricing == "Fixed Price Including Parts":
			parts_total = 0
		self.labour_total = labour_total
		self.parts_total = parts_total
		self.grand_total = labour_total + parts_total

	def validate_status(self):
		if self.status == "Invoiced" and not self.sales_invoice:
			frappe.throw(_("Use the Invoice button; a job becomes Invoiced when its sales invoice is submitted."))
		if self.status in ("In Progress", "Completed", "Approved") and self.motorcycle and not self.odometer_in:
			frappe.msgprint(_("Odometer in has not been recorded."), indicator="orange", alert=True)
		if self.status == "Completed":
			open_items = [r.item_text for r in self.checklist if not r.result]
			if open_items:
				frappe.msgprint(
					_("{0} checklist items are not ticked off.").format(len(open_items)), indicator="orange", alert=True
				)
		if self.status == "Approved" and self.has_value_changed("status"):
			if not {"System Manager", "Workshop Manager"} & set(frappe.get_roles()):
				frappe.throw(_("Only the workshop manager can approve a job."))

	def set_parts_status(self):
		"""Roll the parts lines up to the job's parts status, as EvoPOS does for customer orders."""
		states = {r.part_status for r in self.parts}
		if "On Order" in states:
			self.parts_status = "On Order"
		elif "Requested" in states:
			self.parts_status = "Requested"
		elif self.parts_status in ("On Order", "Requested"):
			self.parts_status = "OK"
		for r in self.parts:
			if r.part_status == "Fitted" and self.status in ("Booked", "Available"):
				self.status = "In Progress"  # booking parts onto the job starts it, as in EvoPOS
				break

	def update_motorcycle(self):
		if not self.motorcycle:
			return
		bike = frappe.get_doc("Motorcycle", self.motorcycle)
		changed = False
		known = {(r.workshop_job, cint(r.odometer)) for r in bike.odometer_history}
		for reading in (self.odometer_in, self.odometer_out):
			if cint(reading) and (self.name, cint(reading)) not in known:
				bike.add_odometer_reading(reading, job=self.name)
				changed = True
		if self.next_service_date and bike.next_service_date != self.next_service_date:
			bike.next_service_date = self.next_service_date
			changed = True
		if self.next_service_odometer and cint(bike.next_service_odometer) != cint(self.next_service_odometer):
			bike.next_service_odometer = self.next_service_odometer
			changed = True
		if self.job_type == "Internal" and bike.is_stock_bike:
			prep = frappe.db.sql(
				"""select coalesce(sum(grand_total), 0) from `tabWorkshop Job`
				where motorcycle=%s and job_type='Internal' and status in ('Completed','Approved','Invoiced')""",
				self.motorcycle,
			)[0][0]
			if flt(prep) != flt(bike.prep_cost):
				bike.prep_cost = prep
				changed = True
		if changed:
			bike.flags.ignore_permissions = True
			bike.save()


@frappe.whitelist()
def get_template(template):
	"""Values a template puts on a job; the form applies them."""
	t = frappe.get_doc("Workshop Job Template", template)
	t.check_permission("read")
	return {
		"description": t.description,
		"details": t.details,
		"job_type": t.job_type,
		"skill_level": t.skill_level,
		"estimated_hours": t.estimated_hours,
		"labour_rate": t.labour_rate,
		"pricing": t.pricing,
		"tax_inclusive": t.tax_inclusive,
		"show_hours": t.show_hours,
		"show_description": t.show_description,
		"show_details": t.show_details,
		"checklist": [{"item_text": r.item_text, "code": r.code} for r in t.checklist],
		"parts": [
			{
				"item_code": r.item_code,
				"item_name": r.item_name,
				"qty": r.qty,
				"rate": frappe.db.get_value(
					"Item Price", {"item_code": r.item_code, "selling": 1}, "price_list_rate"
				)
				or 0,
			}
			for r in t.parts
		],
		"labour": [
			{
				"description": t.description,
				"estimated_hours": t.estimated_hours,
				"hours": t.estimated_hours if t.pricing == "Hourly" else 1,
				"rate": t.labour_rate,
			}
		],
	}
