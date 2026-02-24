# fiabila_customization/overrides/work_order.py

import frappe
from erpnext.manufacturing.doctype.work_order.work_order import WorkOrder as ERPNextWorkOrder


class CustomWorkOrder(ERPNextWorkOrder):

    def before_save(self):
        super().before_save()  # Let ERPNext do everything first
        self.apply_custom_warehouse_mapping()  # Then overwrite with BOM custom fields

    def apply_custom_warehouse_mapping(self):
        if not self.bom_no:
            return

        bom = frappe.get_doc("BOM", self.bom_no)

        source_wh = bom.get("custom_source_warehouse")
        wip_wh = bom.get("custom_workinprogress_warehouse")
        fg_wh = bom.get("custom_target_warehouse")

        # Only override if BOM has custom values
        if source_wh:
            self.source_warehouse = source_wh
        if wip_wh:
            self.wip_warehouse = wip_wh
        if fg_wh:
            self.fg_warehouse = fg_wh

        # Push source_warehouse down to required_items child table
        final_source = self.source_warehouse
        if final_source:
            for row in self.required_items:
                row.source_warehouse = final_source

# import frappe
# from erpnext.manufacturing.doctype.work_order.work_order import WorkOrder as ERPNextWorkOrder


# class CustomWorkOrder(ERPNextWorkOrder):
#     def on_update(self):
#         frappe.logger().error(f"🚨 FINAL source_warehouse: {self.source_warehouse}")

#     def before_save(self):
#         frappe.logger().error("🔥 CustomWorkOrder before_save triggered")
#         super().before_save()
#         self.apply_custom_warehouse_mapping()

#     def set_warehouses(self):
#         super().set_warehouses()

#         if not self.bom_no:
#             return

#         bom = frappe.get_doc("BOM", self.bom_no)

#         if bom.custom_source_warehouse:
#             self.source_warehouse = bom.custom_source_warehouse

#             for row in self.required_items:
#                 row.source_warehouse = bom.custom_source_warehouse

#     def apply_custom_warehouse_mapping(self):
#         frappe.logger().error(f"🔥 BOM: {self.bom_no}")

#         if not self.bom_no:
#             frappe.logger().error("❌ No BOM Found")
#             return

#         bom = frappe.get_doc("BOM", self.bom_no)

#         frappe.logger().error(f"🔥 BOM custom_source_warehouse: {bom.custom_source_warehouse}")

#         # -------------------------------
#         # PARENT FIELD MAPPING
#         # -------------------------------
#         source_wh = (
#             bom.custom_source_warehouse
#             or self.source_warehouse
#             or self.get_item_default_warehouse()
#         )

#         wip_wh = (
#             bom.custom_workinprogress_warehouse
#             or self.wip_warehouse
#             or self.get_company_default_wip()
#         )

#         fg_wh = (
#             bom.custom_target_warehouse
#             or self.fg_warehouse
#             or self.get_item_default_warehouse()
#         )

#         self.source_warehouse = source_wh
#         self.wip_warehouse = wip_wh
#         self.fg_warehouse = fg_wh

#         # -------------------------------
#         # CHILD TABLE MAPPING
#         # required_items
#         # -------------------------------
#         for row in self.required_items:
#             frappe.logger().error(f"Row Before: {row.source_warehouse}")
#             row.source_warehouse = source_wh
#             frappe.logger().error(f"Row After: {row.source_warehouse}")

#     # -----------------------------------
#     # FALLBACK HELPERS
#     # -----------------------------------

#     def get_item_default_warehouse(self):
#         return frappe.db.get_value(
#             "Item Default",
#             {"parent": self.production_item, "company": self.company},
#             "default_warehouse",
#         )

#     def get_company_default_wip(self):
#         return frappe.db.get_value(
#             "Company",
#             self.company,
#             "default_wip_warehouse"
#         )

