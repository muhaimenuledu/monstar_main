# -*- coding: utf-8 -*-
{
    'name': "Monstar Main",

    'author': "MLES/Pranto",

    'category': 'Accounting',

    'license' : "LGPL-3",

    'version': '18.0.0.1',

    # any module necessary for this one to work correctly

    'depends': ['base','product','contacts','account','sale_management', 'purchase'],

    # always loaded
    'images': ['static/description/icon.png'],

    'data': [
        'security/ir.model.access.csv',
        'views/views.xml',
        'views/general_ledger_view.xml',
        'views/partner_ledger_view.xml',
        'views/partner_ledger_group_view.xml',
        'views/stock_report_view.xml',
        'views/stock_summary_wizard_views.xml',
        'views/group.xml',
        'views/res_partner_views.xml',
        'views/beta_view.xml',
        'views/party_stock_view.xml',


        
        'views/menu.xml',
    ],

}

