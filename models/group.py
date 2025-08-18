from odoo import api, models, fields
from collections import defaultdict
from odoo.http import request


class GeneralLedger(models.Model):
    _name = 'group.party'
    _description = "PL Customization"

    date_from = fields.Date(string="Start Date")
    date_to = fields.Date(string="End Date")
    partner_id = fields.Many2one('res.partner', string="Partner")
    vendor_group = fields.Char(string="Vendor Group")  
    partner_journal_breakdown = fields.Html(string="Partner Journal Breakdown", compute="_compute_journal_breakdown", store=False)

    @api.depends('date_from', 'date_to', 'partner_id', 'vendor_group')
    def _compute_journal_breakdown(self):
        AccountMoveLine = self.env['account.move.line'].sudo()

        for rec in self:
            # -----------------------------
            # Base Domain
            # -----------------------------
            base_domain = [('partner_id', '!=', False), ('move_id.state', '=', 'posted')]
            if rec.partner_id:
                base_domain.append(('partner_id', '=', rec.partner_id.id))
            if rec.vendor_group:
                base_domain.append(('partner_id.vendor_group', '=', rec.vendor_group))

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

            # -----------------------------
            # Closing Balance (ignore product filter)
            # -----------------------------
            total_opening = total_debit = total_credit = 0.0
            if rec.partner_id:
                partner_opening_domain = [('partner_id', '=', rec.partner_id.id), ('move_id.state', '=', 'posted')]
                if rec.date_from:
                    partner_opening_domain.append(('date', '<', rec.date_from))
                partner_trx_domain = [('partner_id', '=', rec.partner_id.id), ('move_id.state', '=', 'posted')]
                if rec.date_from:
                    partner_trx_domain.append(('date', '>=', rec.date_from))
                if rec.date_to:
                    partner_trx_domain.append(('date', '<=', rec.date_to))
                if rec.vendor_group:
                    partner_opening_domain.append(('partner_id.vendor_group', '=', rec.vendor_group))
                    partner_trx_domain.append(('partner_id.vendor_group', '=', rec.vendor_group))

                partner_opening_lines = AccountMoveLine.search(partner_opening_domain)
                partner_trx_lines = AccountMoveLine.search(partner_trx_domain)

                for line in partner_opening_lines:
                    total_opening += line.debit - line.credit
                for line in partner_trx_lines:
                    total_debit += line.debit
                    total_credit += line.credit

            partner_closing_balance = total_opening + total_debit - total_credit

            # -----------------------------
            # Group by Partner (no product grouping)
            # -----------------------------
            grouped_data = defaultdict(lambda: {
                'opening': 0.0, 'debit': 0.0, 'credit': 0.0
            })

            for line in opening_lines:
                partner = line.partner_id.name or "Unknown"
                grouped_data[partner]['opening'] += line.debit - line.credit

            for line in trx_lines:
                partner = line.partner_id.name or "Unknown"
                grouped_data[partner]['debit'] += line.debit
                grouped_data[partner]['credit'] += line.credit

            base_url = request.httprequest.host_url.rstrip('/')
            full_url = f"{base_url}/odoo/partner-ledger"

            html = (
                "<h3>Party Ledger: Group Summary (One Line Per Partner) "
                "<small style='font-weight:normal;'>"
                f"[<a href='{full_url}' target='_blank'>Open Original Partner Ledger</a>]"
                "</small></h3>"
            )

            # Show overall partner closing balance at the top
            if rec.partner_id:
                html += (
                    f"<p style='font-size:14px; font-weight:bold; "
                    f"color:#2a2a2a; background:#f0f0f0; padding:6px;'>"
                    f"Total Closing Balance for {rec.partner_id.name}: "
                    f"{'{:,.0f}'.format(partner_closing_balance)}"
                    f"</p><br>"
                )

            html += "<table border='1' cellpadding='3' cellspacing='0' style='border-collapse: collapse; font-size: 12px; width:100%;'>"
            if rec.partner_id:
                html += "<tr><td><strong>Partner Filter:</strong></td><td colspan='5'>%s</td></tr>" % rec.partner_id.name
            if rec.vendor_group:
                html += "<tr><td><strong>Vendor Group Filter:</strong></td><td colspan='5'>%s</td></tr>" % rec.vendor_group

            html += (
                "<tr style='background:#ddd;'>"
                "<th>Partner</th><th>Opening Balance</th>"
                "<th>Total Debit</th><th>Total Credit</th><th>Closing Balance</th>"
                "</tr>"
            )

            for partner, values in grouped_data.items():
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
