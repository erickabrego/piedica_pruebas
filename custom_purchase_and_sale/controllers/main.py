from odoo.http import Controller, request, route, Response

class MainController(Controller):

    @route('/sync-error-orders/<id>', type='json', auth='none')
    def copy_error_order(self, id, **kwargs):
        if not str(id).isnumeric():
            return {
                'status': 'error',
                'message': 'El id de la orden de venta debe ser un valor numérico. Valor introducido: %s' % str(id)
            }
        order = request.env['sale.order'].sudo().search([('id', '=', id)])
        if not order:
            return {
                'status': 'error',
                'message': 'No se encontró la orden de venta con el id %s' % id
            }
        copy_order = order.sudo().copy_error_order()
        if copy_order:
            return {
                'status': 'success',
                'message': f'Se realizó la creación de la nueva orden de venta con id {copy_order.get("res_id")}'
            }
        else:
            return {
                'status': 'error',
                'message': f'No fue posible crear la nueva orden a partir del error.'
            }