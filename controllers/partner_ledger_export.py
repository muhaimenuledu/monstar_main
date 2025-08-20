from odoo import http
from odoo.http import request
import io
import xlsxwriter

class GroupPartyExportController(http.Controller):

    @http.route(['/group_party/export_xlsx'], type='http', auth="user")
    def export_xlsx(self, record_id=None, **kwargs):
        record = request.env['group.party'].browse(int(record_id))
        if not record.exists():
            return request.not_found()

        AccountMoveLine = request.env['account.move.line'].sudo()

        # === Build the same domain logic as _build_html ===
        line_domain = [
            ('partner_id', '!=', False),
            ('move_id.state', '=', 'posted'),
            ('account_id.account_type', 'in', ['asset_receivable', 'liability_payable']),
        ]
        if record.partner_id:
            line_domain.append(('partner_id', '=', record.partner_id.id))
        if record.vendor_group:
            line_domain.append(('partner_id.vendor_group', '=', record.vendor_group))
        if record.date_from:
            line_domain.append(('date', '>=', record.date_from))
        if record.date_to:
            line_domain.append(('date', '<=', record.date_to))

        partner_domain = ['|', ('customer_rank', '>', 0), ('supplier_rank', '>', 0)]
        partners = request.env['res.partner'].search(partner_domain)
        if record.partner_id:
            partners = partners.filtered(lambda p: p.id == record.partner_id.id)
        if record.vendor_group:
            partners = partners.filtered(lambda p: p.vendor_group == record.vendor_group)

        # === Create Workbook ===
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet("Partner Ledger")

        # Formats
        header_format = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3'})
        bold_format = workbook.add_format({'bold': True})
        money_format = workbook.add_format({'num_format': '#,##0.00'})

        # Header
        headers = ['Date', 'Journal', 'Account', 'Reference', 'Due Date', 'Debit', 'Credit', 'Balance (AR - AP)']
        for col, head in enumerate(headers):
            sheet.write(0, col, head, header_format)

        row = 1
        for partner in partners:
            partner_lines = AccountMoveLine.search(line_domain + [('partner_id', '=', partner.id)], order='date,id')
            if not partner_lines:
                continue

            running_receivable = 0.0
            running_payable = 0.0
            total_debit = 0.0
            total_credit = 0.0

            # Partner header row
            sheet.write(row, 0, f"Partner: {partner.name}", bold_format)
            row += 1

            for line in partner_lines:
                debit_val = line.debit
                credit_val = line.credit
                account_type = line.account_id.account_type

                if account_type == 'asset_receivable':
                    running_receivable += (debit_val - credit_val)
                elif account_type == 'liability_payable':
                    running_payable += (credit_val - debit_val)

                total_debit += debit_val
                total_credit += credit_val
                running_balance = running_receivable - running_payable

                sheet.write(row, 0, str(line.date))
                sheet.write(row, 1, line.move_id.journal_id.code)
                sheet.write(row, 2, f"{line.account_id.code} - {line.account_id.name}")
                sheet.write(row, 3, line.move_id.name or '')
                sheet.write(row, 4, str(line.date_maturity or ''))
                sheet.write_number(row, 5, debit_val, money_format)
                sheet.write_number(row, 6, credit_val, money_format)
                sheet.write_number(row, 7, running_balance, money_format)
                row += 1

            final_balance = running_receivable - running_payable
            sheet.write(row, 0, f"Total {partner.name}", bold_format)
            sheet.write_number(row, 5, total_debit, money_format)
            sheet.write_number(row, 6, total_credit, money_format)
            sheet.write_number(row, 7, final_balance, money_format)
            row += 2  # space before next partner

        workbook.close()
        output.seek(0)

        return request.make_response(
            output.read(),
            headers=[
                ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                ('Content-Disposition', 'attachment; filename="partner_ledger.xlsx"')
            ]
        )
