app_name = "fiabila_customization"
app_title = "Fiabila Customization"
app_publisher = "dhanvant marathe"
app_description = "Fiabila Customization"
app_email = "marathedhanvant9@gmail.com"
app_license = "mit"

app_include_js = []

doctype_js = {
    "Work Order": "public/js/work_order.js"
}

override_whitelisted_methods = {
    "erpnext.stock.doctype.pick_list.pick_list.get_available_item_locations":
        "fiabila_customization.overrides.pick_list.get_available_item_locations"
}

override_doctype_class = {
    "Work Order": "fiabila_customization.overrides.work_order.CustomWorkOrder",
    "Stock Entry": "fiabila_customization.overrides.stock_entry.CustomStockEntry"
}
