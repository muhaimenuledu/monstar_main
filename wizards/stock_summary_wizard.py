from odoo import models, fields
from datetime import date, timedelta

class StockSummaryWizard(models.TransientModel):
    _name = 'stock.summary.wizard'
    _description = 'Stock Summary Date Filter Wizard'

    date_from = fields.Date(string="From Date", required=True, default=lambda self: date.today() - timedelta(days=30))
    date_to = fields.Date(string="To Date", required=True, default=lambda self: date.today())

    def action_show_stock_summary(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Stock Summary',
            'res_model': 'stock.mles',
            'view_mode': 'list',
            'target': 'current',
            'context': {
                'date_from': self.date_from.isoformat(),
                'date_to': self.date_to.isoformat(),
            },
        }
