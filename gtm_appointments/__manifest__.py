{
    'name': "Google Tag Manager",
    'summary': "Integra Google Tag Manager en Odoo",
    'description': """
        Integra Google Tag Manager en Odoo
    """,
    'category': '',
    'version': '14.0.1',
    'depends': ['web', 'website', 'website_calendar'],
    'data': [
        'views/assets.xml',
        'views/res_config_settings_views.xml',
        'views/website_templates.xml'
    ]
}
