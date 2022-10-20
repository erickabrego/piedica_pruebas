from odoo import api, fields, models, _
import requests

class MergeDeliveries(models.TransientModel):
    _inherit = "merge.deliveries.wizard"

    def prepare_to_merge_deliveries(self):
        res = super(MergeDeliveries, self).prepare_to_merge_deliveries()
        merge_picking = self.env["stock.picking"].sudo().browse(res.get("res_id"))
        if merge_picking:
            merge_picking.x_merge_pickings = self.picking_ids.ids
            merge_picking.origin = self.picking_ids.mapped("sale_id.name")
        return res