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
	}
}
after_install = "revelry_workshop.install.after_install"
