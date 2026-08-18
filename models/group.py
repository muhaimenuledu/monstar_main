# -*- coding: utf-8 -*-
from odoo import api, models, fields


class GeneralLedger(models.Model):
    _name = 'group.party'
    _description = "Partner Ledger Custom HTML Report"

    date_from = fields.Date(string="Start Date")
    date_to = fields.Date(string="End Date")
    partner_id = fields.Many2one('res.partner', string="Partner")

    company_id = fields.Many2one(
        'res.company',
        string="Company",
        default=lambda self: self.env.company,
        domain=lambda self: [('id', 'in', self.env.companies.ids)],
        help="Filter partners and transactions by company"
    )

    vendor_group = fields.Selection(
        selection=lambda self: self._get_vendor_groups(),
        string="Vendor Group",
        help="Filter partners by vendor group"
    )

    partner_journal_breakdown = fields.Html(
        string="Partner Ledger",
        compute="_compute_journal_breakdown",
        store=False
    )

    # --------------------------------------------
    # Helpers (Cross-Company Safe Selection)
    # --------------------------------------------
    @api.model
    def _get_vendor_groups(self):
        # Use env.companies.ids (active company scope) with sudo to prevent rule crashes
        allowed_companies = self.env.companies.ids
        if allowed_companies:
            partners = self.env['res.partner'].sudo().search([
                ('vendor_group', '!=', False),
                '|', ('company_id', '=', False), ('company_id', 'in', allowed_companies)
            ])
            groups = sorted(list(set(partners.mapped('vendor_group'))))
            return [(g, g) for g in groups if g]
        return []

    # --------------------------------------------
    # Centralized Data Fetcher (Used by HTML & Excel)
    # --------------------------------------------
    def _get_report_data(self):
        self.ensure_one()
        # Always resolve a valid company ID (selected company OR active session company)
        target_company = self.company_id or self.env.company
        company_id = target_company.id

        AccountMoveLine = self.env['account.move.line'].sudo()

        # 1. Base domain for move lines filtered strictly by target company
        line_domain = [
            ('partner_id', '!=', False),
            ('move_id.state', '=', 'posted'),
            ('company_id', '=', company_id),
            ('account_id.account_type', 'in', ['asset_receivable', 'liability_payable']),
        ]
        if self.partner_id:
            line_domain.append(('partner_id', '=', self.partner_id.id))
        if self.vendor_group:
            line_domain.append(('partner_id.vendor_group', '=', self.vendor_group))
        if self.date_from:
            line_domain.append(('date', '>=', self.date_from))
        if self.date_to:
            line_domain.append(('date', '<=', self.date_to))

        # 2. Partner Domain (Fetch using sudo)
        partner_domain = [
            '&',
            '|', ('customer_rank', '>', 0), ('supplier_rank', '>', 0),
            '|', ('company_id', '=', False), ('company_id', '=', company_id)
        ]
        partners = self.env['res.partner'].sudo().search(partner_domain)

        if self.partner_id:
            partners = partners.filtered(lambda p: p.id == self.partner_id.id)
        if self.vendor_group:
            partners = partners.filtered(lambda p: p.vendor_group == self.vendor_group)

        # Detect account type field (compatibility)
        acct_model = self.env['account.account']
        atype_field = 'account_type' if 'account_type' in acct_model._fields else 'internal_type'
        AR_VALUE = 'asset_receivable' if atype_field == 'account_type' else 'receivable'
        AP_VALUE = 'liability_payable' if atype_field == 'account_type' else 'payable'

        report_data = []
        all_totals = {
            'opening': 0.0,
            'debit': 0.0,
            'credit': 0.0,
            'balance': 0.0,
            'company_name': target_company.sudo().name,
        }

        for partner in partners:
            partner_lines = AccountMoveLine.search(
                line_domain + [('partner_id', '=', partner.id)],
                order='date,id'
            )

            # Opening balance calculation
            opening_balance = 0.0
            opening_debit_sum = 0.0
            opening_credit_sum = 0.0

            if self.date_from:
                base_opening_domain = [
                    ('partner_id', '=', partner.id),
                    ('move_id.state', '=', 'posted'),
                    ('company_id', '=', company_id),
                    ('date', '<', self.date_from),
                ]

                ar_grp = AccountMoveLine.read_group(
                    base_opening_domain + [(f'account_id.{atype_field}', '=', AR_VALUE)],
                    ['debit:sum', 'credit:sum'], []
                )
                ar_d = float((ar_grp[0].get('debit', 0.0) if ar_grp else 0.0) or 0.0)
                ar_c = float((ar_grp[0].get('credit', 0.0) if ar_grp else 0.0) or 0.0)

                ap_grp = AccountMoveLine.read_group(
                    base_opening_domain + [(f'account_id.{atype_field}', '=', AP_VALUE)],
                    ['debit:sum', 'credit:sum'], []
                )
                ap_d = float((ap_grp[0].get('debit', 0.0) if ap_grp else 0.0) or 0.0)
                ap_c = float((ap_grp[0].get('credit', 0.0) if ap_grp else 0.0) or 0.0)

                opening_debit_sum = ar_d + ap_d
                opening_credit_sum = ar_c + ap_c
                opening_balance = (ar_d - ar_c) - (ap_c - ap_d)

            if not partner_lines and not opening_balance:
                continue

            period_total_debit = sum(float(l.debit) for l in partner_lines)
            period_total_credit = sum(float(l.credit) for l in partner_lines)
            period_ar = sum(
                (float(l.debit) - float(l.credit)) for l in partner_lines
                if getattr(l.account_id.sudo(), atype_field) == AR_VALUE
            )
            period_ap = sum(
                (float(l.credit) - float(l.debit)) for l in partner_lines
                if getattr(l.account_id.sudo(), atype_field) == AP_VALUE
            )
            final_balance = opening_balance + (period_ar - period_ap)

            lines_data = []
            running_receivable = 0.0
            running_payable = 0.0

            for line in partner_lines:
                # Wrap relational lookups in sudo() to prevent cross-company blocks
                move = line.move_id.sudo()
                account = line.account_id.sudo()

                debit_val = float(line.debit)
                credit_val = float(line.credit)
                acc_type_val = getattr(account, atype_field)

                if acc_type_val == AR_VALUE:
                    running_receivable += (debit_val - credit_val)
                elif acc_type_val == AP_VALUE:
                    running_payable += (credit_val - debit_val)

                running_balance = opening_balance + (running_receivable - running_payable)

                lines_data.append({
                    'date': line.date,
                    'journal': move.journal_id.code or '',
                    'account': f"{account.code} - {account.name}",
                    'reference': move.name or '',
                    'due_date': line.date_maturity or '',
                    'debit': debit_val,
                    'credit': credit_val,
                    'balance': running_balance,
                })

            report_data.append({
                'partner': partner,
                'opening_balance': opening_balance,
                'opening_debit_sum': opening_debit_sum,
                'opening_credit_sum': opening_credit_sum,
                'period_total_debit': period_total_debit,
                'period_total_credit': period_total_credit,
                'final_balance': final_balance,
                'lines': lines_data,
            })

            all_totals['opening'] += opening_balance
            all_totals['debit'] += period_total_debit
            all_totals['credit'] += period_total_credit
            all_totals['balance'] += final_balance

        return report_data, all_totals

    # --------------------------------------------
    # Compute HTML
    # --------------------------------------------
    @api.depends('date_from', 'date_to', 'partner_id', 'vendor_group', 'company_id')
    def _compute_journal_breakdown(self):
        for rec in self:
            rec._build_html()

    def _build_html(self):
        for rec in self:
            report_data, all_totals = rec._get_report_data()

            html = """
            <h3>Partner Ledger Report</h3>
            <table border='1' cellpadding='3' cellspacing='0'
                style='border-collapse:collapse; font-size:12px; width:100%; margin-bottom:10px;'>
                <tr style='background:#f0f0f0; font-weight:bold;'>
                    <th style='text-align:left;'>Partner</th>
                    <th style='text-align:right;'>Opening Balance</th>
                    <th style='text-align:right;'>Total Debit</th>
                    <th style='text-align:right;'>Total Credit</th>
                    <th style='text-align:right;'>Balance</th>
                </tr>
            """

            for pdata in report_data:
                partner = pdata['partner']
                html += f"""
                <tr>
                    <td style='text-align:left;'>
                        <details>
                            <summary style='cursor:pointer;'>{partner.name}</summary>
                            <div style='margin-top:5px;'>
                                <table border='1' cellpadding='3' cellspacing='0'
                                    style='border-collapse:collapse; font-size:11px; width:100%; margin-top:5px;'>
                                    <tr style='background:#ddd; font-weight:bold;'>
                                        <th>Date</th><th>Journal</th><th>Account</th>
                                        <th>Reference</th><th>Due Date</th>
                                        <th style='text-align:right;'>Debit</th>
                                        <th style='text-align:right;'>Credit</th>
                                        <th style='text-align:right;'>Balance (AR - AP)</th>
                                    </tr>
                                    <tr style='background:#fafafa;'>
                                        <td></td><td></td><td></td><td><i>Initial Balance</i></td><td></td>
                                        <td style='text-align:right;'>{pdata['opening_debit_sum']:,.2f}</td>
                                        <td style='text-align:right;'>{pdata['opening_credit_sum']:,.2f}</td>
                                        <td style='text-align:right;'>{pdata['opening_balance']:,.2f}</td>
                                    </tr>
                """

                for line in pdata['lines']:
                    html += f"""
                                    <tr>
                                        <td>{line['date']}</td>
                                        <td>{line['journal']}</td>
                                        <td>{line['account']}</td>
                                        <td>{line['reference']}</td>
                                        <td>{line['due_date']}</td>
                                        <td style='text-align:right;'>{line['debit']:,.2f}</td>
                                        <td style='text-align:right;'>{line['credit']:,.2f}</td>
                                        <td style='text-align:right;'>{line['balance']:,.2f}</td>
                                    </tr>
                    """

                html += f"""
                                    <tr style='background:#eee; font-weight:bold;'>
                                        <td colspan="5" style='text-align:right;'>Total {partner.name}</td>
                                        <td style='text-align:right;'>{pdata['period_total_debit']:,.2f}</td>
                                        <td style='text-align:right;'>{pdata['period_total_credit']:,.2f}</td>
                                        <td style='text-align:right;'>{pdata['final_balance']:,.2f}</td>
                                    </tr>
                                </table>
                            </div>
                        </details>
                    </td>
                    <td style='text-align:right;'>{pdata['opening_balance']:,.2f}</td>
                    <td style='text-align:right;'>{pdata['period_total_debit']:,.2f}</td>
                    <td style='text-align:right;'>{pdata['period_total_credit']:,.2f}</td>
                    <td style='text-align:right;'>{pdata['final_balance']:,.2f}</td>
                </tr>
                """

            html += f"""
            <tr style='background:#cce5ff; font-weight:bold;'>
                <td style='text-align:right;'>All Partners Total</td>
                <td style='text-align:right;'>{all_totals['opening']:,.2f}</td>
                <td style='text-align:right;'>{all_totals['debit']:,.2f}</td>
                <td style='text-align:right;'>{all_totals['credit']:,.2f}</td>
                <td style='text-align:right;'>{all_totals['balance']:,.2f}</td>
            </tr>
            </table>
            """
            rec.partner_journal_breakdown = html

    # --------------------------------------------
    # Buttons
    # --------------------------------------------
    def action_refresh_current_company(self):
        for rec in self:
            rec.partner_journal_breakdown = False
            rec._build_html()
        return True

    def action_export_xlsx(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/group_party/export_xlsx?record_id={self.id}&ts={fields.Datetime.now().timestamp()}',
            'target': 'self',
        }

    def action_export_totals_xlsx(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/group_party/export_totals_xlsx?record_id={self.id}&ts={fields.Datetime.now().timestamp()}',
            'target': 'self',
        }
