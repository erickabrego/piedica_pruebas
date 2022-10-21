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
                if picking_id.sale_id and picking_id.sale_id.folio_pedido:
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
                    crm_status = self.env["crm.status"].search(['|', ('name', '=', 'Enviado'), ("code", "=", "6")], limit=1)
                    if picking_id.sale_id:
                        if picking_id.sale_id.x_branch_order_id:
                            self.send_crm_status_factory(picking_id.sale_id.x_branch_order_id, response, crm_status)
                            self.send_crm_status_factory(picking_id.sale_id, response, crm_status)
                        else:
                            factory_order = self.env["sale.order"].sudo().search([("x_branch_order_id.id", "=", picking_id.sale_id.id)], limit=1)
                            if factory_order:
                                self.send_crm_status_factory(factory_order, response, crm_status)
                            self.send_crm_status_factory(picking_id.sale_id, response, crm_status)
        return res

    def send_crm_status_factory(self, sale_id, response, crm_status):
        sale_id.sudo().message_post(body=response.content)
        sale_id.sudo().write({'estatus_crm': crm_status.id})
        sale_id.sudo().create_estatus_crm()