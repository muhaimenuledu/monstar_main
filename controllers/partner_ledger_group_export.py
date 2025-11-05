from odoo import http
from odoo.http import request
import io
import xlsxwriter


class PartnerLedgerGroupExportController(http.Controller):

    @http.route('/partner_ledger_group/export_xlsx', type='http', auth='user')
    def export_xlsx(self, record_id=None, **kwargs):
        record = request.env['partner.ledger.group'].sudo().browse(int(record_id))
        if not record:
            return request.not_found()

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Partner Ledger (Products Only)')

        # === Formatting styles ===
        bold = workbook.add_format({'bold': True})
        money = workbook.add_format({'num_format': '#,##0.00'})
        header_bg = workbook.add_format({'bold': True, 'bg_color': '#D9E1F2'})
        summary_bg = workbook.add_format({'bold': True, 'bg_color': '#C6EFCE', 'num_format': '#,##0.00'})

        # === Column headers ===
        row = 0
        headers = [
            "Partner",
            "Date",
            "Ref",
            "Label",
            "Product Group",
            "Product",
            "Unit Price",
            "Account (DR)",
            "Account (CR)",
            "Amount Dr.",
            "Amount Cr.",
        ]
        for col, header in enumerate(headers):
            sheet.write(row, col, header, bold)
        row += 1

        AccountMoveLine = request.env['account.move.line'].sudo()
        AccountAccount = request.env['account.account'].sudo()

        # === Build domain (only product lines) ===
        domain = [
            ('partner_id', '!=', False),
            ('move_id.state', '=', 'posted'),
            ('product_id', '!=', False),  # ✅ Added: only product-related lines
        ]
        if record.date_from:
            domain.append(('date', '>=', record.date_from))
        if record.date_to:
            domain.append(('date', '<=', record.date_to))
        if record.partner_id:
            domain.append(('partner_id', '=', record.partner_id.id))

        move_lines = AccountMoveLine.search(domain, order='date, id')

        # === Group by partner ===
        lines_by_partner = {}
        for line in move_lines:
            lines_by_partner.setdefault(line.partner_id, []).append(line)

        # === Write each partner section ===
        for partner, lines in lines_by_partner.items():
            # Partner header row
            sheet.write(row, 0, partner.name, header_bg)
            row += 1

            for line in lines:
                move = line.move_id
                ref = move.ref or move.name or "Unavailable"
                label = line.name or move.name or "Unavailable"
                product_group = line.product_id.categ_id.name if line.product_id and line.product_id.categ_id else "Unavailable"
                product_name = line.product_id.display_name if line.product_id else "Unavailable"
                account_dr = f"{line.account_id.code} - {line.account_id.name}" if line.debit else ""
                account_cr = f"{line.account_id.code} - {line.account_id.name}" if line.credit else ""
                amount_dr = line.debit or 0.0
                amount_cr = line.credit or 0.0

                # === Compute unit price ===
                if getattr(line, 'price_unit', False):
                    unit_price = line.price_unit
                elif getattr(line, 'quantity', 0) and (amount_dr or amount_cr):
                    total = amount_dr or amount_cr
                    unit_price = total / line.quantity if line.quantity else 0.0
                else:
                    unit_price = 0.0

                # === Write line ===
                sheet.write(row, 0, "")  # Empty partner cell
                sheet.write(row, 1, str(line.date))
                sheet.write(row, 2, ref)
                sheet.write(row, 3, label)
                sheet.write(row, 4, product_group)
                sheet.write(row, 5, product_name)
                sheet.write(row, 6, unit_price, money)
                sheet.write(row, 7, account_dr)
                sheet.write(row, 8, account_cr)
                sheet.write(row, 9, amount_dr, money)
                sheet.write(row, 10, amount_cr, money)
                row += 1

            # === Partner summary balance ===
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
                balance = totals.get('debit', 0.0) - totals.get('credit', 0.0)

            # Summary row
            sheet.write(row, 0, f"Balance for {partner.name}", bold)
            sheet.write(row, 10, balance, summary_bg)
            row += 2  # Blank line after each partner section

        # === Adjust column widths ===
        widths = [18, 12, 18, 25, 20, 25, 12, 30, 30, 15, 15]
        for i, w in enumerate(widths):
            sheet.set_column(i, i, w)

        workbook.close()
        output.seek(0)

        return request.make_response(
            output.read(),
            headers=[
                ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                ('Content-Disposition', 'attachment; filename="partner_ledger_group_products_only.xlsx"'),
            ]
        )
