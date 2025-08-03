from odoo import api, models, fields
from collections import defaultdict
from datetime import datetime


class PartnerLedgerGroup(models.Model):
    _name = 'partner.ledger'
    _description = "Partner Ledger Journal Line Breakdown"

    partner_journal_breakdown = fields.Html(string="Partner Journal Breakdown", compute="_compute_journal_breakdown", store=False)

    @api.depends()
    def _compute_journal_breakdown(self):
        AccountMoveLine = self.env['account.move.line'].sudo()

        move_lines = AccountMoveLine.search([
            ('partner_id', '!=', False),
            ('move_id.state', '=', 'posted')
        ], order='date, id')

        # Grouping: Product Group → Partner
        grouped_data = defaultdict(lambda: defaultdict(list))

        for line in move_lines:
            product_group = line.product_id.categ_id.name if line.product_id and line.product_id.categ_id else "Unknown"
            partner = line.partner_id.name or "Unknown"
            grouped_data[product_group][partner].append(line)

        # Render breakdown as HTML table
        for rec in self:
            html = "<h3>Party ledger: Group summary ledger detail</h3>"
            html += "<table border='1' cellpadding='3' cellspacing='0' style='border-collapse: collapse; font-size: 12px;'>"
            html += "<tr><td><strong>Group:</strong></td><td colspan='7'>All</td></tr>"

            # Table headers
            html += (
                "<tr style='background:#ddd;'>"
                "<th>Date</th><th>Product Group</th><th>Partner</th>"
                "<th>Opening Balance</th><th>Amount Dr.</th><th>Amount Cr.</th><th>Balance</th>"
                "</tr>"
            )

            for group, partners in grouped_data.items():
                for partner, lines in partners.items():
                    opening_balance = 0.0
                    balance = 0.0
                    for line in lines:
                        opening_balance += line.debit - line.credit

                    for line in lines:
                        date = line.date.strftime('%-m/%-d/%Y')
                        amount_dr = line.debit
                        amount_cr = line.credit
                        balance += amount_dr - amount_cr

                        html += (
                            f"<tr>"
                            f"<td>{date}</td>"
                            f"<td>{group}</td>"
                            f"<td>{partner}</td>"
                            f"<td>{'{:,.0f}'.format(opening_balance) if isinstance(opening_balance, (int, float)) else ''}</td>"
                            f"<td>{'{:,.0f}'.format(amount_dr)}</td>"
                            f"<td>{'{:,.0f}'.format(amount_cr)}</td>"
                            f"<td>{'{:,.0f}'.format(balance)}</td>"
                            f"</tr>"
                        )
                        opening_balance = ''

            html += "</table>"
            rec.partner_journal_breakdown = html
