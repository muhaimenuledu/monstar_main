from odoo import api, models, fields


class PartnerLedgerGroup(models.Model):
    _name = 'partner.ledger.group'
    _description = "Partner Ledger Journal Line Breakdown"

    partner_journal_breakdown = fields.Text(string="Partner Journal Breakdown", compute="_compute_journal_breakdown", store=False)

    @api.depends()
    def _compute_journal_breakdown(self):
        AccountMoveLine = self.env['account.move.line'].sudo()

        move_lines = AccountMoveLine.search([
            ('partner_id', '!=', False),
            ('move_id.state', '=', 'posted')
        ])

        for rec in self:
            breakdown = []

            # Group lines by partner
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

                seen_moves = set()
                for line in sorted(lines, key=lambda l: (l.date, l.move_id.id)):
                    move = line.move_id
                    if move.id in seen_moves:
                        continue
                    seen_moves.add(move.id)

                    breakdown.append(f"\nJournal Entry: {move.name or ''}")
                    breakdown.append(f"Date: {move.date} | Journal: {move.journal_id.name}")
                    breakdown.append("-" * 270)

                    breakdown.append(" | {:>45} {:>45} {:>45} {:>45} {:>45} {:>35} {:>35}".format(
                        "Account", "Partner", "Product", "Category", "Date", "Debit", "Credit"
                    ))
                    breakdown.append(" | " + "-" * 260 + " |")

                    for jline in move.line_ids.filtered(lambda l: l.partner_id == partner):
                        acc = f"{jline.account_id.code or ''} {jline.account_id.name or ''}"
                        partner_name = jline.partner_id.name or '-'
                        product_name = jline.product_id.name or '-'
                        category_name = jline.product_id.categ_id.name if jline.product_id and jline.product_id.categ_id else '-'

                        breakdown.append(" | {:>40} {:>35} {:>35} {:>55} {:>30} {:>15.2f} {:>15.2f}".format(
                            acc[:20],
                            partner_name[:25],
                            product_name[:25],
                            category_name[:25],
                            str(jline.date or '')[:20],
                            jline.debit,
                            jline.credit
                        ))

                    breakdown.append("=" * 200)

            rec.partner_journal_breakdown = '\n'.join(breakdown) if breakdown else 'No partner data found.'
# working