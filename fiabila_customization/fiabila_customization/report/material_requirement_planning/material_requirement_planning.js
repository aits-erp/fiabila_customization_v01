// Copyright (c) 2025, dhanvant marathe and contributors
// For license information, please see license.txt


frappe.query_reports["Material Requirement Planning"] =
 {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			reqd: 1,
			default: frappe.defaults.get_user_default("Company"),
		},
		{
			fieldname: "based_on",
			label: __("Based On"),
			fieldtype: "Select",
			options: ["Sales Order", "Work Order"],
			default: "Sales Order",
			reqd: 1,
			on_change: function () {
				let filters = frappe.query_report.filters;
				let based_on = frappe.query_report.get_filter_value("based_on");
				let options = {
					"Sales Order": ["Delivery Date", "Total Amount"],
					"Material Request": ["Required Date"],
					"Work Order": ["Planned Start Date"],
				};

				filters.forEach((d) => {
					if (d.fieldname == "order_by") {
						d.df.options = options[based_on];
						d.set_input(d.df.options);
					}
				});

				frappe.query_report.refresh();
			},
		},
	
		{
			fieldname: "item_group",
			label: __("Item Group"),
			fieldtype: "Link",
			options: "Item Group",
		
		},
				{
			"fieldname": "from_doc",
			"label": __("From"),
			"fieldtype": "Link",
			"options": "Sales Order",
			"depends_on": "eval:doc.based_on == 'Sales Order'" 
			
		},

		{
			"fieldname": "to_doc",
			"label": __("To"),
			"fieldtype": "Link",
			"options": "Sales Order",
			"depends_on": "eval:doc.based_on == 'Sales Order'"  
			
		},
		
		{
			fieldname: "order_by",
			label: __("Order By"),
			fieldtype: "Select",
			options: ["Delivery Date", "Total Amount"],
			default: "Delivery Date",
		},
		
	],

	onload: function (report) {

		// Get the selected item group filter value (if any)
		const item_group_filter = report.get_filter_value("item_group");
		console.log("Selected Item Group Filter →", item_group_filter);

		// Add a custom button to create Material Request
		report.page.add_button(__('Create Material Request'), function() {

			// Step 1: Check report data
			if (!report.data || report.data.length === 0) {
				frappe.msgprint(__('No data found in report.'));
				return;
			}

			// Step 2: Aggregate total qty by item_code
			const itemTotals = {};
			report.data.forEach(row => {
				if (!row.item_code) return;

				const item_code = row.item_code;
				const qty = flt(row.balance_qty) || 0;

				// Only include positive or required qtys
				if (qty > 0) {
					itemTotals[item_code] = (itemTotals[item_code] || 0) + qty;
				}
			});

			const items = Object.entries(itemTotals).map(([item_code, qty]) => ({
				item_code: item_code,
				qty: Math.abs(qty)
			}));

			if (items.length === 0) {
				frappe.msgprint(__('No valid items with positive quantity to create Material Request.'));
				return;
			}

			// Step 3: Confirm before creating Material Request
			frappe.confirm(
				`Do you want to create a Material Request for <b>${items.length}</b> item(s)?`,
				() => {
					// User confirmed — call backend
					frappe.call({
						method: "fiabila_customization.fiabila_customization.report.material_requirement_planning.material_requirement_planning.create_material_request_draft",
						args: {
							items: items,
							item_group_filter: item_group_filter
						},
						freeze: true,
						freeze_message: __("Creating Material Request..."),
						callback: function (r) {
							if (r.message) {
								if (r.message.created_requests) {
									// If multiple MRs created
									const list = r.message.created_requests.map(mr => `<li>${mr}</li>`).join("");
									frappe.msgprint({
										title: __("Material Requests Created"),
										message: `<ul>${list}</ul>`,
										indicator: "green"
									});
								} else {
									frappe.msgprint(r.message);
								}
							} else {
								frappe.msgprint({
									title: __("No Material Request Created"),
									message: __("All item groups already have an existing Material Request."),
									indicator: "orange"
								});
							}
						}
					});
				},
				() => {
					// Cancelled
					frappe.msgprint(__("Material Request creation cancelled."));
				}
			);
		});
	}


}
