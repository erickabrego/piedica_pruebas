# -*- coding: utf-8 -*-
{
    'name': "Fabricación a sucursales",
    'summary': """
        Sincronización con CRM de ventas en sucursal y fabrica.
    """,
    'description': """
        Sincronización con CRM de ventas en sucursal y fabrica.
    """,
    'author': "M22",
    'website': "http://www.yourcompany.com",
    'category': 'Venta y compra',
    'version': '14.0.1',
    'depends': ['base','sale_management','purchase','crm_sync_orders','hr','purchase_request'],
    'data': [
        'security/ir.model.access.csv',
        'views/branch_factory.xml',
        'views/sale_order.xml'
    ],
    'license': 'AGPL-3'
}
