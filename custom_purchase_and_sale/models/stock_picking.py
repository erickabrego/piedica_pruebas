from odoo import api, fields, models
import requests

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    x_merge_pickings = fields.Char(string="Transferencias agrupadas")

    def button_validate(self):
        res = super(StockPicking, self).button_validate()
        if self.x_merge_pickings:
            picking_ids = eval(str(self.x_merge_pickings))
            for picking in picking_ids:
                picking_id = self.env["stock.picking"].sudo().browse(picking)
                if picking_id.sale_id.folio_pedido:
                    url = f"https://crmpiedica.com/api/api.php?id_pedido={picking_id.sale_id.folio_pedido}&id_etapa=6"

                    # no. seguimiento
                    if picking_id.carrier_tracking_ref:
                        url += '&guia_rastreo=' + picking_id.carrier_tracking_ref

                    # transportista
                    if picking_id.carrier_id:
                        url += '&transportista=' + picking_id.carrier_id.name

                    token = self.env['ir.config_parameter'].sudo().get_param("crm.sync.token")
                    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
                    response = requests.put(url, headers=headers)
                    picking_id.sale_id.message_post(body=response.content)
        return res