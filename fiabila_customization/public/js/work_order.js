frappe.ui.form.on("Work Order", {
    bom_no: function(frm) {
        if (!frm.doc.bom_no) return;

        frappe.db.get_doc("BOM", frm.doc.bom_no).then(bom => {
            let updates = {};

            if (bom.custom_source_warehouse) {
                updates.source_warehouse = bom.custom_source_warehouse;
            }
            if (bom.custom_workinprogress_warehouse) {
                updates.wip_warehouse = bom.custom_workinprogress_warehouse;
            }
            if (bom.custom_target_warehouse) {
                updates.fg_warehouse = bom.custom_target_warehouse;
            }

            if (Object.keys(updates).length) {
                frm.set_value(updates);
            }
        });
    },

    refresh: function(frm) {
        // Also apply on refresh for newly created WOs not yet saved
        if (frm.doc.bom_no && frm.is_new()) {
            frappe.db.get_doc("BOM", frm.doc.bom_no).then(bom => {
                let updates = {};

                if (bom.custom_source_warehouse) {
                    updates.source_warehouse = bom.custom_source_warehouse;
                }
                if (bom.custom_workinprogress_warehouse) {
                    updates.wip_warehouse = bom.custom_workinprogress_warehouse;
                }
                if (bom.custom_target_warehouse) {
                    updates.fg_warehouse = bom.custom_target_warehouse;
                }

                if (Object.keys(updates).length) {
                    frm.set_value(updates);
                }
            });
        }
    }
});