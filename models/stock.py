from odoo import api, fields, models
from datetime import date, timedelta


class StockSummary(models.Model):
    _name = 'stock.mles'
    _description = 'Stock Summary Report'

    product_id = fields.Many2one('product.product', string='Product', required=True, index=True)
    name = fields.Char(string="Product Name", compute='_compute_product_details', store=True)
    default_code = fields.Char(string='Internal Reference', compute='_compute_product_details', store=True)
    categ_id = fields.Many2one('product.category', string="Product Category", compute='_compute_product_details', store=True)
    list_price = fields.Float(string="Sales Price", compute='_compute_product_details', store=True)
    uom_id = fields.Many2one('uom.uom', string="Unit of Measure", compute='_compute_product_details', store=True)

    qty_in = fields.Float(string="Quantity In", compute="_compute_qty_movement", store=False)
    qty_out = fields.Float(string="Quantity Out", compute="_compute_qty_movement", store=False)
    qty_available = fields.Float(string="Current Stock", compute="_compute_qty_available", store=False)

    company_id = fields.Many2one(
        'res.company', string="Company", required=True,
        default=lambda self: self.env.company,
        index=True
    )

    @api.depends('product_id')
    def _compute_product_details(self):
        for rec in self:
            product = rec.product_id.sudo() if rec.product_id else False
            if product:
                rec.name = product.name
                rec.default_code = product.default_code
                rec.categ_id = product.categ_id.id
                rec.list_price = product.list_price
                rec.uom_id = product.uom_id.id
            else:
                rec.name = False
                rec.default_code = False
                rec.categ_id = False
                rec.list_price = 0.0
                rec.uom_id = False

    @api.depends('product_id')
    def _compute_qty_movement(self):
        StockMoveLine = self.env['stock.move.line'].sudo()
        ctx = self.env.context
        date_from = ctx.get('date_from') or (date.today() - timedelta(days=30))
        date_to = ctx.get('date_to') or date.today()

        for rec in self:
            if not rec.product_id:
                rec.qty_in = 0.0
                rec.qty_out = 0.0
                continue

            domain = [
                ('product_id', '=', rec.product_id.id),
                ('date', '>=', date_from),
                ('date', '<=', date_to),
            ]

            incoming = StockMoveLine.search(domain + [('location_dest_id.usage', '=', 'internal')])
            outgoing = StockMoveLine.search(domain + [('location_id.usage', '=', 'internal')])

            rec.qty_in = sum(move.qty_done for move in incoming)
            rec.qty_out = sum(move.qty_done for move in outgoing)

    def _compute_qty_available(self):
        for rec in self:
            rec.qty_available = rec.product_id.sudo().qty_available if rec.product_id else 0.0

    @api.model
    def _populate_product_summaries(self):
        company = self.env.company

        # 1. Delete all records across all companies (clean global slate)
        self.search([]).unlink()

        # 2. Get products for the current company or shared products
        domain = ['|', ('company_id', '=', False), ('company_id', '=', company.id)]
        products = self.env['product.product'].sudo().search(domain)

        # 3. Create stock.mles entries for current company only
        for product in products:
            self.create({
                'product_id': product.id,
                'company_id': company.id,
            })

    @api.model
    def init(self):
        self._populate_product_summaries()
    
    def action_refresh_stock_summary(self):
        """Button-triggered method to refresh product list for current company."""
        self._populate_product_summaries()
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

# stock report with wizard and product refresh