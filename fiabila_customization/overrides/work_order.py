# # fiabila_customization/overrides/work_order.py

import frappe
from erpnext.manufacturing.doctype.work_order.work_order import WorkOrder as ERPNextWorkOrder

class CustomWorkOrder(ERPNextWorkOrder):

    # -----------------------------
    # 🔹 CORE OVERRIDE POINTS
    # -----------------------------

    def validate(self):
        super().validate()
        self._enforce_custom_warehouses()

    def before_save(self):
        # CRITICAL: last point before DB write
        self._enforce_custom_warehouses()

    def on_update(self):
        # Ensures values persist after save/update cycles
        self._enforce_custom_warehouses()

    def before_submit(self):
        # Final enforcement before submit
        self._enforce_custom_warehouses()

    # -----------------------------
    # 🔹 MOST IMPORTANT OVERRIDE
    # -----------------------------

    def set_required_items(self, reset_only_qty=False):
        # Let ERPNext rebuild items first
        super().set_required_items(reset_only_qty)

        # Immediately override AFTER rebuild
        self._enforce_custom_warehouses()

    # -----------------------------
    # 🔹 HARD ENFORCEMENT METHOD
    # -----------------------------

    def _enforce_custom_warehouses(self):
        if not self.bom_no:
            return

        bom = frappe.get_cached_doc("BOM", self.bom_no)

        source_wh = bom.get("custom_source_warehouse")
        wip_wh = bom.get("custom_workinprogress_warehouse")
        fg_wh = bom.get("custom_target_warehouse")

        # 🔴 FORCE override at parent level
        if source_wh:
            self.source_warehouse = source_wh

        if wip_wh:
            self.wip_warehouse = wip_wh

        if fg_wh:
            self.fg_warehouse = fg_wh

        # 🔴 FORCE override at child level (NO CONDITIONS)
        if source_wh:
            for row in self.required_items:
                row.source_warehouse = source_wh

    # -----------------------------
    # 🔹 OPTIONAL: BLOCK ERPNext DEFAULT LOGIC
    # -----------------------------

    def validate_materials(self):
        """
        Override ERPNext internal method that may reset warehouses.
        We call super but enforce again.
        """
        super().validate_materials()
        self._enforce_custom_warehouses()


# import frappe
# from erpnext.manufacturing.doctype.work_order.work_order import WorkOrder as ERPNextWorkOrder

# class CustomWorkOrder(ERPNextWorkOrder):

#     def validate(self):
#         # Let ERPNext do all its internal calculations first
#         super().validate()

#         # Apply your custom logic AFTER standard behavior
#         self.apply_custom_warehouse_mapping()

#     def apply_custom_warehouse_mapping(self):
#         if not self.bom_no:
#             return

#         bom = frappe.get_cached_doc("BOM", self.bom_no)

#         source_wh = bom.get("custom_source_warehouse")
#         wip_wh = bom.get("custom_workinprogress_warehouse")
#         fg_wh = bom.get("custom_target_warehouse")

#         # Set only if present in BOM
#         if source_wh:
#             self.source_warehouse = source_wh
#         if wip_wh:
#             self.wip_warehouse = wip_wh
#         if fg_wh:
#             self.fg_warehouse = fg_wh

#         # Apply to child table WITHOUT overriding user edits
#         if self.source_warehouse:
#             for row in self.required_items:
#                 # Only set if empty OR if you want strict control, remove condition
#                 if not row.source_warehouse:
#                     row.source_warehouse = self.source_warehouse



# import frappe
# from erpnext.manufacturing.doctype.work_order.work_order import WorkOrder as ERPNextWorkOrder


# class CustomWorkOrder(ERPNextWorkOrder):

#     def before_save(self):
#         # super().before_save()  # Let ERPNext do everything first Crashes
#         self.apply_custom_warehouse_mapping()  # Then overwrite with BOM custom fields

#     def apply_custom_warehouse_mapping(self):
#         if not self.bom_no:
#             return

#         bom = frappe.get_doc("BOM", self.bom_no)

#         source_wh = bom.get("custom_source_warehouse")
#         wip_wh = bom.get("custom_workinprogress_warehouse")
#         fg_wh = bom.get("custom_target_warehouse")

#         # Only override if BOM has custom values
#         if source_wh:
#             self.source_warehouse = source_wh
#         if wip_wh:
#             self.wip_warehouse = wip_wh
#         if fg_wh:
#             self.fg_warehouse = fg_wh

#         # Push source_warehouse down to required_items child table
#         final_source = self.source_warehouse
#         if final_source:
#             for row in self.required_items:
#                 row.source_warehouse = final_source







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

