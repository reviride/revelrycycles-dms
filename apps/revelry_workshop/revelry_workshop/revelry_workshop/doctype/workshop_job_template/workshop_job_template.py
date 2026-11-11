# Copyright (c) 2026, Revelry Cycles
# License: GPLv3

from frappe.model.document import Document


class WorkshopJobTemplate(Document):
	def validate(self):
		# EvoPOS rule: a template whose code starts with WARRANTY makes warranty jobs
		if (self.template_code or "").upper().startswith("WARRANTY"):
			self.job_type = "Warranty"
