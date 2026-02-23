# Copyright (c) 2025, dhanvant marathe and contributors
# For license information, please see license.txt


import frappe
from frappe import _
from pypika import Order
import datetime
import json
from frappe.utils import nowdate

from erpnext.stock.doctype.warehouse.warehouse import get_child_warehouses


def execute(filters=None):
	return ProductionPlanReport(filters).execute_report()


@frappe.whitelist()
def create_material_request_draft(items, item_group_filter=None):
    """
    Create Material Requests grouped by Item Group.
    Skip items already present (same item_code & qty) in existing open Material Requests.
    """

    if isinstance(items, str):
        items = json.loads(items)

    if not items:
        frappe.throw(_("No items provided for Material Request"))

    # Fetch all existing (non-cancelled) Material Request Items
    existing_items = frappe.db.sql("""
        SELECT 
            mri.item_code, 
            mri.qty,
            i.item_group
        FROM `tabMaterial Request Item` mri
        INNER JOIN `tabMaterial Request` mr ON mr.name = mri.parent
        INNER JOIN `tabItem` i ON i.name = mri.item_code
        WHERE mr.docstatus < 2
    """, as_dict=True)

    # Convert to a lookup set for quick skip check
    existing_set = {(d.item_code, float(d.qty)) for d in existing_items}

    # Group new items by item_group
    grouped_items = {}
    for item in items:
        if not (isinstance(item, dict) and item.get("item_code") and item.get("qty") > 0):
            continue

        item_group = item_group_filter or frappe.db.get_value("Item", item["item_code"], "item_group")
        item_key = (item["item_code"], float(item["qty"]))

        # Skip items that already exist with same qty
        if item_key in existing_set:
            # frappe.logger().info(f"Skipping {item['item_code']} (qty: {item['qty']}) — already in existing MR.")
            continue

        grouped_items.setdefault(item_group, []).append(item)

    if not grouped_items:
        return _("All items already exist in existing Material Requests.")

    created_requests = []

    # Create new MR for each item_group
    for item_group, group_items in grouped_items.items():
        mr = frappe.new_doc("Material Request")
        mr.material_request_type = "Manufacture"
        mr.transaction_date = nowdate()
        mr.schedule_date = nowdate()

        for item in group_items:
            mr.append("items", {
                "item_code": item["item_code"],
                "qty": item["qty"],
                "schedule_date": nowdate(),
                "item_group": item_group,
            })

        mr.insert(ignore_permissions=True)
        created_requests.append(mr.name)

    return {
        "message": _("Material Requests created successfully."),
        "created_requests": created_requests
    }

class ProductionPlanReport:
	def __init__(self, filters=None):
		self.filters = frappe._dict(filters or {})
		self.raw_materials_dict = {}
		self.data = []
		

	def execute_report(self):
		# Step 1: Prepare all base data
		self.get_open_orders()
		self.get_raw_materials()
		self.get_item_details()
		self.get_bin_details()
		self.get_purchase_details()
		self.prepare_data()
		self.get_columns()

		# Step 2: Filter data if item_group filter is applied
		if self.filters.item_group:
			self.data = [
				row for row in self.data
				if row.get('item_code')
				and frappe.db.get_value("Item", row.get('item_code'), "item_group") == self.filters.item_group
			]

		# Step 3: Aggregate duplicate raw materials BEFORE zeroing stock
		self.aggregate_duplicate_raw_materials()

	
		seen_fg_raw_material = []
		for row in self.data:
			rm_item = row.get("item_code")
			so_no = row.get("name")
			if not rm_item:
				continue
			
			if rm_item not in seen_fg_raw_material:
				seen_fg_raw_material.append(rm_item)
			else:
				for field in list(row.keys()):
					if field.startswith("stock_"):
						row[field] = 0.0
				row["po_qty"] = 0.0
		

		return self.columns, self.data

	

	def get_open_orders(self):
		doctype, order_by = self.filters.based_on, self.filters.order_by

		parent = frappe.qb.DocType(doctype)
		query = None

		if doctype == "Work Order":
			query = (
				frappe.qb.from_(parent)
				.select(
					parent.production_item,
					parent.item_name.as_("production_item_name"),
					parent.planned_start_date,
					parent.stock_uom,
					parent.qty.as_("qty_to_manufacture"),
					parent.name,
					parent.bom_no,
					parent.fg_warehouse.as_("warehouse"),
				)
				.where(parent.status.notin(["Completed", "Stopped", "Closed"]))
			)

			if order_by == "Planned Start Date":
				query = query.orderby(parent.planned_start_date, order=Order.asc)

			if self.filters.docnames:
				query = query.where(parent.name.isin(self.filters.docnames))

		else:
			child = frappe.qb.DocType(f"{doctype} Item")
		
			query = (
				frappe.qb.from_(parent)
				.from_(child)
				.select(
					child.bom_no,
					child.stock_uom,
					child.warehouse,
					child.parent.as_("name"),
					child.item_code.as_("production_item"),
					child.stock_qty.as_("qty_to_manufacture"),
					child.item_name.as_("production_item_name"),
				)
				.where(parent.name == child.parent)
			)
   
			
			if self.filters.from_doc and self.filters.to_doc:
				query = query.where(child.parent.between(self.filters.from_doc, self.filters.to_doc))
			
			
			if doctype == "Sales Order":
				query = query.select(
					child.delivery_date,
					parent.base_grand_total,
				).where(
					(child.stock_qty > child.produced_qty)
					& (parent.per_delivered < 100.0)
					& (parent.status.notin(["Completed", "Closed"]))
				)

				if order_by == "Delivery Date":
					query = query.orderby(child.delivery_date, order=Order.asc)
				elif order_by == "Total Amount":
					query = query.orderby(parent.base_grand_total, order=Order.desc)

			elif doctype == "Material Request":
				query = query.select(
					child.schedule_date,
				).where(
					(parent.per_ordered < 100)
					& (parent.material_request_type == "Manufacture")
					& (parent.status != "Stopped")
				)

				if order_by == "Required Date":
					query = query.orderby(child.schedule_date, order=Order.asc)

		query = query.where(parent.docstatus == 1)

		if self.filters.company:
			query = query.where(parent.company == self.filters.company)
   
		if doctype == "Sales Order":
			open_orders = query.run(as_dict=True)  
			self.orders = sorted(open_orders, key=lambda x: (x['bom_no'] is None, x['bom_no']))
		else:
			self.orders = query.run(as_dict=True)
   
	def aggregate_duplicate_raw_materials(self):
		"""
		Aggregate required_qty for duplicate raw materials across BOMs.
		Show sum at first occurrence, zero out duplicates below.
		"""
		if not self.data:
			return
		
		# Track: item_code -> {first_index, total_required_qty}
		item_tracker = {}
		
		# First pass: Calculate total required_qty for each item and find first occurrence
		for idx, row in enumerate(self.data):
			item_code = row.get('item_code')
			if not item_code:
				continue
			
			required_qty = row.get('required_qty', 0) or 0
			
			if item_code not in item_tracker:
				# First occurrence - store index and start sum
				item_tracker[item_code] = {
					'first_index': idx,
					'total_required_qty': required_qty
				}
			else:
				# Duplicate - add to sum
				item_tracker[item_code]['total_required_qty'] += required_qty
		
		# Second pass: Update first occurrence with sum, zero out duplicates
		for idx, row in enumerate(self.data):
			item_code = row.get('item_code')
			if not item_code or item_code not in item_tracker:
				continue
			
			tracker = item_tracker[item_code]
			
			if idx == tracker['first_index']:
				# First occurrence - show aggregated sum
				row['required_qty'] = tracker['total_required_qty']
				# Recalculate balance_qty with new required_qty
				row['balance_qty'] = self.calculate_balance_qty(row)
			else:
				# Duplicate - zero out
				row['required_qty'] = 0.0
				row['balance_qty'] = 0.0
				row["item_code"] = " "
				row["raw_material_name"] = " "


    
	def get_raw_materials(self):
		"""Fetch raw materials against Work Orders or BOMs, 
		including sub-assembly children if linked_bom exists.
		Properly calculates required_qty for nested BOMs.
		"""
		if not self.orders:
			return

		self.warehouses = [d.warehouse for d in self.orders if d.warehouse]
		self.item_codes = [d.production_item for d in self.orders if d.production_item]

		if self.filters.based_on == "Work Order":
			work_orders = [d.name for d in self.orders]

			raw_materials = frappe.get_all(
				"Work Order Item",
				fields=[
					"parent",
					"item_code",
					"item_name as raw_material_name",
					"source_warehouse as warehouse",
					"required_qty",
				],
				filters={
					"docstatus": 1,
					"parent": ("in", work_orders),
					"source_warehouse": ("!=", ""),
				},
			) or []
			self.warehouses.extend([d.source_warehouse for d in raw_materials if d.source_warehouse])

		else:
			bom_nos = []
			for d in self.orders:
				bom_no = d.bom_no or frappe.get_cached_value("Item", d.production_item, "default_bom")
				if not d.bom_no:
					d.bom_no = bom_no
				if bom_no:
					bom_nos.append(bom_no)

			if not bom_nos:
				return

			bom_item_doctype = (
				"BOM Explosion Item" if self.filters.include_subassembly_raw_materials else "BOM Item"
			)
			bom = frappe.qb.DocType("BOM")
			bom_item = frappe.qb.DocType(bom_item_doctype)

			qty_field = (
				bom_item.qty_consumed_per_unit
				if self.filters.include_subassembly_raw_materials
				else bom_item.qty / bom.quantity
			)

			select_fields = [
				bom_item.parent,
				bom_item.item_code,
				bom_item.item_name.as_("raw_material_name"),
				qty_field.as_("required_qty_per_unit"),
			]

			# only add bom_no if Doctype actually has it
			if frappe.db.has_column(bom_item_doctype, "bom_no"):
				select_fields.append(bom_item.bom_no)

			raw_materials = (
				frappe.qb.from_(bom)
				.from_(bom_item)
				.select(*select_fields)
				.where(
					(bom_item.parent.isin(bom_nos))
					& (bom_item.parent == bom.name)
					& (bom.docstatus == 1)
				)
			).run(as_dict=True)
			
			# Recursive function to fetch all nested BOM items with proper qty calculation
			def fetch_child_bom_items(parent_bom, bom_no, parent_multiplier=1.0):
				"""
				Recursively fetch all raw materials from a BOM and its child BOMs.
				parent_multiplier: The cumulative quantity multiplier from parent BOMs
				"""
				bom_quantity = frappe.get_cached_value("BOM", bom_no, "quantity") or 1
				child_items = frappe.get_all(
					"BOM Item",
					fields=[
						"parent",
						"item_code",
						"item_name as raw_material_name",
						"qty as required_qty_per_unit",
						"bom_no",
					],
					filters={"parent": bom_no, "docstatus": 1},
				)

				for child in child_items:
					if not child.item_code:
						continue

					# Calculate the required_qty_per_unit considering parent multiplier
					child_qty_per_unit = child["required_qty_per_unit"] / bom_quantity
					cumulative_multiplier = parent_multiplier * child_qty_per_unit

					# Assign parent_bom as top-level FG
					child["parent"] = parent_bom
					child["required_qty_per_unit"] = cumulative_multiplier
					
					self.item_codes.append(child.item_code)
					self.raw_materials_dict[parent_bom].append(child)

					# Recurse if child has its own BOM (sub-assembly)
					if child.get("bom_no"):
						# Pass the cumulative multiplier to calculate nested quantities correctly
						fetch_child_bom_items(parent_bom, child["bom_no"], cumulative_multiplier)

			# Fetch child items recursively for all top-level BOMs
			for d in raw_materials:
				parent_bom = d.parent
				self.raw_materials_dict.setdefault(parent_bom, [])
				self.raw_materials_dict[parent_bom].append(d)

				linked_bom = d.get("bom_no")
				if linked_bom:
					# Pass the parent's required_qty_per_unit as the initial multiplier
					fetch_child_bom_items(parent_bom, linked_bom, d.required_qty_per_unit)
						
		if self.filters.based_on == "Sales Order":
			flattened_list = [item for sublist in self.raw_materials_dict.values() for item in sublist]
			if not flattened_list:
				return

			flattened_list = sorted(flattened_list, key=lambda x: x['parent'])

			self.item_codes.extend([d.item_code for d in flattened_list if d.item_code])
			warehouse_stock = self.get_warehouse_item_stock(item_codes=self.item_codes)

			warehouse_lookup = {wh["item_code"]: wh for wh in warehouse_stock}

			global_seen_items = set()
			stock_fields = set()
			
			if warehouse_stock:
				sample = warehouse_stock[0]
				stock_fields = {k for k in sample.keys() if k != "item_code"}

			for d in flattened_list:
				item_code = d.item_code
				stock_info = {field: 0.0 for field in stock_fields}		

				# First occurrence → update actual warehouse stock
				if item_code not in global_seen_items and item_code in warehouse_lookup:
					stock_info.update(warehouse_lookup[item_code])
					po_qty_data = frappe.db.sql("""
						SELECT SUM(poi.qty) as po_qty
						FROM `tabPurchase Order Item` poi
						JOIN `tabPurchase Order` po ON po.name = poi.parent
						WHERE poi.item_code = %s AND po.status = 'To Receive and Bill'
					""", (item_code,), as_dict=True)
					stock_info["po_qty"] = po_qty_data[0].get('po_qty') if po_qty_data[0].get('po_qty') is not None else 0.0
					
					global_seen_items.add(item_code)
				d.update(stock_info)

		elif self.filters.based_on == "Work Order":
			if not raw_materials:
				return

			raw_materials = sorted(raw_materials, key=lambda x: x['parent'])
			self.item_codes.extend([d.item_code for d in raw_materials])
			warehouse_stock = self.get_warehouse_item_stock(item_codes=self.item_codes)

			warehouse_lookup = {wh["item_code"]: wh for wh in warehouse_stock}

			global_seen_items = set()
			stock_fields = set()
			if warehouse_stock:
				sample = warehouse_stock[0]
				stock_fields = {k for k in sample.keys() if k != "item_code"}

			for d in raw_materials:
				item_code = d.item_code
				parent = d.parent

				self.raw_materials_dict.setdefault(parent, [])
				stock_info = {field: 0.0 for field in stock_fields}

				# First time seen → update with actual warehouse stock
				if item_code not in global_seen_items and item_code in warehouse_lookup:
					stock_info.update(warehouse_lookup[item_code])
					
					po_qty_data = frappe.db.sql("""
						SELECT SUM(poi.qty) as po_qty
						FROM `tabPurchase Order Item` poi
						JOIN `tabPurchase Order` po ON po.name = poi.parent
						WHERE poi.item_code = %s AND po.status = 'To Receive and Bill'
					""", (item_code,), as_dict=True)
					stock_info["po_qty"] = po_qty_data[0].get('po_qty') if po_qty_data[0].get('po_qty') is not None else 0.0

					global_seen_items.add(item_code)

				# Merge stock info into raw material row
				d.update(stock_info)

				# Add to Work Order grouping
				self.raw_materials_dict[parent].append(d)

	def get_item_details(self):
		if not (self.orders and self.item_codes):
			return

		self.item_details = {}
		for d in frappe.get_all(
			"Item Default",
			fields=["parent", "default_warehouse"],
			filters={"company": self.filters.company, "parent": ("in", self.item_codes)},
		):
			self.item_details[d.parent] = d

	def get_bin_details(self):
		if not (self.orders and self.raw_materials_dict):
			return

		self.bin_details = {}
		self.mrp_warehouses = []
		if self.filters.raw_material_warehouse:
			self.mrp_warehouses.extend(get_child_warehouses(self.filters.raw_material_warehouse))
			self.warehouses.extend(self.mrp_warehouses)

		for d in frappe.get_all(
			"Bin",
			fields=["warehouse", "item_code", "actual_qty", "ordered_qty", "projected_qty"],
			filters={"item_code": ("in", self.item_codes), "warehouse": ("in", self.warehouses)},
		):
			key = (d.item_code, d.warehouse)
			if key not in self.bin_details:
				self.bin_details.setdefault(key, d)
	


	def get_purchase_details(self):
		
		if not (self.orders and self.raw_materials_dict):
			return

		self.purchase_details = {}
		
		purchased_items = frappe.get_all(
			"Purchase Order Item",
			fields=["item_code", "min(schedule_date) as arrival_date", "qty as arrival_qty", "warehouse"],
			filters={
				"item_code": ("in", self.item_codes),
				"docstatus": 1,
				"received_qty":0
			},
			group_by="item_code",
		)
		
		
		for d in purchased_items:
			key = d.item_code
			
			if key not in self.purchase_details:
				self.purchase_details.setdefault(key, d)
		
			self.purchase_details[key].po_qty = d.arrival_qty
		
			

   
	def get_warehouse_item_stock(self, item_codes=None):

       
		"""
		Returns a list of dicts with warehouse-wise availability for each item.
		If item_codes is provided, only those items will be considered.
		"""
		
		item_codes = item_codes or self.item_codes
		if not item_codes:
			return []

		
		# warehouses = frappe.get_all("Warehouse", filters={"disabled": 0}, pluck="name")

		bins = frappe.get_all(
			"Bin",
			fields=["item_code", "warehouse", "actual_qty"],
			filters={"item_code": ("in", item_codes)}
		)

	
		stock_map = {(b.item_code, b.warehouse): b.actual_qty for b in bins}
		# New: Get parent warehouse mappings
		parent_warehouse_map = self.get_parent_warehouses_with_children()

		
		report_data = []

		for item in item_codes:
			row = {"item_code": item}
			# New: Sum child warehouse quantities under parent
			#  CORRECT CODE:
			for parent_wh, child_warehouses in parent_warehouse_map.items():
				total_qty = 0
				for child_wh in child_warehouses:
					# Access using tuple key (item_code, warehouse)
					total_qty += stock_map.get((item, child_wh), 0)
				
				row[f"stock_{frappe.scrub(parent_wh)}"] = total_qty
			# for wh in warehouses:
				
			# 	row[f"stock_{frappe.scrub(wh)}"] = stock_map.get((item, wh), 0)
			report_data.append(row)
		
		return report_data

			


	def prepare_data(self):
		if not self.orders:
			return

		for d in self.orders:
			key = d.name if self.filters.based_on == "Work Order" else d.bom_no

			if not self.raw_materials_dict.get(key):
				continue
			

			bin_data = self.bin_details.get((d.production_item, d.warehouse)) or {}
			d.update({"for_warehouse": d.warehouse, "available_qty": 0})

			if bin_data and bin_data.get("actual_qty") > 0 and d.qty_to_manufacture:
				d.available_qty = (
					bin_data.get("actual_qty")
					if (d.qty_to_manufacture > bin_data.get("actual_qty"))
					else d.qty_to_manufacture
				)

				bin_data["actual_qty"] -= d.available_qty

			self.update_raw_materials(d, key)
   
	def calculate_balance_qty(self, row):
		
		"""Calculate balance qty = required_qty - warehouse stock - po_qty"""
		required_qty = row.get("required_qty", 0) or 0
		po_qty = row.get("po_qty", 0) or 0

		
		warehouse_stock = sum(
			value for key, value in row.items()
			if key.startswith("stock_") and isinstance(value, (int, float))
		)

		balance_qty = required_qty - warehouse_stock - po_qty
		return balance_qty 


	def update_raw_materials(self, data, key):
		
		self.index = 0
		self.raw_materials_dict.get(key)

		warehouses = self.mrp_warehouses or []
		for d in self.raw_materials_dict.get(key):
			if self.filters.based_on != "Work Order":
				d.required_qty = d.required_qty_per_unit * data.qty_to_manufacture

			if not warehouses:
				warehouses = [data.warehouse]

			if self.filters.based_on == "Work Order" and d.warehouse:
				warehouses = [d.warehouse]
			else:
				item_details = self.item_details.get(d.item_code)
				if item_details:
					warehouses = [item_details["default_warehouse"]]

			if self.filters.raw_material_warehouse:
				warehouses = get_child_warehouses(self.filters.raw_material_warehouse)

			d.remaining_qty = d.required_qty
			self.pick_materials_from_warehouses(d, data, warehouses)

			if d.remaining_qty and self.filters.raw_material_warehouse and d.remaining_qty != d.required_qty:
				row = self.get_args()
				d.warehouse = self.filters.raw_material_warehouse
				d.required_qty = d.remaining_qty
				d.allotted_qty = 0
				row.update(d)
				self.data.append(row)

	def pick_materials_from_warehouses(self, args, order_data, warehouses):
		for index, warehouse in enumerate(warehouses):
			if not args.remaining_qty:
				return

			row = self.get_args()

			key = (args.item_code, warehouse)
			bin_data = self.bin_details.get(key)

			if bin_data:
				row.update(bin_data)

			args.allotted_qty = 0
			if bin_data and bin_data.get("actual_qty") > 0:
				args.allotted_qty = (
					bin_data.get("actual_qty")
					if (args.required_qty > bin_data.get("actual_qty"))
					else args.required_qty
				)

				args.remaining_qty -= args.allotted_qty
				bin_data["actual_qty"] -= args.allotted_qty

			if (
				self.mrp_warehouses and (args.allotted_qty or index == len(warehouses) - 1)
			) or not self.mrp_warehouses:
				if not self.index:
					row.update(order_data)
					self.index += 1

				args.warehouse = warehouse
				row.update(args)
				if self.purchase_details.get(key):
					row.update(self.purchase_details.get(key))
			
				row.balance_qty = self.calculate_balance_qty(row)

				self.data.append(row)

	def get_args(self):
		return frappe._dict(
			{
				"work_order": "",
				"sales_order": "",
				"production_item": "",
				"production_item_name": "",
				"qty_to_manufacture": "",
				"produced_qty": "",
			}
		)
	
	

	def get_columns(self):
		based_on = self.filters.based_on

		self.columns = [
			{"label": _("ID"), "options": based_on, "fieldname": "name", "fieldtype": "Link", "width": 100},
			{
				"label": _("Item Code"),
				"fieldname": "production_item",
				"fieldtype": "Link",
				"options": "Item",
				"width": 120,
			},
			{
				"label": _("Item Name"),
				"fieldname": "production_item_name",
				"fieldtype": "Data",
				"width": 130,
			},
			
			{"label": _("Order Qty"), "fieldname": "qty_to_manufacture", "fieldtype": "Float", "width": 80},
			
		]

		fieldname, fieldtype = "delivery_date", "Date"
		if self.filters.based_on == "Sales Order" and self.filters.order_by == "Total Amount":
			fieldname, fieldtype = "base_grand_total", "Currency"
		elif self.filters.based_on == "Material Request":
			fieldname = "schedule_date"
		elif self.filters.based_on == "Work Order":
			fieldname = "planned_start_date"

		self.columns.append(
			{
				"label": _(self.filters.order_by),
				"fieldname": fieldname,
				"fieldtype": fieldtype,
				"width": 100,
			}
		)

		self.columns.extend(
			[
				{
					"label": _("Raw Material Code"),
					"fieldname": "item_code",
					"fieldtype": "Link",
					"options": "Item",
					"width": 120,
				},
				{
					"label": _("Raw Material Name"),
					"fieldname": "raw_material_name",
					"fieldtype": "Data",
					"width": 130,
				},
				
				{"label": _("Required Qty"), "fieldname": "required_qty", "fieldtype": "Float", "width": 100},
				
    
				
			]
   
		)
		#  Dynamic Warehouse Stock Columns
		# all_warehouses = frappe.get_all("Warehouse", filters={"disabled": 0}, pluck="name")

		# for wh in sorted(all_warehouses):
		# 	fieldname = f"stock_{frappe.scrub(wh)}"
		# 	self.columns.append({
		# 		"label": _(f"Stock in {wh}"),
		# 		"fieldname": fieldname,
		# 		"fieldtype": "Float",
		# 		"width": 120,
		# 	})

		# New: Only parent warehouses
		parent_warehouse_map = self.get_parent_warehouses_with_children()

		for parent_wh in sorted(parent_warehouse_map.keys()):
			fieldname = f"stock_{frappe.scrub(parent_wh)}"
			self.columns.append({
				"label": _(f"Stock in {parent_wh}"),
				"fieldname": fieldname,
				"fieldtype": "Float",
				"width": 120,
			})
   
		self.columns.extend(
          [
			   {
					"label": _("PO Qty"),
					"fieldname": "po_qty",
					"fieldtype": "Float",
					"width": 140,
			},
      
			{
					"label": _("Balance Qty"),
					"fieldname": "balance_qty",
					"fieldtype": "Float",
					"width": 140,
				}
		  ]
		)
  
 
 
	def get_parent_warehouses_with_children(self):
		parent_warehouse_map = {}

		all_warehouses = frappe.get_all(
			"Warehouse",
			fields=["name", "parent_warehouse", "is_group"],
			filters={"disabled": 0}
		)

		for wh in all_warehouses:
			if wh.is_group:  # Only parent warehouses
				children = get_child_warehouses(wh.name)
				parent_warehouse_map[wh.name] = children

		return parent_warehouse_map