# Copyright (c) 2026, Revelry Cycles
# License: GPLv3

import frappe
from frappe.model.document import Document
from frappe.utils import cint


class Motorcycle(Document):
	def validate(self):
		if self.vin:
			self.vin = self.vin.strip().upper()
		if self.rego:
			self.rego = self.rego.strip().upper()
		parts = [str(self.year) if self.year else "", self.make or "", self.model or ""]
		label = " ".join(p for p in parts if p).strip() or "Motorcycle"
		ident = self.rego or (self.vin[-6:] if self.vin else "")
		self.title = f"{label} ({ident})" if ident else label

	def add_odometer_reading(self, reading, job=None, reading_date=None):
		reading = cint(reading)
		if not reading:
			return
		self.append(
			"odometer_history",
			{"reading_date": reading_date or frappe.utils.today(), "odometer": reading, "workshop_job": job},
		)
		if reading > cint(self.odometer):
			self.odometer = reading
