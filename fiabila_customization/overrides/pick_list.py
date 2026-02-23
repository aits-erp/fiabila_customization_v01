import frappe
from erpnext.stock.doctype.pick_list.pick_list import get_available_item_locations as original_get_locations


BLOCKED_WAREHOUSES = [
    "Work in Progress",
    "Quality Checking"
]


@frappe.whitelist()
def get_available_item_locations(*args, **kwargs):
    """
    Override ERPNext Pick List warehouse allocation
    Removes blocked warehouses and reallocates stock.
    """

    # Call original ERPNext function
    locations = original_get_locations(*args, **kwargs)

    if not locations:
        return locations

    filtered_locations = []

    for row in locations:
        warehouse_name = row.get("warehouse")

        # Skip blocked warehouses
        if warehouse_name in BLOCKED_WAREHOUSES:
            continue

        filtered_locations.append(row)

    if not filtered_locations:
        frappe.throw(
            "Stock is only available in blocked warehouses (Work in Progress / Quality Checking). "
            "Please move stock to valid warehouse."
        )

    return filtered_locations