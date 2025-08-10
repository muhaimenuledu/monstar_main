from odoo import api, models, fields
from collections import defaultdict
from odoo.http import request

class PartnerLedgerGroup(models.Model):
    _name = 'partner.ledger'
    _description = "Partner Ledger Journal Line Breakdown"

    date_from = fields.Date(string="Start Date")
    date_to = fields.Date(string="End Date")
    product_categ_id = fields.Many2one('product.category', string="Product Category")
    partner_id = fields.Many2one('res.partner', string="Partner")
    partner_journal_breakdown = fields.Html(string="Partner Journal Breakdown", compute="_compute_journal_breakdown", store=False)

    @api.depends('date_from', 'date_to', 'product_categ_id', 'partner_id')
    def _compute_journal_breakdown(self):
        AccountMoveLine = self.env['account.move.line'].sudo()

        for rec in self:
            base_domain = [('partner_id', '!=', False), ('move_id.state', '=', 'posted')]
            if rec.product_categ_id:
                base_domain.append(('product_id.categ_id', '=', rec.product_categ_id.id))
            if rec.partner_id:
                base_domain.append(('partner_id', '=', rec.partner_id.id))

            opening_domain = list(base_domain)
            if rec.date_from:
                opening_domain.append(('date', '<', rec.date_from))

            trx_domain = list(base_domain)
            if rec.date_from:
                trx_domain.append(('date', '>=', rec.date_from))
            if rec.date_to:
                trx_domain.append(('date', '<=', rec.date_to))

            opening_lines = AccountMoveLine.search(opening_domain)
            trx_lines = AccountMoveLine.search(trx_domain)

            grouped_data = defaultdict(lambda: defaultdict(lambda: {
                'opening': 0.0, 'debit': 0.0, 'credit': 0.0
            }))

            for line in opening_lines:
                group = line.product_id.categ_id.name if line.product_id and line.product_id.categ_id else "Unknown"
                partner = line.partner_id.name or "Unknown"
                grouped_data[group][partner]['opening'] += line.debit - line.credit

            for line in trx_lines:
                group = line.product_id.categ_id.name if line.product_id and line.product_id.categ_id else "Unknown"
                partner = line.partner_id.name or "Unknown"
                grouped_data[group][partner]['debit'] += line.debit
                grouped_data[group][partner]['credit'] += line.credit

            base_url = request.httprequest.host_url.rstrip('/')
            full_url = f"{base_url}/odoo/partner-ledger"

            html = (
                "<h3>Party Ledger: Group Summary (One Line Per Partner) "
                "<small style='font-weight:normal;'>"
                f"[<a href='{full_url}' target='_blank'>Open Original Partner Ledger</a>]"
                "</small></h3>"
            )

            for group, partners in grouped_data.items():
                html += f"<h4 style='background:#add8e6;padding:4px;'>{group}</h4>"
                html += "<table border='1' cellpadding='3' cellspacing='0' style='border-collapse: collapse; font-size: 12px; width:100%;'>"
                html += "<tr><td><strong>Group Filter:</strong></td><td colspan='5'>%s</td></tr>" % (
                    rec.product_categ_id.name if rec.product_categ_id else "All"
                )
                if rec.partner_id:
                    html += "<tr><td><strong>Partner Filter:</strong></td><td colspan='5'>%s</td></tr>" % rec.partner_id.name

                html += (
                    "<tr style='background:#ddd;'>"
                    "<th>Partner</th><th>Opening Balance</th>"
                    "<th>Total Debit</th><th>Total Credit</th><th>Closing Balance</th>"
                    "</tr>"
                )

                for partner, values in partners.items():
                    opening = values['opening']
                    debit = values['debit']
                    credit = values['credit']
                    closing = opening + debit - credit

                    html += (
                        f"<tr>"
                        f"<td>{partner}</td>"
                        f"<td>{'{:,.0f}'.format(opening)}</td>"
                        f"<td>{'{:,.0f}'.format(debit)}</td>"
                        f"<td>{'{:,.0f}'.format(credit)}</td>"
                        f"<td>{'{:,.0f}'.format(closing)}</td>"
                        f"</tr>"
                    )

                html += "</table><br>"

            rec.partner_journal_breakdown = html

    def action_export_xlsx(self):
        return {
            'type': 'ir.actions.act_url',
            'url': '/partner_ledger/export_xlsx?record_id=%s' % self.id,
            'target': 'self',
        }
