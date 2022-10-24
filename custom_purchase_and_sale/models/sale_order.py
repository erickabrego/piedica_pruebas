# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError
import datetime
import requests

class SaleOrder(models.Model):
    _inherit = "sale.order"

    x_branch_order_id = fields.Many2one(comodel_name="sale.order", string="Orden sucursal", copy=False)
    x_status_error_crm = fields.Many2one(comodel_name="crm.status", string="Estado de error", copy=False)
    x_from_error_order = fields.Boolean(string="Proveniente de orden con error", copy=False)
    x_error_order = fields.Many2one(comodel_name="sale.order", string="Orden con error", copy=False)
    x_has_factory_rule = fields.Boolean(string="Regla de fabrica", compute="_get_has_factory_rule", store=True)
    x_has_error = fields.Boolean(string="Es una orden con error?", copy=False)

    #Identificamos si la compañía tiene un regla de sucursal
    @api.depends("company_id","company_id.x_is_factory")
    def _get_has_factory_rule(self):
        for rec in self:
            rule_id = rec.env["branch.factory"].sudo().search([("branch_id.id", "=", rec.company_id.id)], limit=1)
            if rule_id:
                rec.x_has_factory_rule = True
            elif rec.company_id.x_is_factory:
                rec.x_has_factory_rule = True
            else:
                rec.x_has_factory_rule = False

    #El historial de la sucursal es un espejo de la fabrica
    def write(self, values):
        res = super(SaleOrder, self).write(values)
        for rec in self:
            if rec.x_branch_order_id:                
                if values.get("estatus_crm"):
                    rec.x_branch_order_id.sudo().write({'estatus_crm': values.get("estatus_crm")})
                if values.get("crm_status_history"):
                    rec.x_branch_order_id.crm_status_history = [(5, 0, 0)]
                    for history in rec.crm_status_history.sorted(lambda line: line.date):
                        data = {
                            "status": history.status.id,
                            "date": history.date
                        }
                        rec.x_branch_order_id.crm_status_history = [(0, 0, data)]
        return res

    #Se identifica si la orden sigue el flujo de sucursal, sino el flujo es el nativo de Odoo
    def action_confirm(self):        
        rule_id = self.env["branch.factory"].sudo().search([("branch_id.id", "=", self.company_id.id)], limit=1)
        if not rule_id:
            self.p_ask_for_send_to_crm = False
        return super(SaleOrder, self).action_confirm()
                
    #Se cancelan ambas ordenes cuando es por sucursal
    def action_cancel(self):
        res = super(SaleOrder, self).action_cancel()
        if self.x_branch_order_id:
            self.x_branch_order_id.sudo().action_cancel()
        else:
            factory_order = self.env["sale.order"].sudo().search([("x_branch_order_id.id", "=", self.id)], limit=1)
            if factory_order:
                factory_order.sudo().action_cancel()
        return res

    #Se crea la orden de compra si es que no se tiene una regla para hacerlo
    def create_branch_purchase_order(self, rule_id, mrp_lines):
        if self.partner_id.x_studio_es_paciente and mrp_lines and rule_id:
            purchase_data = {
                "partner_id": rule_id.factory_id.partner_id.id,
                "company_id": self.company_id.id,
                "partner_ref": self.name,
                "department_id": rule_id.department_id.id,
                "user_id": self.user_id.id
            }
            purchase_id = self.env["purchase.order"].sudo().create(purchase_data)
            for order_line in mrp_lines:
                purchase_line = {
                    "product_id": order_line.product_id.id,
                    "product_qty": order_line.product_uom_qty,
                    "product_uom": order_line.product_uom.id,
                }
                purchase_id.order_line = [(0, 0, purchase_line)]
            return purchase_id

    #Se crea la orden de venta dentro de la fabrica dependiendo de la regla
    def create_factory_sale_order(self,rule_id, purchase_id, mrp_lines):
        if not self.partner_id.id_crm:
            raise ValidationError(f"El paciente {self.partner_id} no cuenta con un id de CRM, favor de sincronizar e intentar de nuevo.")
        sale_data = {
            "partner_id": self.company_id.partner_id.id,
            "partner_shipping_id": self.partner_shipping_id.id,
            "branch_id": self.company_id.partner_id.id,
            "x_studio_selection_field_waqzv": self.x_studio_selection_field_waqzv,
            "company_id": rule_id.factory_id.id,
            "team_id": False,
            "observations": self.observations,
            "user_id": self.user_id.id,
            "p_ask_for_send_to_crm": False,
            "client_order_ref": purchase_id.name,
            "payment_term_id": self.payment_term_id.id,
            "x_branch_order_id": self.id
        }
        sale_order = self.env["sale.order"].sudo().create(sale_data)
        for order_line in mrp_lines:
            sale_line = {
                "product_id": order_line.product_id.id,
                "product_uom_qty": order_line.product_uom_qty,
                "product_uom": order_line.product_uom.id,
                "insole_size": order_line.insole_size,
                "top_cover_id": order_line.top_cover_id.id,
                "design_type": order_line.design_type,
                "analytic_tag_ids": order_line.analytic_tag_ids.ids,
                "main_layer_id": order_line.main_layer_id.id,
                "mid_layer_id": order_line.mid_layer_id.id
            }
            sale_order.order_line = [(0,0,sale_line)]

        confirme_send_obj = self.env["crm.confirm.send"].sudo().create({"sale_order": sale_order.id, "x_is_branch_order":True})
        notification = confirme_send_obj.sudo().send_to_crm()
        if notification and notification['params']['type'] == 'success' and not self.x_from_error_order:
            self.folio_pedido = sale_order.folio_pedido
            self.estatus_crm = sale_order.estatus_crm
        return notification

    #Renvio de información
    def resend_to_crm(self):
        mrp_lines = self.order_line.filtered(
                lambda line: 'Fabricar' in line.product_id.route_ids.mapped('name') and line.product_uom_qty == 1)
        if mrp_lines:
            crm_confirm_obj = self.env["crm.confirm.send"].create({'sale_order': self.id})
            return crm_confirm_obj.send_to_crm()
        else:
            notification = {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': ("Error al reenviar el pedido"),
                    'message': "No existen productos fabricables dentro de la orden.",
                    'type': 'warning',
                    'next': {'type': 'ir.actions.act_window_close'},
                }
            }
            return notification

    def send_error_to_crm(self):
        if self.order_line.filtered(lambda line: line.x_is_error_line):
            crm_status = self.env["crm.status"].sudo().search(['|',('name','=','Error'),("code", "=", "2")], limit=1)
            url = f"https://crmpiedica.com/api/api.php?id_pedido={self.folio_pedido}&id_etapa={crm_status.id}"
            token = self.env['ir.config_parameter'].sudo().get_param("crm.sync.token")
            headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
            response = requests.put(url, headers=headers)

            if self.x_branch_order_id:
                self.send_crm_status_factory(self, response, crm_status)
                self.x_has_error = True
                self.x_branch_order_id.x_has_error = True
            else:
                factory_order = self.env["sale.order"].sudo().search([("x_branch_order_id.id", "=", self.id)], limit=1)
                if factory_order:
                    self.send_crm_status_factory(factory_order, response, crm_status)
                    factory_order.x_has_error = True
                self.x_has_error = True
        else:
            raise ValidationError("No es posible de marcar como error la orden, debido a que no se cuenta con productos con errores.")

    #Copiamos la orden de venta y
    def copy_error_order(self, kwargs):
        error_type = kwargs.get("error_type",None)
        if error_type == "branch_error":
            pricelist_id = self.env["product.pricelist"].sudo().serach([('id','=',80)])
        sale_order_id = self.copy()
        error_lines = sale_order_id.order_line.filtered(lambda line: not line.x_is_error_line)
        for error_line in error_lines:
            sale_order_id.order_line = [(2,error_line.id)]
        sale_order_id.x_error_order = self.id
        sale_order_id.folio_pedido = self.folio_pedido
        sale_order_id.estatus_crm = self.estatus_crm
        sale_order_id.x_from_error_order = True
        crm_status = self.env["crm.status"].sudo().search(['|', ('name', '=', 'Recibido'), ("code", "=", "8")], limit=1)
        sale_order_id.crm_status_history = [(0,0,{'status': crm_status.id, 'date': datetime.datetime.now()})]
        sale_order_id.action_confirm()

        if sale_order_id.x_branch_order_id:
            order_id = sale_order_id
        else:
            order_id = self.env["sale.order"].sudo().search([("x_branch_order_id","=",sale_order_id.id)],limit=1)

        if pricelist_id:
            if sale_order_id.x_branch_order_id:
                sale_order_id.x_branch_order_id.pricelist_id = pricelist_id.id
                sale_order_id.x_branch_order_id.update_prices()
                sale_order_id.pricelist_id = pricelist_id.id
                sale_order_id.update_prices()
            else:
                factory_order = self.env["sale.order"].sudo().search([("x_branch_order_id","=",sale_order_id.id)],limit=1)
                if factory_order:
                    factory_order.pricelist_id.id = pricelist_id.id
                    factory_order.update_prices()
                sale_order_id.pricelist_id = pricelist_id.id
                sale_order_id.update_prices()

        procurement_groups = self.env['procurement.group'].search([('sale_id', 'in', order_id.ids)])
        mrp_orders = procurement_groups.stock_move_ids.created_production_id
        mrp_orders_list = []

        res = {
            'status': 'success',
            'content': {
                'sale_order': {
                    'id': order_id.id,
                    'name': order_id.name
                }

            }
        }
        if mrp_orders:
            for mrp_order in mrp_orders:
                mrp_orders_list.append({
                    'id': mrp_order.id,
                    'name': mrp_order.name,
                    'product_id': mrp_order.product_id.id
                })
            res['content']['mrp_orders'] = mrp_orders_list
        return res

    #Actualiza los status de crm en Odoo tanto para la sucursal y fabrica
    def send_crm_status_factory(self, sale_id, response, crm_status):
        sale_id.sudo().message_post(body=response.content)
        sale_id.sudo().write({'estatus_crm': crm_status.id})
        sale_id.sudo().create_estatus_crm()
