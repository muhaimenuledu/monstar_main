# -*- coding: utf-8 -*-
from odoo import api, models, fields


class GeneralLedger(models.Model):
    _name = 'group.party'
    _description = "Partner Ledger Custom HTML Report"

    date_from = fields.Date(string="Start Date")
    date_to = fields.Date(string="End Date")
    partner_id = fields.Many2one('res.partner', string="Partner")

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
    # Helpers
    # --------------------------------------------
    @api.model
    def _get_vendor_groups(self):
        self.env.cr.execute("""
            SELECT DISTINCT vendor_group
            FROM res_partner
            WHERE vendor_group IS NOT NULL
            ORDER BY vendor_group
        """)
        results = self.env.cr.fetchall()
        return [(row[0], row[0]) for row in results if row[0]]

    # --------------------------------------------
    # Compute
    # --------------------------------------------
    @api.depends('date_from', 'date_to', 'partner_id', 'vendor_group')
    def _compute_journal_breakdown(self):
        self._build_html(company_id=None)

    # --------------------------------------------
    # Core builder
    # --------------------------------------------
    def _build_html(self, company_id=None):
        AccountMoveLine = self.env['account.move.line'].sudo()

        for rec in self:
            # Base domain for IN-PERIOD lines
            line_domain = [
                ('partner_id', '!=', False),
                ('move_id.state', '=', 'posted'),
                ('account_id.account_type', 'in', ['asset_receivable', 'liability_payable']),
            ]
            if rec.partner_id:
                line_domain.append(('partner_id', '=', rec.partner_id.id))
            if rec.vendor_group:
                line_domain.append(('partner_id.vendor_group', '=', rec.vendor_group))
            if rec.date_from:
                line_domain.append(('date', '>=', rec.date_from))
            if rec.date_to:
                line_domain.append(('date', '<=', rec.date_to))
            if company_id:
                line_domain.append(('company_id', '=', company_id))

            # Candidate partners (filtered by activity later)
            partner_domain = ['|', ('customer_rank', '>', 0), ('supplier_rank', '>', 0)]
            if company_id:
                partner_domain.append(('company_id', '=', company_id))
            partners = self.env['res.partner'].search(partner_domain)
            if rec.partner_id:
                partners = partners.filtered(lambda p: p.id == rec.partner_id.id)
            if rec.vendor_group:
                partners = partners.filtered(lambda p: p.vendor_group == rec.vendor_group)

            # Detect account type field (compatibility)
            acct_model = self.env['account.account']
            atype_field = 'account_type' if 'account_type' in acct_model._fields else 'internal_type'
            AR_VALUE = 'asset_receivable' if atype_field == 'account_type' else 'receivable'
            AP_VALUE = 'liability_payable' if atype_field == 'account_type' else 'payable'

            # HTML wrapper
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

            # Totals across all partners
            all_total_opening = 0.0
            all_total_debit = 0.0
            all_total_credit = 0.0
            all_final_balance = 0.0

            for partner in partners:
                # IN-PERIOD lines
                partner_lines = AccountMoveLine.search(
                    line_domain + [('partner_id', '=', partner.id)],
                    order='date,id'
                )

                # ---------------- Opening Balance ----------------
                opening_balance = 0.0
                opening_debit_sum = 0.0
                opening_credit_sum = 0.0
                if rec.date_from:
                    base_opening_domain = [
                        ('partner_id', '=', partner.id),
                        ('move_id.state', '=', 'posted'),
                        ('date', '<', rec.date_from),
                    ]
                    if company_id:
                        base_opening_domain.append(('company_id', '=', company_id))

                    # Receivable
                    ar_grp = AccountMoveLine.read_group(
                        base_opening_domain + [(f'account_id.{atype_field}', '=', AR_VALUE)],
                        ['debit:sum', 'credit:sum'], []
                    )
                    ar_d = float((ar_grp[0].get('debit', 0.0) if ar_grp else 0.0) or 0.0)
                    ar_c = float((ar_grp[0].get('credit', 0.0) if ar_grp else 0.0) or 0.0)
                    opening_ar = ar_d - ar_c

                    # Payable
                    ap_grp = AccountMoveLine.read_group(
                        base_opening_domain + [(f'account_id.{atype_field}', '=', AP_VALUE)],
                        ['debit:sum', 'credit:sum'], []
                    )
                    ap_d = float((ap_grp[0].get('debit', 0.0) if ap_grp else 0.0) or 0.0)
                    ap_c = float((ap_grp[0].get('credit', 0.0) if ap_grp else 0.0) or 0.0)
                    opening_ap = ap_c - ap_d

                    opening_debit_sum = ar_d + ap_d
                    opening_credit_sum = ar_c + ap_c
                    opening_balance = opening_ar - opening_ap
                # --------------------------------------------------

                # Skip partner if no opening balance and no lines
                if not partner_lines and not opening_balance:
                    continue

                # Period totals
                period_total_debit = sum(float(l.debit) for l in partner_lines)
                period_total_credit = sum(float(l.credit) for l in partner_lines)
                period_ar = sum(
                    (float(l.debit) - float(l.credit)) for l in partner_lines
                    if getattr(l.account_id, atype_field) == AR_VALUE
                )
                period_ap = sum(
                    (float(l.credit) - float(l.debit)) for l in partner_lines
                    if getattr(l.account_id, atype_field) == AP_VALUE
                )
                period_net = period_ar - period_ap

                # Final balance
                final_balance = opening_balance + period_net

                # Update global totals
                all_total_opening += opening_balance
                all_total_debit += period_total_debit
                all_total_credit += period_total_credit
                all_final_balance += final_balance

                # -------- Partner row with collapse/expand details --------
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
                                        <td style='text-align:right;'>{opening_debit_sum:,.2f}</td>
                                        <td style='text-align:right;'>{opening_credit_sum:,.2f}</td>
                                        <td style='text-align:right;'>{opening_balance:,.2f}</td>
                                    </tr>
                """

                running_receivable = 0.0
                running_payable = 0.0
                for line in partner_lines:
                    debit_val = float(line.debit)
                    credit_val = float(line.credit)
                    acc_type_val = getattr(line.account_id, atype_field)

                    if acc_type_val == AR_VALUE:
                        running_receivable += (debit_val - credit_val)
                    elif acc_type_val == AP_VALUE:
                        running_payable += (credit_val - debit_val)

                    running_balance = opening_balance + (running_receivable - running_payable)

                    html += f"""
                                    <tr>
                                        <td>{line.date}</td>
                                        <td>{line.move_id.journal_id.code}</td>
                                        <td>{line.account_id.code} - {line.account_id.name}</td>
                                        <td>{line.move_id.name or ''}</td>
                                        <td>{line.date_maturity or ''}</td>
                                        <td style='text-align:right;'>{debit_val:,.2f}</td>
                                        <td style='text-align:right;'>{credit_val:,.2f}</td>
                                        <td style='text-align:right;'>{running_balance:,.2f}</td>
                                    </tr>
                    """

                html += f"""
                                    <tr style='background:#eee; font-weight:bold;'>
                                        <td colspan="5" style='text-align:right;'>Total {partner.name}</td>
                                        <td style='text-align:right;'>{period_total_debit:,.2f}</td>
                                        <td style='text-align:right;'>{period_total_credit:,.2f}</td>
                                        <td style='text-align:right;'>{final_balance:,.2f}</td>
                                    </tr>
                                </table>
                            </div>
                        </details>
                    </td>
                    <td style='text-align:right;'>{opening_balance:,.2f}</td>
                    <td style='text-align:right;'>{period_total_debit:,.2f}</td>
                    <td style='text-align:right;'>{period_total_credit:,.2f}</td>
                    <td style='text-align:right;'>{final_balance:,.2f}</td>
                </tr>
                """

            # ===== Global Totals Row =====
            html += f"""
            <tr style='background:#cce5ff; font-weight:bold;'>
                <td style='text-align:right;'>All Partners Total</td>
                <td style='text-align:right;'>{all_total_opening:,.2f}</td>
                <td style='text-align:right;'>{all_total_debit:,.2f}</td>
                <td style='text-align:right;'>{all_total_credit:,.2f}</td>
                <td style='text-align:right;'>{all_final_balance:,.2f}</td>
            </tr>
            """

            html += "</table>"
            rec.partner_journal_breakdown = html

    # --------------------------------------------
    # Buttons
    # --------------------------------------------
    def action_refresh_current_company(self):
        for rec in self:
            rec.partner_journal_breakdown = False
            rec._build_html(company_id=self.env.company.id)
        return True

    def action_export_xlsx(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/group_party/export_xlsx?record_id={self.id}',
            'target': 'self',
        }

    def action_export_totals_xlsx(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/group_party/export_totals_xlsx?record_id={self.id}',
            'target': 'self',
        }
