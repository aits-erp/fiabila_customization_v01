# fiabila_customization/overrides/stock_entry.py

import frappe
from erpnext.stock.doctype.stock_entry.stock_entry import StockEntry as ERPNextStockEntry


class CustomStockEntry(ERPNextStockEntry):

    def validate(self):
        super().validate()
        self.map_warehouses_from_work_order_with_fallback()

    def map_warehouses_from_work_order_with_fallback(self):
        if not self.work_order:
            return

        wo = frappe.get_doc("Work Order", self.work_order)

        source_wh = wo.source_warehouse
        wip_wh = wo.wip_warehouse
        fg_wh = wo.fg_warehouse

        if self.purpose == "Material Transfer for Manufacture":
            self.from_warehouse = source_wh
            self.to_warehouse = wip_wh
            for item in self.items:
                item.s_warehouse = source_wh
                item.t_warehouse = wip_wh

        elif self.purpose == "Material Consumption for Manufacture":
            self.from_warehouse = wip_wh
            for item in self.items:
                item.s_warehouse = wip_wh

        elif self.purpose == "Manufacture":
            self.from_warehouse = wip_wh
            self.to_warehouse = fg_wh
            for item in self.items:
                if item.is_finished_item:
                    item.t_warehouse = fg_wh
                else:
                    item.s_warehouse = wip_wh

        elif self.purpose == "Material Receipt":
            self.to_warehouse = fg_wh
            for item in self.items:
                item.t_warehouse = fg_wh

# import frappe
# from erpnext.stock.doctype.stock_entry.stock_entry import StockEntry as ERPNextStockEntry


# class CustomStockEntry(ERPNextStockEntry):

#     def validate(self):
#         super().validate()
#         self.map_warehouses_from_work_order_with_fallback()

#     def map_warehouses_from_work_order_with_fallback(self):

#         if not self.work_order:
#             return

#         wo = frappe.get_doc("Work Order", self.work_order)

#         source_wh = wo.source_warehouse
#         wip_wh = wo.wip_warehouse
#         fg_wh = wo.fg_warehouse

#         # -------------------------------
#         # Material Transfer
#         # -------------------------------
#         if self.purpose == "Material Transfer for Manufacture":
#             self.from_warehouse = source_wh
#             self.to_warehouse = wip_wh

#         # -------------------------------
#         # Material Consumption
#         # -------------------------------
#         elif self.purpose == "Material Consumption for Manufacture":
#             self.from_warehouse = wip_wh

#         # -------------------------------
#         # Manufacture
#         # -------------------------------
#         elif self.purpose == "Manufacture":
#             self.from_warehouse = wip_wh
#             self.to_warehouse = fg_wh

#         # -------------------------------
#         # Material Receipt
#         # -------------------------------
#         elif self.purpose == "Material Receipt":
#             self.to_warehouse = fg_wh