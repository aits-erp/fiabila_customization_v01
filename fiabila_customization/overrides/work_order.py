import frappe
from erpnext.manufacturing.doctype.work_order.work_order import WorkOrder as ERPNextWorkOrder


class CustomWorkOrder(ERPNextWorkOrder):

    def validate(self):
        super().validate()
        self.map_warehouses_from_bom_with_fallback()

    def map_warehouses_from_bom_with_fallback(self):
        if not self.bom_no:
            return

        bom = frappe.get_doc("BOM", self.bom_no)

        # ---- SOURCE WAREHOUSE ----
        self.source_warehouse = (
            bom.custom_source_warehouse
            or self.source_warehouse
            or self.get_item_default_warehouse()
        )

        # ---- WIP WAREHOUSE ----
        self.wip_warehouse = (
            bom.custom_workinprogress_warehouse
            or self.wip_warehouse
            or self.get_company_default_wip()
        )

        # ---- FG / TARGET WAREHOUSE ----
        self.fg_warehouse = (
            bom.custom_target_warehouse
            or self.fg_warehouse
            or self.get_item_default_warehouse()
        )

    # -----------------------------------
    # FALLBACK HELPERS
    # -----------------------------------

    def get_item_default_warehouse(self):
        item_defaults = frappe.db.get_value(
            "Item Default",
            {"parent": self.production_item, "company": self.company},
            "default_warehouse",
        )
        return item_defaults

    def get_company_default_wip(self):
        return frappe.db.get_value(
            "Company",
            self.company,
            "default_wip_warehouse"
        )