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

    @api.depends("company_id")
    def _get_has_factory_rule(self):
        for rec in self:
            rule_id = rec.env["branch.factory"].sudo().search([("branch_id.id", "=", rec.company_id.id)], limit=1)
            rec.x_has_factory_rule = True if rule_id else False

    def write(self, values):
        res = super(SaleOrder, self).write(values)
        for rec in self:
            if rec.x_branch_order_id:                
                if values.get("estatus_crm"):
                    rec.x_branch_order_id.sudo().write({'estatus_crm': values.get("estatus_crm")})
        return res

    def action_confirm(self):        
        rule_id = self.env["branch.factory"].sudo().search([("branch_id.id", "=", self.company_id.id)], limit=1)
        if not rule_id:
            self.p_ask_for_send_to_crm = False
        return super(SaleOrder, self).action_confirm()
                

    def action_cancel(self):
        res = super(SaleOrder, self).action_cancel()
        factory_order = self.env["sale.order"].sudo().search([("x_branch_order_id.id","=",self.id)])
        if factory_order:
            factory_order.sudo().action_cancel()
        return res

    def create_estatus_crm(self):
        res = super(SaleOrder, self).create_estatus_crm()
        for rec in self:
            if rec.x_branch_order_id:
                rec.x_branch_order_id.write({
                    'crm_status_history': [(0, 0, {
                        'sale_order': self.id,
                        'status': self.estatus_crm.id,
                        'date': datetime.datetime.now()
                    })]
                })
        return res

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
        crm_status = self.env["crm.status"].search(['|',('name','=','Error'),("code", "=", "2")], limit=1)
        url = f"https://crmpiedica.com/api/api.php?id_pedido={self.folio_pedido}&id_etapa={crm_status.id}"
        token = self.env['ir.config_parameter'].sudo().get_param("crm.sync.token")
        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
        response = requests.put(url, headers=headers)
        self.message_post(body=response.content)
        self.write({'estatus_crm': crm_status.id})
        self.create_estatus_crm()
        factory_order = self.env["sale.order"].sudo().search([("x_branch_order_id.id","=",self.id)], limit=1)
        if factory_order:
            factory_order.message_post(body=response.content)
            factory_order.write({'estatus_crm': crm_status.id})
            factory_order.create_estatus_crm()

    def copy_error_order(self):
        sale_order_id = self.copy()
        error_lines = sale_order_id.order_line.filtered(lambda line: not line.x_is_error_line)
        for error_line in error_lines:
            sale_order_id.order_line = [(2,error_line.id)]
        sale_order_id.x_error_order = self.id
        sale_order_id.folio_pedido = self.folio_pedido
        sale_order_id.estatus_crm = self.estatus_crm
        sale_order_id.x_from_error_order = True
        sale_order_id.crm_status_history = [(0,0,{'status': self.x_status_error_crm.id, 'date': datetime.datetime.now()})]
        view = self.env.ref('sale.view_order_form')
        return {
            'name': 'Venta por error',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'sale.order',
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'target': 'current',
            'res_id': sale_order_id.id
        }



