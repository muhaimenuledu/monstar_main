from odoo import api, fields, models


class GeneralLedger(models.Model):
    _name = 'general.ledger'
    _description = "GL Customization"

    date_from = fields.Date(string="Start Date")
    date_to = fields.Date(string="End Date")
    account_id = fields.Many2one('account.account', string="Filter by Account")
    partner_id = fields.Many2one('res.partner', string="Filter by Partner")

    journal_items = fields.Html(
        string="Journal Entry Breakdown by Account",
        compute="_compute_journal_breakdowns",
        store=False,
    )

    @api.depends('date_from', 'date_to', 'account_id', 'partner_id')
    def _compute_journal_breakdowns(self):
        AccountMoveLine = self.env['account.move.line'].sudo()
        Account = self.env['account.account'].sudo()

        for rec in self:
            accounts = (
                Account.search([('id', '=', rec.account_id.id)])
                if rec.account_id
                else Account.search([], order='code')
            )

            widths = {
                "account": 30,
                "date": 14,
                "ref": 22,
                "label": 28,
                "group": 28,
                "partner": 28,
                "counter": 40,
                "amount_dr": 15,
                "amount_cr": 15,
                "balance": 15,
            }

            breakdown = []

            for account in accounts:
                # ---------------------------------------------------------
                # 1) Base domain and opening balance
                # ---------------------------------------------------------
                base_domain = [
                    ('account_id', '=', account.id),
                    ('move_id.state', '=', 'posted'),
                ]
                if rec.partner_id:
                    base_domain.append(('partner_id', '=', rec.partner_id.id))

                # Opening balance: all entries before date_from, else 0
                opening_balance = 0.0
                if rec.date_from:
                    opening_domain = base_domain + [('date', '<', rec.date_from)]
                    opening_lines = AccountMoveLine.search(opening_domain)
                    for ol in opening_lines:
                        opening_balance += (ol.debit or 0.0) - (ol.credit or 0.0)

                # ---------------------------------------------------------
                # 2) Period transactions domain (the rows you already show)
                # ---------------------------------------------------------
                period_domain = list(base_domain)
                if rec.date_from:
                    period_domain.append(('date', '>=', rec.date_from))
                if rec.date_to:
                    period_domain.append(('date', '<=', rec.date_to))

                move_lines = AccountMoveLine.search(period_domain, order='date, id')

                # If no period moves and no date filter at all → keep old behavior: skip
                if not move_lines and not (rec.date_from or rec.date_to):
                    continue

                # ---------------------------------------------------------
                # 3) Add account header + table header (always)
                # ---------------------------------------------------------
                breakdown.append(
                    f"ACCOUNT_HEADER||Account: {account.code} - {account.name}"
                )

                header = "| {account} | {date} | {ref} | {label} | {group} | {partner} | {counter} | {amount_dr} | {amount_cr} | {balance} |".format(
                    account="Account".center(widths["account"]),
                    date="Date".center(widths["date"]),
                    ref="V. No./Ref".center(widths["ref"]),
                    label="Label".center(widths["label"]),
                    group="Product Group".center(widths["group"]),
                    partner="Partner".center(widths["partner"]),
                    counter="Counter Account".center(widths["counter"]),
                    amount_dr="Amount Dr.".center(widths["amount_dr"]),
                    amount_cr="Amount Cr.".center(widths["amount_cr"]),
                    balance="Balance".center(widths["balance"]),
                )
                breakdown.append(header)

                # ---------------------------------------------------------
                # 4) Detail rows for the period (unchanged logic)
                #     - "balance" here is PERIOD balance only.
                # ---------------------------------------------------------
                period_balance = 0.0

                for line in move_lines:
                    move = line.move_id
                    label = (line.name or move.name or "Unavailable")[
                        :widths["label"]
                    ]
                    ref = (move.ref or move.name or "Unavailable")[:widths["ref"]]
                    product_group = (
                        line.product_id.categ_id.name
                        if line.product_id and line.product_id.categ_id
                        else "Unavailable"
                    )[:widths["group"]]
                    partner_name = (line.partner_id.name or "Unavailable")[
                        :widths["partner"]
                    ]

                    counter_accounts = line.move_id.line_ids.filtered(
                        lambda l: l != line and l.account_id != line.account_id
                    )
                    counter = ", ".join(
                        set(
                            f"{l.account_id.code} - {l.account_id.name}"
                            for l in counter_accounts
                        )
                    )
                    counter = (counter or "Unavailable")[:widths["counter"]]

                    amount_dr = line.debit or 0.0
                    amount_cr = line.credit or 0.0
                    period_balance += amount_dr - amount_cr

                    row = "| {account} | {date} | {ref} | {label} | {group} | {partner} | {counter} | {amount_dr} | {amount_cr} | {balance} |".format(
                        account=f"{account.code} - {account.name}"[
                            :widths["account"]
                        ].ljust(widths["account"]),
                        date=str(line.date)[:widths["date"]].ljust(widths["date"]),
                        ref=ref.ljust(widths["ref"]),
                        label=label.ljust(widths["label"]),
                        group=product_group.ljust(widths["group"]),
                        partner=partner_name.ljust(widths["partner"]),
                        counter=counter.ljust(widths["counter"]),
                        amount_dr="{:,.2f}".format(amount_dr).rjust(
                            widths["amount_dr"]
                        ),
                        amount_cr="{:,.2f}".format(amount_cr).rjust(
                            widths["amount_cr"]
                        ),
                        balance="{:,.2f}".format(period_balance).rjust(
                            widths["balance"]
                        ),
                    )
                    breakdown.append(row)

                # ---------------------------------------------------------
                # 5) Summary row at bottom: Opening in label, Closing text in last col
                # ---------------------------------------------------------
                closing_balance = opening_balance + period_balance

                # Only Opening in the label column
                summary_label = (
                    f"Opening: {opening_balance:,.2f}"
                )[:widths["label"]]

                # Partner name (if filtered by partner)
                summary_partner = (
                    (rec.partner_id.name or "")[:widths["partner"]]
                    if rec.partner_id
                    else ""
                )

                # Last column shows "Closing: xxx"
                closing_text = (
                    f"Closing: {closing_balance:,.2f}"
                )[:widths["balance"]].rjust(widths["balance"])

                summary_row = "| {account} | {date} | {ref} | {label} | {group} | {partner} | {counter} | {amount_dr} | {amount_cr} | {balance} |".format(
                    account=f"{account.code} - {account.name}"[
                        :widths["account"]
                    ].ljust(widths["account"]),
                    date="".ljust(widths["date"]),
                    ref="".ljust(widths["ref"]),
                    label=summary_label.ljust(widths["label"]),
                    group="".ljust(widths["group"]),
                    partner=summary_partner.ljust(widths["partner"]),
                    counter="".ljust(widths["counter"]),
                    amount_dr="{:,.2f}".format(0.0).rjust(widths["amount_dr"]),
                    amount_cr="{:,.2f}".format(0.0).rjust(widths["amount_cr"]),
                    balance=closing_text,
                )
                breakdown.append(summary_row)

            # Build HTML from breakdown
            html = "<h3>General Ledger - Journal Entry Breakdown by Account</h3>"
            html += (
                "<table border='1' cellpadding='3' cellspacing='0' "
                "style='border-collapse: collapse; font-size: 12px; width: 100%;'>"
            )

            for line in breakdown:
                if line.startswith("ACCOUNT_HEADER||"):
                    account_name = line.split("||")[1]
                    html += (
                        "<tr style='background:#a0c4ff;'>"
                        "<td colspan='10'><strong>{}</strong></td>"
                        "</tr>".format(account_name)
                    )
                elif line.strip().startswith("|"):
                    columns = [col.strip() for col in line.strip("|").split("|")]
                    tag = "th" if "Date" in columns[1] else "td"
                    row_style = "background:#f1f1f1;" if tag == "th" else ""
                    html += "<tr style='{}'>".format(row_style) + "".join(
                        "<{tag}>{c}</{tag}>".format(tag=tag, c=c) for c in columns
                    ) + "</tr>"

            html += "</table>"
            rec.journal_items = html

    def action_export_xlsx(self):
        return {
            'type': 'ir.actions.act_url',
            'url': '/general_ledger/export_xlsx?record_id=%s' % self.id,
            'target': 'self',
        }

# date filter wont discard account without transaction
# opening and closing balance at the end row
