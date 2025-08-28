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

    @api.depends('date_from', 'date_to', 'partner_id', 'vendor_group')
    def _compute_journal_breakdown(self):
        self._build_html(company_id=None)

    def _build_html(self, company_id=None):
        AccountMoveLine = self.env['account.move.line'].sudo()
        for rec in self:
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

            partner_domain = ['|', ('customer_rank', '>', 0), ('supplier_rank', '>', 0)]
            if company_id:
                partner_domain.append(('company_id', '=', company_id))
            partners = self.env['res.partner'].search(partner_domain)
            if rec.partner_id:
                partners = partners.filtered(lambda p: p.id == rec.partner_id.id)
            if rec.vendor_group:
                partners = partners.filtered(lambda p: p.vendor_group == rec.vendor_group)

            # Start HTML
            html = """
            <h3>Partner Ledger Report</h3>
            <table border='1' cellpadding='3' cellspacing='0'
                   style='border-collapse:collapse; font-size:12px; width:100%; margin-bottom:10px;'>
                <tr style='background:#f0f0f0; font-weight:bold;'>
                    <th style='text-align:left;'>Partner</th>
                    <th style='text-align:right;'>Opening Balance</th>
                    <th style='text-align:right;'>Total Debit</th>
                    <th style='text-align:right;'>Total Credit</th>
                    <th style='text-align:right;'>Closing Balance</th>
                </tr>
            """

            for partner in partners:
                # Opening balance (all lines BEFORE date_from)
                opening_domain = [
                    ('partner_id', '=', partner.id),
                    ('move_id.state', '=', 'posted'),
                    ('account_id.account_type', 'in', ['asset_receivable', 'liability_payable']),
                ]
                if rec.date_from:
                    opening_domain.append(('date', '<', rec.date_from))
                if company_id:
                    opening_domain.append(('company_id', '=', company_id))

                opening_lines = AccountMoveLine.search(opening_domain)
                opening_receivable = sum(l.debit - l.credit for l in opening_lines if l.account_id.account_type == 'asset_receivable')
                opening_payable = sum(l.credit - l.debit for l in opening_lines if l.account_id.account_type == 'liability_payable')
                opening_balance = opening_receivable - opening_payable

                # Period lines (between date_from and date_to)
                partner_lines = AccountMoveLine.search(
                    line_domain + [('partner_id', '=', partner.id)], order='date,id'
                )
                if not partner_lines and not opening_balance:
                    continue

                total_debit = sum(l.debit for l in partner_lines)
                total_credit = sum(l.credit for l in partner_lines)
                period_balance = sum(l.debit - l.credit for l in partner_lines if l.account_id.account_type == 'asset_receivable') \
                               - sum(l.credit - l.debit for l in partner_lines if l.account_id.account_type == 'liability_payable')

                closing_balance = opening_balance + period_balance

                # Summary row with collapsible details
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
                                        <th style='text-align:right;'>Running Balance</th>
                                    </tr>
                """

                running_balance = opening_balance
                # Show opening balance row
                html += f"""
                                    <tr style="font-style:italic; background:#f9f9f9;">
                                        <td colspan="7">Opening Balance</td>
                                        <td style='text-align:right;'>{opening_balance:,.2f}</td>
                                    </tr>
                """

                for line in partner_lines:
                    debit_val = line.debit
                    credit_val = line.credit
                    if line.account_id.account_type == 'asset_receivable':
                        running_balance += (debit_val - credit_val)
                    elif line.account_id.account_type == 'liability_payable':
                        running_balance += (credit_val - debit_val)

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

                html += """
                                </table>
                            </div>
                        </details>
                    </td>
                    <td style='text-align:right;'>{:,.2f}</td>
                    <td style='text-align:right;'>{:,.2f}</td>
                    <td style='text-align:right;'>{:,.2f}</td>
                    <td style='text-align:right;'>{:,.2f}</td>
                </tr>
                """.format(opening_balance, total_debit, total_credit, closing_balance)

            html += "</table>"
            rec.partner_journal_breakdown = html

    def action_refresh_current_company(self):
        for rec in self:
            rec.partner_journal_breakdown = False
            rec._build_html(company_id=self.env.company.id)
        return True

    def action_export_xlsx(self):
        """Return URL for full XLSX export with details"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/group_party/export_xlsx?record_id={self.id}',
            'target': 'self',
        }

    def action_export_totals_xlsx(self):
        """Return URL for partner totals XLSX (no details)"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/group_party/export_totals_xlsx?record_id={self.id}',
            'target': 'self',
        }
