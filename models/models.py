from odoo import models, fields, api
from datetime import datetime
from dateutil.relativedelta import relativedelta


class MonstarMain(models.Model):
    _name = 'monstar_main.monstar_main'
    _description = 'Monstar Product Monthly Summary'

    # product_id = fields.Many2one('product.product', string='Product', required=True)

    # name = fields.Char(string='Product Name', compute='_compute_product_info', store=True)
    # default_code = fields.Char(string='Internal Reference', compute='_compute_product_info', store=True)
    # categ_id = fields.Many2one('product.category', string='Category', compute='_compute_product_info', store=True)
    # list_price = fields.Float(string='Sales Price', compute='_compute_product_info', store=True)


    # GL
    # account_names = fields.Text(string="All Chart of Accounts", compute="_compute_all_account_names", store=False)

    # @api.depends()
    # def _compute_all_account_names(self):
    #     Account = self.env['account.account'].sudo()
    #     all_accounts = Account.search([], order='name')
    #     names = '\n'.join([acct.name for acct in all_accounts])  # <- one per line

    #     for rec in self:
    #         rec.account_names = names

    # separating gl 

    # account_names = fields.Text(string="All Chart of Accounts", compute="_compute_all_account_data", store=False)
    # partner_names = fields.Text(string="Partners", compute="_compute_all_account_data", store=False)
    # account_breakdown = fields.Text(string="Account Line Breakdown", compute="_compute_all_account_data", store=False)
    # journal_items = fields.Text(string="Accounts|Journal Breakdown", compute="_compute_all_account_data", store=False)

    # total_debit = fields.Float(string="Total Debit", compute="_compute_all_account_data", store=False)
    # total_credit = fields.Float(string="Total Credit", compute="_compute_all_account_data", store=False)

    # @api.depends()
    # def _compute_all_account_data(self):
    #     AccountMoveLine = self.env['account.move.line'].sudo()
    #     Account = self.env['account.account'].sudo()
    #     all_accounts = Account.search([], order='code')

    #     for rec in self:
    #         # All account names
    #         rec.account_names = '\n'.join([acct.name for acct in all_accounts])

    #         # Journal items
    #         move_lines = AccountMoveLine.search([
    #             ('account_id', 'in', all_accounts.ids),
    #             ('move_id.state', '=', 'posted')
    #         ])

    #         # Partners
    #         partners = move_lines.mapped('partner_id.name')
    #         rec.partner_names = '\n'.join(partners) if partners else 'N/A'

    #         # Total debit and credit
    #         rec.total_debit = sum(move_lines.mapped('debit'))
    #         rec.total_credit = sum(move_lines.mapped('credit'))

    #         # Breakdown per account
    #         breakdown_lines = []
    #         for account in all_accounts:
    #             lines = move_lines.filtered(lambda ml: ml.account_id == account)

    #             if not lines:
    #                 continue

    #             breakdown_lines.append(f"[{account.code}] {account.name}")
    #             for line in lines:
    #                 ref = line.move_id.name or 'N/A'
    #                 debit = line.debit
    #                 credit = line.credit
    #                 breakdown_lines.append(f"  - {ref} | Debit: {debit:.2f} | Credit: {credit:.2f}")
    #         rec.account_breakdown = '\n'.join(breakdown_lines)

    #         # Journal item details
    #         journal_item_lines = []

    #         for account in all_accounts:
    #             lines = move_lines.filtered(lambda l: l.account_id == account)
    #             if not lines:
    #                 continue

    #             journal_item_lines.append("")
    #             journal_item_lines.append("═" * 80)
    #             journal_item_lines.append(f"{account.code} - {account.name}")
    #             journal_item_lines.append("═" * 80)

    #             for line in lines:
    #                 journal_item_lines.append(f"  Date     : {line.date}")
    #                 journal_item_lines.append(f"  Ref      : {line.move_id.name or 'N/A'}")
    #                 journal_item_lines.append(f"  Partner  : {line.partner_id.name or 'N/A'}")
    #                 journal_item_lines.append(f"  Label    : {line.name or '-'}")
    #                 journal_item_lines.append(f"  Account  : {line.account_id.name}")
    #                 journal_item_lines.append(f"  Debit    : {line.debit:.2f}")
    #                 journal_item_lines.append(f"  Credit   : {line.credit:.2f}")
    #                 journal_item_lines.append("  " + "-" * 60)
    #             move = line.move_id
    #             full_lines = move.line_ids.sorted(key=lambda l: l.account_id.code)

    #             journal_item_lines.append("  Full Journal Lines:")
    #             journal_item_lines.append("  {:<30} {:<30} {:>10} {:>10}".format("Account", "Partner", "Debit", "Credit"))
    #             journal_item_lines.append("  " + "-" * 90)

    #             for jline in full_lines:
    #                 acc = f"{jline.account_id.code} {jline.account_id.name}"
    #                 partner = jline.partner_id.name or '-'
    #                 debit = f"{jline.debit:.2f}"
    #                 credit = f"{jline.credit:.2f}"

    #                 journal_item_lines.append("  {:<30} {:<30} {:>10} {:>10}".format(acc[:30], partner[:30], debit, credit))
                
    #             journal_item_lines.append("  " + "=" * 90)
    #         rec.journal_items = '\n'.join(journal_item_lines)

    #Partner Report

    # partner_journal_breakdown = fields.Text(string="Partner Journal Breakdown", compute="_compute_all_account_data2", store=False)

    # @api.depends()
    # def _compute_all_account_data2(self):
    #     AccountMoveLine = self.env['account.move.line'].sudo()
    #     Account = self.env['account.account'].sudo()

    #     # Search only posted move lines with partner and account
    #     move_lines = AccountMoveLine.search([
    #         ('partner_id', '!=', False),
    #         ('move_id.state', '=', 'posted')
    #     ])

    #     for rec in self:
    #         breakdown = []

    #         # Filter lines for this record if needed (or use global move_lines)
    #         lines_by_partner = {}
    #         for line in move_lines:
    #             partner = line.partner_id
    #             if partner not in lines_by_partner:
    #                 lines_by_partner[partner] = []
    #             lines_by_partner[partner].append(line)

    #         for partner, lines in lines_by_partner.items():
    #             breakdown.append("")
    #             breakdown.append("=" * 80)
    #             breakdown.append(f"Partner: {partner.name}")
    #             breakdown.append("=" * 80)

    #             # 🟢 Open Balance Logic
    #             total_debit = sum(line.debit for line in lines)
    #             total_credit = sum(line.credit for line in lines)
    #             open_balance = total_debit - total_credit
    #             breakdown.append(f"  Total Debit : {total_debit:.2f}")
    #             breakdown.append(f"  Total Credit: {total_credit:.2f}")
    #             breakdown.append(f"  Open Balance: {open_balance:.2f}")
    #             breakdown.append("-" * 80)

    #             for line in lines:
    #                 breakdown.append(f"  Date     : {line.date}")
    #                 breakdown.append(f"  Ref      : {line.move_id.name or 'N/A'}")
    #                 breakdown.append(f"  Label    : {line.name or '-'}")
    #                 breakdown.append(f"  Account  : {line.account_id.code} {line.account_id.name}")
    #                 breakdown.append(f"  Debit    : {line.debit:.2f}")
    #                 breakdown.append(f"  Credit   : {line.credit:.2f}")
    #                 breakdown.append("  " + "-" * 60)

    #             move = lines[0].move_id
    #             full_lines = move.line_ids.sorted(key=lambda l: l.account_id.code or '')

    #             breakdown.append("  Full Journal Lines:")
    #             breakdown.append("  {:<30} {:<30} {:>10} {:>10}".format("Account", "Partner", "Debit", "Credit"))
    #             breakdown.append("  " + "-" * 90)
    #             for jline in full_lines:
    #                 acc = f"{jline.account_id.code} {jline.account_id.name}"
    #                 partner_name = jline.partner_id.name or '-'
    #                 breakdown.append("  {:<30} {:<30} {:>10.2f} {:>10.2f}".format(
    #                     acc[:30], partner_name[:30], jline.debit, jline.credit
    #                 ))
    #             breakdown.append("  " + "=" * 90)

    #         rec.partner_journal_breakdown = '\n'.join(breakdown) if breakdown else 'No partner data found.'


    # partner
    # separating partner

    # partner_id = fields.Many2one('res.partner', string='Partner', required=True)
    # pname = fields.Char(string='Name', related='partner_id.name', store=True)
    # email = fields.Char(string='Email', related='partner_id.email', store=True)
    # phone = fields.Char(string='Phone', related='partner_id.phone', store=True)
    # vat = fields.Char(string='VAT', related='partner_id.vat', store=True)
    # company_type = fields.Selection(related='partner_id.company_type', store=True)
    # credit = fields.Monetary(string='Receivable', related='partner_id.credit', store=True)
    # debit = fields.Monetary(string='Payable', related='partner_id.debit', store=True)
    # currency_id = fields.Many2one('res.currency', string='Currency', related='partner_id.currency_id', store=True)
    # customer_rank = fields.Integer(string='Customer Rank', related='partner_id.customer_rank', store=True)
    # supplier_rank = fields.Integer(string='Supplier Rank', related='partner_id.supplier_rank', store=True)
    # balance = fields.Monetary(string='Balance', compute='_compute_balance', store=True, currency_field='currency_id')
    # move_line_ids = fields.One2many('account.move.line', 'partner_id', string='Journal Items')
    # journal_entry_count = fields.Integer(string='Journal Entry Count', compute='_compute_journal_entry_count')

    # account_receivable_id = fields.Many2one(
    #     'account.account',
    #     string='Receivable Account',
    #     related='partner_id.property_account_receivable_id',
    #     store=False,
    # )

    # account_payable_id = fields.Many2one(
    #     'account.account',
    #     string='Payable Account',
    #     related='partner_id.property_account_payable_id',
    #     store=False,
    # )

    # @api.depends('credit', 'debit')
    # def _compute_balance(self):
    #     for rec in self:
    #         rec.balance = rec.credit - rec.debit
    # @api.depends('move_line_ids')
    # def _compute_journal_entry_count(self):
    #     for rec in self:
    #         rec.journal_entry_count = len(rec.move_line_ids)

    # year = fields.Integer(
    #     string='Year',
    #     required=True,
    #     default=lambda self: datetime.now().year
    # )

    # month = fields.Selection(
    #     [(str(m), datetime(1900, m, 1).strftime('%B')) for m in range(1, 13)],
    #     string='Month',
    #     required=True,
    #     default=lambda self: str(datetime.now().month)
    # )

    # qin = fields.Float(string='Qty In', compute='_compute_product_quantity', store=False)
    # qout = fields.Float(string='Qty Out', compute='_compute_product_quantity', store=False)

    # @api.depends('product_id')
    # def _compute_product_info(self):
    #     for record in self:
    #         product = record.product_id
    #         if product:
    #             record.name = product.name
    #             record.default_code = product.default_code
    #             record.categ_id = product.categ_id.id
    #             record.list_price = product.list_price
    #         else:
    #             record.name = False
    #             record.default_code = False
    #             record.categ_id = False
    #             record.list_price = 0.0

    # @api.depends('product_id', 'year', 'month')
    # def _compute_product_quantity(self):
    #     for record in self:
    #         record.qin = 0.0
    #         record.qout = 0.0

    #         if not record.product_id or not record.year or not record.month:
    #             continue

    #         try:
    #             year = int(record.year)
    #             month = int(record.month)
    #             start_date = datetime(year, month, 1)
    #             end_date = (start_date + relativedelta(months=1)) - relativedelta(seconds=1)
    #         except Exception:
    #             continue

    #         moves = self.env['stock.move'].sudo().search([
    #             ('product_id', '=', record.product_id.id),
    #             ('date', '>=', start_date),
    #             ('date', '<=', end_date),
    #             ('state', '=', 'done'),
    #         ])

    #         for move in moves:
    #             if move.location_id.usage != 'internal' and move.location_dest_id.usage == 'internal':
    #                 record.qin += move.product_uom_qty
    #             elif move.location_id.usage == 'internal' and move.location_dest_id.usage != 'internal':
    #                 record.qout += move.product_uom_qty
