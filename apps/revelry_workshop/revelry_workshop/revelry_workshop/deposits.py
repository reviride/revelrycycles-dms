# Copyright (c) 2026, Revelry Cycles
# License: GPLv3
"""Deposits on workshop jobs: a customer advance (Payment Entry) tagged with the job number.
The invoice picks up the customer's unallocated advances automatically."""

import frappe
from frappe import _
from frappe.utils import flt, today


def deposit_total(job_name):
	return flt(
		frappe.db.sql(
			"""select coalesce(sum(paid_amount), 0) from `tabPayment Entry`
			where docstatus=1 and payment_type='Receive' and party_type='Customer' and reference_no=%s""",
			job_name,
		)[0][0]
	)


@frappe.whitelist()
def take_deposit(job, amount, mode_of_payment):
	from erpnext.accounts.doctype.sales_invoice.sales_invoice import get_bank_cash_account
	from erpnext.accounts.party import get_party_account

	doc = frappe.get_doc("Workshop Job", job)
	doc.check_permission("write")
	amount = flt(amount)
	if amount <= 0:
		frappe.throw(_("Enter the deposit amount."))
	if not doc.customer:
		frappe.throw(_("Set the customer on the job first."))
	if doc.status in ("Invoiced", "Cancelled"):
		frappe.throw(_("This job is {0}.").format(doc.status))
	company = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value(
		"Global Defaults", "default_company"
	)
	paid_to = (get_bank_cash_account(mode_of_payment, company) or {}).get("account")
	if not paid_to:
		frappe.throw(_("Set a default account for {0} under Mode of Payment.").format(mode_of_payment))

	pe = frappe.new_doc("Payment Entry")
	pe.payment_type = "Receive"
	pe.company = company
	pe.posting_date = today()
	pe.mode_of_payment = mode_of_payment
	pe.party_type = "Customer"
	pe.party = doc.customer
	pe.paid_from = get_party_account("Customer", doc.customer, company)
	pe.paid_to = paid_to
	pe.paid_amount = amount
	pe.received_amount = amount
	pe.reference_no = doc.name
	pe.reference_date = today()
	pe.remarks = _("Deposit on workshop job {0}: {1}").format(doc.name, doc.description)
	pe.setup_party_account_field()
	pe.set_missing_values()
	pe.insert()
	pe.submit()
	frappe.db.set_value("Workshop Job", doc.name, "deposit_total", deposit_total(doc.name))
	return pe.name
