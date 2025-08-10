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
        sheet = workbook.add_worksheet('Partner Ledger')

        bold = workbook.add_format({'bold': True})
        money = workbook.add_format({'num_format': '#,##0.00'})

        # Column headers
        row = 0
        sheet.write(row, 0, "Partner", bold)
        sheet.write(row, 1, "Date", bold)
        sheet.write(row, 2, "Label", bold)
        sheet.write(row, 3, "Group", bold)
        sheet.write(row, 4, "Unit Price", bold)  # New Column
        sheet.write(row, 5, "Account (DR)", bold)
        sheet.write(row, 6, "Account (CR)", bold)
        sheet.write(row, 7, "Amount Dr.", bold)
        sheet.write(row, 8, "Amount Cr.", bold)
        sheet.write(row, 9, "Balance", bold)
        row += 1

        AccountMoveLine = request.env['account.move.line'].sudo()
        domain = [('partner_id', '!=', False), ('move_id.state', '=', 'posted')]

        if record.date_from:
            domain.append(('date', '>=', record.date_from))
        if record.date_to:
            domain.append(('date', '<=', record.date_to))

        move_lines = AccountMoveLine.search(domain, order='date, id')

        # Group lines by partner
        lines_by_partner = {}
        for line in move_lines:
            lines_by_partner.setdefault(line.partner_id, []).append(line)

        # Write each partner section
        for partner, lines in lines_by_partner.items():
            # Partner name as a header row
            sheet.write(row, 0, partner.name, bold)
            row += 1

            balance = 0.0
            for line in lines:
                move = line.move_id
                label = line.name or move.name or "Unavailable"
                product_group = line.product_id.categ_id.name if line.product_id and line.product_id.categ_id else "Unavailable"
                account_dr = f"{line.account_id.code} - {line.account_id.name}" if line.debit else ""
                account_cr = f"{line.account_id.code} - {line.account_id.name}" if line.credit else ""
                amount_dr = line.debit or 0.0
                amount_cr = line.credit or 0.0
                balance += amount_dr - amount_cr

                # Compute unit price
                if hasattr(line, 'price_unit') and line.price_unit:
                    unit_price = line.price_unit
                elif getattr(line, 'quantity', 0) and (amount_dr or amount_cr):
                    # try calculating from total / qty
                    total = amount_dr or amount_cr
                    unit_price = total / line.quantity if line.quantity else 0.0
                else:
                    unit_price = 0.0

                # Write data row
                sheet.write(row, 0, "")  # empty partner cell
                sheet.write(row, 1, str(line.date))
                sheet.write(row, 2, label)
                sheet.write(row, 3, product_group)
                sheet.write(row, 4, unit_price, money)  # New column
                sheet.write(row, 5, account_dr)
                sheet.write(row, 6, account_cr)
                sheet.write(row, 7, amount_dr, money)
                sheet.write(row, 8, amount_cr, money)
                sheet.write(row, 9, balance, money)
                row += 1

            row += 1  # blank line after each partner

        workbook.close()
        output.seek(0)
        return request.make_response(
            output.read(),
            headers=[
                ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                ('Content-Disposition', 'attachment; filename="partner_ledger_group.xlsx"'),
            ]
        )
