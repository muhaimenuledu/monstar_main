from odoo import api, models, fields


class GeneralLedger(models.Model):
    _name = 'general.ledger'
    _description = "GL Customization"

    name = fields.Char(string="GL", required=True)
    journal_items = fields.Html(string="Journal Entry Breakdown by Account", compute="_compute_journal_breakdowns", store=False)

    @api.depends()
    def _compute_journal_breakdowns(self):
        AccountMoveLine = self.env['account.move.line'].sudo()
        Account = self.env['account.account'].sudo()
        all_accounts = Account.search([], order='code')

        # Define fixed widths for columns for alignment (adjust as needed)
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

        for rec in self:
            breakdown = []

            for account in all_accounts:
                move_lines = AccountMoveLine.search([
                    ('account_id', '=', account.id),
                    ('move_id.state', '=', 'posted')
                ], order='date, id')

                if not move_lines:
                    continue

                breakdown.append(f"ACCOUNT_HEADER||Account: {account.code} - {account.name}")

                # Header row (fixed width columns)
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

            # Convert to HTML table like in PartnerLedgerGroup
            html = "<h3>General Ledger - Journal Entry Breakdown by Account</h3>"
            html += "<table border='1' cellpadding='3' cellspacing='0' style='border-collapse: collapse; font-size: 12px; width: 100%;'>"

            for line in breakdown:
                if line.startswith("ACCOUNT_HEADER||"):
                    account_name = line.split("||")[1]
                    html += f"<tr style='background:#a0c4ff;'><td colspan='9'><strong>{account_name}</strong></td></tr>"
                elif line.strip().startswith("|"):
                    columns = [col.strip() for col in line.strip('|').split('|')]
                    tag = "th" if "Date" in columns[1] else "td"  # Header row check based on "Date" in 2nd col
                    row_style = "background:#f1f1f1;" if tag == "th" else ""
                    html += f"<tr style='{row_style}'>" + "".join([f"<{tag}>{c}</{tag}>" for c in columns]) + "</tr>"

            html += "</table>"

            rec.journal_items = html
