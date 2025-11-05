from odoo import api, models, fields


class PartnerLedgerGroup(models.Model):
    _name = 'partner.ledger.group'
    _description = "Partner Ledger Journal Line Breakdown"

    date_from = fields.Date(string="Start Date")
    date_to = fields.Date(string="End Date")
    partner_id = fields.Many2one("res.partner", string="Partner")
    partner_journal_breakdown = fields.Html(
        string="Partner Journal Breakdown",
        compute="_compute_journal_breakdown",
        store=False,
    )

    @api.depends('date_from', 'date_to', 'partner_id')
    def _compute_journal_breakdown(self):
        AccountMoveLine = self.env['account.move.line'].sudo()
        AccountAccount = self.env['account.account'].sudo()

        for rec in self:
            domain = [
                ('partner_id', '!=', False),
                ('move_id.state', '=', 'posted'),
                ('product_id', '!=', False),  # ✅ Added: Only include product lines
            ]

            if rec.date_from:
                domain.append(('date', '>=', rec.date_from))
            if rec.date_to:
                domain.append(('date', '<=', rec.date_to))
            if rec.partner_id:
                domain.append(('partner_id', '=', rec.partner_id.id))

            move_lines = AccountMoveLine.search(domain, order='date, id')

            breakdown = []
            lines_by_partner = {}

            for line in move_lines:
                partner = line.partner_id
                lines_by_partner.setdefault(partner, []).append(line)

            widths = {
                "date": 14,
                "ref": 22,
                "label": 28,
                "group": 28,
                "product_name": 28,
                "unit_price": 15,
                "account_dr": 30,
                "account_cr": 30,
                "amount_dr": 15,
                "amount_cr": 15,
            }

            for partner, lines in lines_by_partner.items():
                breakdown.append(f"PARTNER_HEADER||Party: {partner.name}")
                header = "| {date} | {ref} | {label} | {group} | {product_name} | {unit_price} | {account_dr} | {account_cr} | {amount_dr} | {amount_cr} |".format(
                    date="Date".center(widths["date"]),
                    ref="Ref".center(widths["ref"]),
                    label="Label".center(widths["label"]),
                    group="Product Group".center(widths["group"]),
                    product_name="Product".center(widths["product_name"]),
                    unit_price="Unit Price".center(widths["unit_price"]),
                    account_dr="Account (DR.)".center(widths["account_dr"]),
                    account_cr="Account (CR.)".center(widths["account_cr"]),
                    amount_dr="Amount Dr.".center(widths["amount_dr"]),
                    amount_cr="Amount Cr.".center(widths["amount_cr"]),
                )
                breakdown.append(header)

                for line in lines:
                    move = line.move_id

                    label = (line.name or move.name or "Unavailable")[:widths["label"]]
                    ref = (move.ref or move.name or "Unavailable")[:widths["ref"]]
                    product_group = (line.product_id.categ_id.name if line.product_id and line.product_id.categ_id else "Unavailable")[:widths["group"]]
                    product_name = (line.product_id.display_name if line.product_id else "Unavailable")[:widths["product_name"]]
                    account_dr = f"{line.account_id.code} - {line.account_id.name}" if line.debit else "Unavailable"
                    account_cr = f"{line.account_id.code} - {line.account_id.name}" if line.credit else "Unavailable"

                    unit_price = 0.0
                    if line.quantity:
                        unit_price = (line.debit or line.credit) / line.quantity

                    amount_dr = line.debit or 0.0
                    amount_cr = line.credit or 0.0

                    row = "| {date} | {ref} | {label} | {group} | {product_name} | {unit_price} | {account_dr} | {account_cr} | {amount_dr} | {amount_cr} |".format(
                        date=str(line.date)[:widths["date"]].ljust(widths["date"]),
                        ref=ref[:widths["ref"]].ljust(widths["ref"]),
                        label=label[:widths["label"]].ljust(widths["label"]),
                        group=product_group[:widths["group"]].ljust(widths["group"]),
                        product_name=product_name[:widths["product_name"]].ljust(widths["product_name"]),
                        unit_price="{:,.2f}".format(unit_price).rjust(widths["unit_price"]),
                        account_dr=account_dr[:widths["account_dr"]].ljust(widths["account_dr"]),
                        account_cr=account_cr[:widths["account_cr"]].ljust(widths["account_cr"]),
                        amount_dr="{:,.2f}".format(amount_dr).rjust(widths["amount_dr"]),
                        amount_cr="{:,.2f}".format(amount_cr).rjust(widths["amount_cr"]),
                    )
                    breakdown.append(row)

                # === Calculate Current Balance for Partner ===
                payable_receivable_accounts = AccountAccount.search([
                    ('account_type', 'in', ['asset_receivable', 'liability_payable'])
                ])
                partner_lines = AccountMoveLine.read_group(
                    domain=[
                        ('partner_id', '=', partner.id),
                        ('account_id', 'in', payable_receivable_accounts.ids),
                        ('move_id.state', '=', 'posted')
                    ],
                    fields=['debit', 'credit'],
                    groupby=[]
                )
                balance = 0.0
                if partner_lines:
                    totals = partner_lines[0]
                    balance = (totals.get('debit', 0.0) - totals.get('credit', 0.0))

                summary_row = f"| {'':{widths['date']}} | {'':{widths['ref']}} | {'':{widths['label']}} | {'':{widths['group']}} | {'':{widths['product_name']}} | {'':{widths['unit_price']}} | {'':{widths['account_dr']}} | {'':{widths['account_cr']}} | {'':{widths['amount_dr']}} | {'Balance: ' + '{:,.2f}'.format(balance):{widths['amount_cr']}} |"
                breakdown.append("SUMMARY_ROW||" + summary_row)

            html = "<h3>Partner Ledger Journal Line Breakdown (Product Lines Only)</h3>"
            html += "<table border='1' cellpadding='3' cellspacing='0' style='border-collapse: collapse; font-size: 12px;'>"

            for line in breakdown:
                if line.startswith("PARTNER_HEADER||"):
                    partner_name = line.split("||")[1]
                    html += f"<tr style='background:#a0c4ff;'><td colspan='10'><strong>{partner_name}</strong></td></tr>"
                elif line.startswith("SUMMARY_ROW||"):
                    row = line.split("||")[1]
                    columns = [col.strip() for col in row.strip('|').split('|')]
                    html += "<tr style='background:#d3f8d3; font-weight:bold;'>" + "".join([f"<td>{c}</td>" for c in columns]) + "</tr>"
                elif line.strip().startswith("|"):
                    columns = [col.strip() for col in line.strip('|').split('|')]
                    tag = "th" if "Date" in columns[0] else "td"
                    row_style = "background:#f1f1f1;" if tag == "th" else ""
                    html += f"<tr style='{row_style}'>" + "".join([f"<{tag}>{c}</{tag}>" for c in columns]) + "</tr>"

            html += "</table>"
            rec.partner_journal_breakdown = html

    def action_export_xlsx(self):
        return {
            'type': 'ir.actions.act_url',
            'url': '/partner_ledger_group/export_xlsx?record_id=%s' % self.id,
            'target': 'self',
        }
