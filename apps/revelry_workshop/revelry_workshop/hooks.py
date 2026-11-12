app_name = "revelry_workshop"
app_title = "Revelry Workshop"
app_publisher = "Revelry Cycles"
app_description = "Motorcycle workshop module for ERPNext"
app_email = "sales@revelrycycles.com.au"
app_license = "gpl-3.0"
required_apps = ["erpnext"]

doc_events = {
	"Sales Invoice": {
		"on_submit": "revelry_workshop.revelry_workshop.invoicing.on_sales_invoice_submit",
		"on_cancel": "revelry_workshop.revelry_workshop.invoicing.on_sales_invoice_cancel",
	},
	"Material Request": {"on_cancel": "revelry_workshop.revelry_workshop.parts.on_material_request_cancel"},
	"Purchase Order": {
		"on_submit": "revelry_workshop.revelry_workshop.parts.on_purchase_order_submit",
		"on_cancel": "revelry_workshop.revelry_workshop.parts.on_purchase_order_cancel",
	},
	"Purchase Receipt": {
		"on_submit": "revelry_workshop.revelry_workshop.parts.on_purchase_receipt_submit",
		"on_cancel": "revelry_workshop.revelry_workshop.parts.on_purchase_receipt_cancel",
	},
}
after_install = "revelry_workshop.install.after_install"

jinja = {"methods": ["revelry_workshop.revelry_workshop.printing.job_qr"]}
