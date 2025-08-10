from odoo import http
from odoo.http import request
import io
import xlsxwriter
from collections import defaultdict

class PartnerLedgerExportController(http.Controller):

    @http.route(['/partner_ledger/export_xlsx'], type='http', auth="user")
    def export_xlsx(self, record_id=None, **kwargs):
        record = request.env['partner.ledger'].browse(int(record_id))

        # Set up workbook
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet("Partner Ledger")

        # Formats
        header_format = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3'})
        category_format = workbook.add_format({'bold': True, 'bg_color': '#ADD8E6'})
        money_format = workbook.add_format({'num_format': '#,##0'})

        row = 0
        sheet.write(row, 0, 'Partner', header_format)
        sheet.write(row, 1, 'Opening Balance', header_format)
        sheet.write(row, 2, 'Total Debit', header_format)
        sheet.write(row, 3, 'Total Credit', header_format)
        sheet.write(row, 4, 'Closing Balance', header_format)
        row += 1

        # Grouping logic
        AccountMoveLine = request.env['account.move.line'].sudo()

        base_domain = [('partner_id', '!=', False), ('move_id.state', '=', 'posted')]
        if record.product_categ_id:
            base_domain.append(('product_id.categ_id', '=', record.product_categ_id.id))
        if record.partner_id:
            base_domain.append(('partner_id', '=', record.partner_id.id))

        opening_domain = list(base_domain)
        if record.date_from:
            opening_domain.append(('date', '<', record.date_from))

        trx_domain = list(base_domain)
        if record.date_from:
            trx_domain.append(('date', '>=', record.date_from))
        if record.date_to:
            trx_domain.append(('date', '<=', record.date_to))

        opening_lines = AccountMoveLine.search(opening_domain)
        trx_lines = AccountMoveLine.search(trx_domain)

        grouped_data = defaultdict(lambda: defaultdict(lambda: {
            'opening': 0.0, 'debit': 0.0, 'credit': 0.0
        }))

        for line in opening_lines:
            group = line.product_id.categ_id.name if line.product_id and line.product_id.categ_id else "Unknown"
            partner = line.partner_id.name or "Unknown"
            grouped_data[group][partner]['opening'] += line.debit - line.credit

        for line in trx_lines:
            group = line.product_id.categ_id.name if line.product_id and line.product_id.categ_id else "Unknown"
            partner = line.partner_id.name or "Unknown"
            grouped_data[group][partner]['debit'] += line.debit
            grouped_data[group][partner]['credit'] += line.credit

        # Write category once, then its partner rows
        for category, partners in grouped_data.items():
            sheet.write(row, 0, category, category_format)
            row += 1

            for partner, values in partners.items():
                opening = values['opening']
                debit = values['debit']
                credit = values['credit']
                closing = opening + debit - credit

                sheet.write(row, 0, partner)
                sheet.write_number(row, 1, opening, money_format)
                sheet.write_number(row, 2, debit, money_format)
                sheet.write_number(row, 3, credit, money_format)
                sheet.write_number(row, 4, closing, money_format)
                row += 1

            row += 1  # blank line between categories

        workbook.close()
        output.seek(0)

        return request.make_response(
            output.read(),
            headers=[
                ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                ('Content-Disposition', 'attachment; filename="partner_ledger_summary.xlsx"')
            ]
        )
