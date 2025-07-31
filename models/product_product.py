from odoo import models, api

class ProductProduct(models.Model):
    _inherit = 'product.product'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)

        StockMles = self.env['stock.mles']
        for product in records:
            # Check if already exists (to avoid duplication)
            if not StockMles.search([('product_id', '=', product.id)], limit=1):
                StockMles.create({'product_id': product.id})

        return records
