from odoo import api, models, fields


class GeneralLedger(models.Model):
    _name = 'group.party'
    _description = "Partner Ledger Custom HTML Report"

    date_from = fields.Date(string="Start Date")
    date_to = fields.Date(string="End Date")
    partner_id = fields.Many2one('res.partner', string="Partner")
    vendor_group = fields.Char(string="Vendor Group")
    partner_journal_breakdown = fields.Html(
        string="Partner Ledger",
        compute="_compute_journal_breakdown",
        store=False
    )

    @api.depends('date_from', 'date_to', 'partner_id', 'vendor_group')
    def _compute_journal_breakdown(self):
        AccountMoveLine = self.env['account.move.line'].sudo()

        for rec in self:
            domain = [
                ('partner_id', '!=', False),
                ('move_id.state', '=', 'posted'),
                ('account_id.account_type', 'in', ['asset_receivable', 'liability_payable']),
            ]
            if rec.partner_id:
                domain.append(('partner_id', '=', rec.partner_id.id))
            if rec.vendor_group:
                domain.append(('partner_id.vendor_group', '=', rec.vendor_group))
            if rec.date_from:
                domain.append(('date', '>=', rec.date_from))
            if rec.date_to:
                domain.append(('date', '<=', rec.date_to))

            partners = self.env['res.partner'].browse(
                AccountMoveLine.search(domain).mapped('partner_id').ids
            )

            html = "<h3>Partner Ledger Report (Receivables - Payables)</h3>"
            if rec.partner_id:
                html += f"<p><strong>Partner Filter:</strong> {rec.partner_id.name}</p>"
            if rec.vendor_group:
                html += f"<p><strong>Vendor Group Filter:</strong> {rec.vendor_group}</p>"

            for partner in partners:
                partner_lines = AccountMoveLine.search(
                    domain + [('partner_id', '=', partner.id)], order='date,id'
                )

                html += f"<h4>Partner: {partner.name}</h4>"
                html += "<table border='1' cellpadding='3' cellspacing='0' style='border-collapse: collapse; font-size:12px; width:100%;'>"
                html += (
                    "<tr style='background:#ddd;'>"
                    "<th>Date</th><th>Journal</th><th>Account</th><th>Reference</th>"
                    "<th>Due Date</th><th>Debit</th><th>Credit</th><th>Balance (AR - AP)</th>"
                    "</tr>"
                )

                running_receivable = 0.0
                running_payable = 0.0
                total_debit = 0.0
                total_credit = 0.0

                for line in partner_lines:
                    account_type = line.account_id.account_type
                    debit_val = line.debit
                    credit_val = line.credit

                    if account_type == 'asset_receivable':
                        running_receivable += (debit_val - credit_val)
                    elif account_type == 'liability_payable':
                        running_payable += (credit_val - debit_val)

                    total_debit += debit_val
                    total_credit += credit_val

                    running_balance = running_receivable - running_payable  # AR - AP

                    html += "<tr>"
                    html += f"<td>{line.date}</td>"
                    html += f"<td>{line.move_id.journal_id.code}</td>"
                    html += f"<td>{line.account_id.code} - {line.account_id.name}</td>"
                    html += f"<td>{line.move_id.name or ''}</td>"
                    html += f"<td>{line.date_maturity or ''}</td>"
                    html += f"<td>{debit_val:,.2f}</td>"
                    html += f"<td>{credit_val:,.2f}</td>"
                    html += f"<td>{running_balance:,.2f}</td>"
                    html += "</tr>"

                # Totals
                final_balance = running_receivable - running_payable
                html += (
                    f"<tr style='font-weight:bold; background:#eee;'>"
                    f"<td colspan='5'>Total {partner.name}</td>"
                    f"<td>{total_debit:,.2f}</td>"
                    f"<td>{total_credit:,.2f}</td>"
                    f"<td>{final_balance:,.2f}</td>"
                    "</tr>"
                )
                html += "</table><br>"

            rec.partner_journal_breakdown = html
