from odoo import api, models, fields


class PartnerLedger(models.Model):
    _name = 'partner.ledger'
    _description = "PL Customization"

    partner_journal_breakdown = fields.Text(string="Partner Journal Breakdown", compute="_compute_all_account_data2", store=False)

    @api.depends()
    def _compute_all_account_data2(self):
        AccountMoveLine = self.env['account.move.line'].sudo()

        move_lines = AccountMoveLine.search([
            ('partner_id', '!=', False),
            ('move_id.state', '=', 'posted')
        ])

        for rec in self:
            breakdown = []

            lines_by_partner = {}
            for line in move_lines:
                partner = line.partner_id
                if partner not in lines_by_partner:
                    lines_by_partner[partner] = []
                lines_by_partner[partner].append(line)

            for partner, lines in lines_by_partner.items():
                breakdown.append("")
                breakdown.append("=" * 200)
                breakdown.append(f"Partner: {partner.name}")
                breakdown.append("=" * 200)

                total_debit = sum(line.debit for line in lines)
                total_credit = sum(line.credit for line in lines)
                open_balance = total_debit - total_credit
                breakdown.append(f"  Total Debit : {total_debit:.2f}")
                breakdown.append(f"  Total Credit: {total_credit:.2f}")
                breakdown.append(f"  Open Balance: {open_balance:.2f}")
                breakdown.append("-" * 270)

                # Journal summary header with AR/AP columns
                breakdown.append("{:<25} {:<25} {:<40} {:<40} {:<40} {:>40} {:>40} {:>40} {:>40} {:>40}".format(
                    "Journal Entry", "Journal", "Account", "Inv Date", "Due Date", "Debit", "Credit", "Balance",
                    "Receivable", "Payable"
                ))
                breakdown.append("-" * 270)

                seen_moves = set()
                for line in sorted(lines, key=lambda l: (l.date, l.move_id.id)):
                    move = line.move_id
                    if move.id in seen_moves:
                        continue
                    seen_moves.add(move.id)

                    # Primary line to show summary
                    primary_line = move.line_ids.filtered(lambda l: l.partner_id == partner).sorted('id')[:1]
                    if primary_line:
                        jline = primary_line[0]
                        debit = jline.debit
                        credit = jline.credit
                        balance = debit - credit

                        # Find receivable and payable accounts from the move
                        receivable_account = next(
                            (l.account_id.name for l in move.line_ids if l.account_id.account_type == 'asset_receivable'),
                            ''
                        )
                        payable_account = next(
                            (l.account_id.name for l in move.line_ids if l.account_id.account_type == 'liability_payable'),
                            ''
                        )

                        breakdown.append("{:<25} {:<25} {:<40} {:<40} {:<40} {:>40.2f} {:>40.2f} {:>40.2f} {:>40} {:>40}".format(
                            move.name or '',
                            jline.journal_id.code or '',
                            jline.account_id.code or '',
                            str(move.invoice_date or ''),
                            str(move.invoice_date_due or ''),
                            debit,
                            credit,
                            balance,
                            receivable_account,
                            payable_account
                        ))

                    # Full breakdown
                    breakdown.append("\n Journal Lines Change:")
                    breakdown.append(" | {:<120}| {:<120} {:>40} {:>40}".format("Account", "Partner", "Debit", "Credit"))
                    breakdown.append(" | " + "-" * 270 + " | ")

                    for jline in move.line_ids.sorted(key=lambda l: l.account_id.code or ''):
                        acc = f"{jline.account_id.code} {jline.account_id.name}"
                        partner_name = jline.partner_id.name or '-'
                        breakdown.append(" | {:<120}| {:<120} {:>40.2f} {:>40.2f}".format(
                            acc[:30], partner_name[:30], jline.debit, jline.credit
                        ))
                    breakdown.append("  " + "=" * 200)

            rec.partner_journal_breakdown = '\n'.join(breakdown) if breakdown else 'No partner data found.'

            # working.  
