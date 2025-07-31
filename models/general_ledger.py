from odoo import api, models, fields


class GeneralLedger(models.Model):
    _name = 'general.ledger'
    _description = "GL Customization"

    name = fields.Char(string="GL", required=True)
    journal_items = fields.Text(string="Journal Entry Breakdown by Account", compute="_compute_journal_breakdowns", store=False)

    @api.depends()
    def _compute_journal_breakdowns(self):
        AccountMoveLine = self.env['account.move.line'].sudo()
        Account = self.env['account.account'].sudo()
        all_accounts = Account.search([], order='code')

        for rec in self:
            lines_output = []

            for account in all_accounts:
                move_lines = AccountMoveLine.search([
                    ('account_id', '=', account.id),
                    ('move_id.state', '=', 'posted')
                ])
                related_moves = move_lines.mapped('move_id')

                if not related_moves:
                    continue

                # Add Account Title Header
                lines_output.append("")
                lines_output.append("═" * 130)
                lines_output.append(f"[{account.code}] {account.name}")
                lines_output.append("═" * 130)

                for move in related_moves:
                    full_lines = move.line_ids.sorted(key=lambda l: l.account_id.code or '')

                    lines_output.append(f" Journal Entry: {move.name or 'N/A'} | Date: {move.date}")
                    lines_output.append("  {:>35} {:>25} {:>25} {:>25} {:>10} {:>10}".format(
                        "Account", "Partner", "Product", "Category", "Debit", "Credit"
                    ))
                    lines_output.append("  " + "-" * 130)

                    for line in full_lines:
                        acc = f"{line.account_id.code} {line.account_id.name}"
                        partner = line.partner_id.name or '-'
                        product = line.product_id.name or '-'
                        category = line.product_id.categ_id.name if line.product_id and line.product_id.categ_id else '-'

                        lines_output.append("  {:>35} {:>25} {:>25} {:>25} {:>10.2f} {:>10.2f}".format(
                            acc[:35], partner[:25], product[:25], category[:25], line.debit, line.credit
                        ))

                    lines_output.append("  " + "=" * 130)

            rec.journal_items = '\n'.join(lines_output)
