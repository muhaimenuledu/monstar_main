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
        groups = self.env['res.partner'].sudo().search_read(
            [('vendor_group', '!=', False)], ['vendor_group']
        )
        return [(g['vendor_group'], g['vendor_group']) for g in groups]

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

            html = "<h3>Partner Ledger Report</h3>"
            if company_id:
                html += f"<p><strong>Company Filter:</strong> {self.env['res.company'].browse(company_id).name}</p>"
            if rec.partner_id:
                html += f"<p><strong>Partner Filter:</strong> {rec.partner_id.name}</p>"
            if rec.vendor_group:
                html += f"<p><strong>Vendor Group Filter:</strong> {rec.vendor_group}</p>"

            if not partners:
                html += "<p><em>No partners found for this company.</em></p>"

            for partner in partners:
                partner_lines = AccountMoveLine.search(
                    line_domain + [('partner_id', '=', partner.id)], order='date,id'
                )
                if not partner_lines:
                    continue

                total_debit = sum(l.debit for l in partner_lines)
                total_credit = sum(l.credit for l in partner_lines)
                running_receivable = sum(l.debit - l.credit for l in partner_lines if l.account_id.account_type == 'asset_receivable')
                running_payable = sum(l.credit - l.debit for l in partner_lines if l.account_id.account_type == 'liability_payable')
                final_balance = running_receivable - running_payable

                # Partner totals outside details
                html += f"""
                <table border='1' cellpadding='3' cellspacing='0' style='border-collapse: collapse; font-size:12px; width:100%; margin-bottom:2px;'>
                    <tr style='background:#f0f0f0; font-weight:bold;'>
                        <td>Partner: {partner.name}</td>
                        <td>Total Debit: {total_debit:,.2f}</td>
                        <td>Total Credit: {total_credit:,.2f}</td>
                        <td>Balance: {final_balance:,.2f}</td>
                    </tr>
                </table>
                """

                # Collapsible details
                html += f"<details style='margin-bottom:10px;'><summary style='font-weight:bold; font-size:13px; cursor:pointer;'>Show/Hide Details</summary>"
                html += """
                <table border='1' cellpadding='3' cellspacing='0' style='border-collapse: collapse; font-size:12px; width:100%; margin-top:5px;'>
                    <tr style='background:#ddd;'>
                        <th>Date</th><th>Journal</th><th>Account</th><th>Reference</th>
                        <th>Due Date</th><th>Debit</th><th>Credit</th><th>Balance (AR - AP)</th>
                    </tr>
                """
                running_receivable = 0.0
                running_payable = 0.0
                for line in partner_lines:
                    debit_val = line.debit
                    credit_val = line.credit
                    account_type = line.account_id.account_type
                    if account_type == 'asset_receivable':
                        running_receivable += (debit_val - credit_val)
                    elif account_type == 'liability_payable':
                        running_payable += (credit_val - debit_val)
                    running_balance = running_receivable - running_payable
                    html += f"""
                        <tr>
                            <td>{line.date}</td>
                            <td>{line.move_id.journal_id.code}</td>
                            <td>{line.account_id.code} - {line.account_id.name}</td>
                            <td>{line.move_id.name or ''}</td>
                            <td>{line.date_maturity or ''}</td>
                            <td>{debit_val:,.2f}</td>
                            <td>{credit_val:,.2f}</td>
                            <td>{running_balance:,.2f}</td>
                        </tr>
                    """
                html += "</table></details><br>"

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
