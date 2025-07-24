# -*- coding: utf-8 -*-
{
    'name': "monstar_main",

    'summary': "Sales, Accounting, Inventory Customization",

    'description': """ Implement Clents Requirement """,

    'author': "MLES/Pranto",

    'category': 'Accounting',

    'version': '18.1',

    # any module necessary for this one to work correctly

    'depends': ['base','product','contacts','account','sale_management', 'purchase'],

    # always loaded

    'data': [
        'security/ir.model.access.csv',
        'views/views.xml',

    ],

}

