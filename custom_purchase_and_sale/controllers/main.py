from odoo.http import Controller, request, route, Response
import logging
import json
_logger = logging.getLogger(__name__)


class MainController(Controller):

    @route('/sync-error-orders/<id>', type='http', auth='none')
    def copy_error_order(self, id, **kwargs):
        response = []

        if not str(id).isnumeric():
            response.append({
                'status': 'error',
                'message': 'El id de la orden de venta debe ser un valor numérico. Valor introducido: %s' % str(id)
            })
        order = request.env['sale.order'].sudo().search([('id', '=', id)])
        if not order:
            response.append({
                'status': 'error',
                'message': 'No se encontró la orden de venta con el id %s' % id
            })
        else:
            copy_order = order.sudo().copy_error_order()
            if copy_order:
                response.append({
                    'status': 'success',
                    'message': f'Se realizó la creación de la nueva orden de venta con id {copy_order.get("res_id")}'
                })

            else:
                response.append({
                    'status': 'error',
                    'message': f'No fue posible crear la nueva orden a partir del error.'
                })

        return json.dumps(response, indent=2)