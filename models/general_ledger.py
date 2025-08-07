from odoo import api, models, fields


class GeneralLedger(models.Model):
    _name = 'general.ledger'
    _description = "GL Customization"

    # name = fields.Char(string="GL", required=True)
    date_from = fields.Date(string="Start Date")
    date_to = fields.Date(string="End Date")
    account_id = fields.Many2one('account.account', string="Filter by Account")

    journal_items = fields.Html(string="Journal Entry Breakdown by Account", compute="_compute_journal_breakdowns", store=False)

    @api.depends('date_from', 'date_to', 'account_id')
    def _compute_journal_breakdowns(self):
        AccountMoveLine = self.env['account.move.line'].sudo()
        Account = self.env['account.account'].sudo()

        for rec in self:
            # Filter accounts
            accounts = Account.search([('id', '=', rec.account_id.id)]) if rec.account_id else Account.search([], order='code')
            widths = {
                "account": 30,
                "date": 14,
                "ref": 22,
                "label": 28,
                "group": 28,
                "counter": 40,
                "amount_dr": 15,
                "amount_cr": 15,
                "balance": 15,
            }

            breakdown = []

            for account in accounts:
                # Build domain with filters
                domain = [('account_id', '=', account.id), ('move_id.state', '=', 'posted')]
                if rec.date_from:
                    domain.append(('date', '>=', rec.date_from))
                if rec.date_to:
                    domain.append(('date', '<=', rec.date_to))

                move_lines = AccountMoveLine.search(domain, order='date, id')

                if not move_lines:
                    continue

                breakdown.append(f"ACCOUNT_HEADER||Account: {account.code} - {account.name}")

                header = "| {account} | {date} | {ref} | {label} | {group} | {counter} | {amount_dr} | {amount_cr} | {balance} |".format(
                    account="Account".center(widths["account"]),
                    date="Date".center(widths["date"]),
                    ref="V. No./Ref".center(widths["ref"]),
                    label="Label".center(widths["label"]),
                    group="Product Group".center(widths["group"]),
                    counter="Counter Account".center(widths["counter"]),
                    amount_dr="Amount Dr.".center(widths["amount_dr"]),
                    amount_cr="Amount Cr.".center(widths["amount_cr"]),
                    balance="Balance".center(widths["balance"]),
                )
                breakdown.append(header)

                balance = 0.0

                for line in move_lines:
                    move = line.move_id
                    label = (line.name or move.name or "Unavailable")[:widths["label"]]
                    ref = (move.ref or move.name or "Unavailable")[:widths["ref"]]
                    product_group = (line.product_id.categ_id.name if line.product_id and line.product_id.categ_id else "Unavailable")[:widths["group"]]
                    counter_accounts = line.move_id.line_ids.filtered(lambda l: l != line and l.account_id != line.account_id)
                    counter = ', '.join(set(f"{l.account_id.code} - {l.account_id.name}" for l in counter_accounts))
                    counter = (counter or "Unavailable")[:widths["counter"]]

                    amount_dr = line.debit or 0.0
                    amount_cr = line.credit or 0.0
                    balance += amount_dr - amount_cr

                    row = "| {account} | {date} | {ref} | {label} | {group} | {counter} | {amount_dr} | {amount_cr} | {balance} |".format(
                        account=f"{account.code} - {account.name}"[:widths["account"]].ljust(widths["account"]),
                        date=str(line.date)[:widths["date"]].ljust(widths["date"]),
                        ref=ref.ljust(widths["ref"]),
                        label=label.ljust(widths["label"]),
                        group=product_group.ljust(widths["group"]),
                        counter=counter.ljust(widths["counter"]),
                        amount_dr="{:,.2f}".format(amount_dr).rjust(widths["amount_dr"]),
                        amount_cr="{:,.2f}".format(amount_cr).rjust(widths["amount_cr"]),
                        balance="{:,.2f}".format(balance).rjust(widths["balance"]),
                    )
                    breakdown.append(row)

            # Convert breakdown to HTML
            html = "<h3>General Ledger - Journal Entry Breakdown by Account</h3>"
            html += "<table border='1' cellpadding='3' cellspacing='0' style='border-collapse: collapse; font-size: 12px; width: 100%;'>"

            for line in breakdown:
                if line.startswith("ACCOUNT_HEADER||"):
                    account_name = line.split("||")[1]
                    html += f"<tr style='background:#a0c4ff;'><td colspan='9'><strong>{account_name}</strong></td></tr>"
                elif line.strip().startswith("|"):
                    columns = [col.strip() for col in line.strip('|').split('|')]
                    tag = "th" if "Date" in columns[1] else "td"
                    row_style = "background:#f1f1f1;" if tag == "th" else ""
                    html += f"<tr style='{row_style}'>" + "".join([f"<{tag}>{c}</{tag}>" for c in columns]) + "</tr>"

            html += "</table>"
            rec.journal_items = html
