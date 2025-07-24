from odoo import models, fields, api
from datetime import datetime
from dateutil.relativedelta import relativedelta


class MonstarMain(models.Model):
    _name = 'monstar_main.monstar_main'
    _description = 'Monstar Product Monthly Summary'

    product_id = fields.Many2one('product.product', string='Product', required=True)

    name = fields.Char(string='Product Name', compute='_compute_product_info', store=True)
    default_code = fields.Char(string='Internal Reference', compute='_compute_product_info', store=True)
    categ_id = fields.Many2one('product.category', string='Category', compute='_compute_product_info', store=True)
    list_price = fields.Float(string='Sales Price', compute='_compute_product_info', store=True)


    # partner

    partner_id = fields.Many2one('res.partner', string='Partner', required=True)
    pname = fields.Char(string='Name', related='partner_id.name', store=True)
    email = fields.Char(string='Email', related='partner_id.email', store=True)
    phone = fields.Char(string='Phone', related='partner_id.phone', store=True)
    vat = fields.Char(string='VAT', related='partner_id.vat', store=True)
    company_type = fields.Selection(related='partner_id.company_type', store=True)
    credit = fields.Monetary(string='Receivable', related='partner_id.credit', store=True)
    debit = fields.Monetary(string='Payable', related='partner_id.debit', store=True)
    currency_id = fields.Many2one('res.currency', string='Currency', related='partner_id.currency_id', store=True)
    customer_rank = fields.Integer(string='Customer Rank', related='partner_id.customer_rank', store=True)
    supplier_rank = fields.Integer(string='Supplier Rank', related='partner_id.supplier_rank', store=True)
    balance = fields.Monetary(string='Balance', compute='_compute_balance', store=True, currency_field='currency_id')
    move_line_ids = fields.One2many('account.move.line', 'partner_id', string='Journal Items')
    journal_entry_count = fields.Integer(string='Journal Entry Count', compute='_compute_journal_entry_count')

    @api.depends('credit', 'debit')
    def _compute_balance(self):
        for rec in self:
            rec.balance = rec.credit - rec.debit
    @api.depends('move_line_ids')
    def _compute_journal_entry_count(self):
        for rec in self:
            rec.journal_entry_count = len(rec.move_line_ids)

    year = fields.Integer(
        string='Year',
        required=True,
        default=lambda self: datetime.now().year
    )

    month = fields.Selection(
        [(str(m), datetime(1900, m, 1).strftime('%B')) for m in range(1, 13)],
        string='Month',
        required=True,
        default=lambda self: str(datetime.now().month)
    )

    qin = fields.Float(string='Qty In', compute='_compute_product_quantity', store=False)
    qout = fields.Float(string='Qty Out', compute='_compute_product_quantity', store=False)

    @api.depends('product_id')
    def _compute_product_info(self):
        for record in self:
            product = record.product_id
            if product:
                record.name = product.name
                record.default_code = product.default_code
                record.categ_id = product.categ_id.id
                record.list_price = product.list_price
            else:
                record.name = False
                record.default_code = False
                record.categ_id = False
                record.list_price = 0.0

    @api.depends('product_id', 'year', 'month')
    def _compute_product_quantity(self):
        for record in self:
            record.qin = 0.0
            record.qout = 0.0

            if not record.product_id or not record.year or not record.month:
                continue

            try:
                year = int(record.year)
                month = int(record.month)
                start_date = datetime(year, month, 1)
                end_date = (start_date + relativedelta(months=1)) - relativedelta(seconds=1)
            except Exception:
                continue

            moves = self.env['stock.move'].sudo().search([
                ('product_id', '=', record.product_id.id),
                ('date', '>=', start_date),
                ('date', '<=', end_date),
                ('state', '=', 'done'),
            ])

            for move in moves:
                if move.location_id.usage != 'internal' and move.location_dest_id.usage == 'internal':
                    record.qin += move.product_uom_qty
                elif move.location_id.usage == 'internal' and move.location_dest_id.usage != 'internal':
                    record.qout += move.product_uom_qty
