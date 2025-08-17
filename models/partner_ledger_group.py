from odoo import api, models, fields


class PartnerLedgerGroup(models.Model):
    _name = 'partner.ledger.group'
    _description = "Partner Ledger Journal Line Breakdown"

    date_from = fields.Date(string="Start Date")
    date_to = fields.Date(string="End Date")
    partner_id = fields.Many2one("res.partner", string="Partner")  # NEW FIELD
    partner_journal_breakdown = fields.Html(string="Partner Journal Breakdown", compute="_compute_journal_breakdown", store=False)

    @api.depends('date_from', 'date_to', 'partner_id')
    def _compute_journal_breakdown(self):
        AccountMoveLine = self.env['account.move.line'].sudo()

        for rec in self:
            domain = [('partner_id', '!=', False), ('move_id.state', '=', 'posted')]

            if rec.date_from:
                domain.append(('date', '>=', rec.date_from))
            if rec.date_to:
                domain.append(('date', '<=', rec.date_to))
            if rec.partner_id:  # NEW CONDITION
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
                "unit_price": 15,   # NEW COLUMN WIDTH
                "account_dr": 30,
                "account_cr": 30,
                "amount_dr": 15,
                "amount_cr": 15,
                "balance": 15,
            }

            for partner, lines in lines_by_partner.items():
                balance = 0.0
                breakdown.append(f"PARTNER_HEADER||Party: {partner.name}")
                header = "| {date} | {ref} | {label} | {group} | {unit_price} | {account_dr} | {account_cr} | {amount_dr} | {amount_cr} | {balance} |".format(
                    date="Date".center(widths["date"]),
                    ref="Ref".center(widths["ref"]),
                    label="Label".center(widths["label"]),
                    group="Product Group".center(widths["group"]),
                    unit_price="Unit Price".center(widths["unit_price"]),  # HEADER FOR UNIT PRICE
                    account_dr="Account (DR.)".center(widths["account_dr"]),
                    account_cr="Account (CR.)".center(widths["account_cr"]),
                    amount_dr="Amount Dr.".center(widths["amount_dr"]),
                    amount_cr="Amount Cr.".center(widths["amount_cr"]),
                    balance="Balance".center(widths["balance"]),
                )
                breakdown.append(header)

                for line in lines:
                    move = line.move_id

                    label = (line.name or move.name or "Unavailable")[:widths["label"]]
                    ref = (move.ref or move.name or "Unavailable")[:widths["ref"]]
                    product_group = (line.product_id.categ_id.name if line.product_id and line.product_id.categ_id else "Unavailable")[:widths["group"]]
                    account_dr = f"{line.account_id.code} - {line.account_id.name}" if line.debit else "Unavailable"
                    account_cr = f"{line.account_id.code} - {line.account_id.name}" if line.credit else "Unavailable"

                    # NEW: Unit Price Calculation
                    unit_price = 0.0
                    if line.quantity:
                        unit_price = (line.debit or line.credit) / line.quantity

                    amount_dr = line.debit or 0.0
                    amount_cr = line.credit or 0.0
                    balance += amount_dr - amount_cr

                    row = "| {date} | {ref} | {label} | {group} | {unit_price} | {account_dr} | {account_cr} | {amount_dr} | {amount_cr} | {balance} |".format(
                        date=str(line.date)[:widths["date"]].ljust(widths["date"]),
                        ref=ref[:widths["ref"]].ljust(widths["ref"]),
                        label=label[:widths["label"]].ljust(widths["label"]),
                        group=product_group[:widths["group"]].ljust(widths["group"]),
                        unit_price="{:,.2f}".format(unit_price).rjust(widths["unit_price"]),  # DISPLAY UNIT PRICE
                        account_dr=account_dr[:widths["account_dr"]].ljust(widths["account_dr"]),
                        account_cr=account_cr[:widths["account_cr"]].ljust(widths["account_cr"]),
                        amount_dr="{:,.2f}".format(amount_dr).rjust(widths["amount_dr"]),
                        amount_cr="{:,.2f}".format(amount_cr).rjust(widths["amount_cr"]),
                        balance="{:,.2f}".format(balance).rjust(widths["balance"]),
                    )
                    breakdown.append(row)

            html = "<h3>Partner Ledger Journal Line Breakdown</h3>"
            html += "<table border='1' cellpadding='3' cellspacing='0' style='border-collapse: collapse; font-size: 12px;'>"

            for line in breakdown:
                if line.startswith("PARTNER_HEADER||"):
                    partner_name = line.split("||")[1]
                    html += f"<tr style='background:#a0c4ff;'><td colspan='10'><strong>{partner_name}</strong></td></tr>"  # colspan increased
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
