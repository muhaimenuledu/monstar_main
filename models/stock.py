# -*- coding: utf-8 -*-
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
                rec.categ_id = product.categ_id.id if product.categ_id else False
                rec.list_price = product.list_price
                rec.uom_id = product.uom_id.id if product.uom_id else False
            else:
                rec.name = False
                rec.default_code = False
                rec.categ_id = False
                rec.list_price = 0.0
                rec.uom_id = False

    @api.depends('product_id')
    def _compute_qty_movement(self):
        StockMoveLine = self.env['stock.move.line'].sudo()
        StockLocation = self.env['stock.location'].sudo()

        ctx = self.env.context
        date_from = ctx.get('date_from') or (date.today() - timedelta(days=30))
        date_to = ctx.get('date_to') or date.today()

        for rec in self:
            if not rec.product_id:
                rec.qty_in = 0.0
                rec.qty_out = 0.0
                continue

            target_company = rec.company_id or self.env.company

            # Fetch internal locations safely using sudo and company scoping
            internal_locations = StockLocation.search([
                ('usage', '=', 'internal'),
                '|', ('company_id', '=', False), ('company_id', '=', target_company.id)
            ]).ids

            domain = [
                ('product_id', '=', rec.product_id.id),
                ('date', '>=', date_from),
                ('date', '<=', date_to),
                ('state', '=', 'done'),
                ('company_id', '=', target_company.id),
            ]

            incoming = StockMoveLine.search(domain + [('location_dest_id', 'in', internal_locations)])
            outgoing = StockMoveLine.search(domain + [('location_id', 'in', internal_locations)])

            # Compatible across Odoo versions (qty_done vs quantity)
            qty_field = 'quantity' if 'quantity' in StockMoveLine._fields else 'qty_done'
            rec.qty_in = sum(getattr(move, qty_field) for move in incoming)
            rec.qty_out = sum(getattr(move, qty_field) for move in outgoing)

    def _compute_qty_available(self):
        for rec in self:
            if rec.product_id:
                target_company = rec.company_id or self.env.company
                rec.qty_available = rec.product_id.sudo().with_company(target_company).qty_available
            else:
                rec.qty_available = 0.0

    @api.model
    def _populate_product_summaries(self):
        company = self.env.company

        # Unlink existing records for THIS company only using sudo()
        self.sudo().search([('company_id', '=', company.id)]).unlink()

        # Search products allowed for the active company
        domain = ['|', ('company_id', '=', False), ('company_id', '=', company.id)]
        products = self.env['product.product'].sudo().search(domain)

        # Batch create stock.mles records with sudo()
        vals_list = [{
            'product_id': product.id,
            'company_id': company.id,
        } for product in products]

        if vals_list:
            self.sudo().create(vals_list)

    def action_refresh_stock_summary(self):
        """Button-triggered method to refresh product list for current company."""
        self._populate_product_summaries()
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
