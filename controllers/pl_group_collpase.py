from odoo import http
from odoo.http import request
import io
import xlsxwriter

class PartnerLedgerCollapseXlsxController(http.Controller):
    """Controller to export Partner Ledger totals XLSX (no details)"""

    @http.route('/group_party/export_totals_xlsx', type='http', auth='user')
    def export_totals_xlsx(self, record_id):
        record = request.env['group.party'].browse(int(record_id))
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Partner Totals')

        # Formats
        bold = workbook.add_format({'bold': True, 'bg_color': '#F0F0F0'})
        money = workbook.add_format({'num_format': '#,##0.00'})

        # Column headers
        row = 0
        sheet.write(row, 0, "Partner", bold)
        sheet.write(row, 1, "Total Debit", bold)
        sheet.write(row, 2, "Total Credit", bold)
        sheet.write(row, 3, "Balance", bold)
        row += 1

        AccountMoveLine = request.env['account.move.line'].sudo()
        partners = request.env['res.partner'].sudo().search(
            ['|', ('customer_rank', '>', 0), ('supplier_rank', '>', 0)]
        )

        if record.partner_id:
            partners = partners.filtered(lambda p: p.id == record.partner_id.id)
        if record.vendor_group:
            partners = partners.filtered(lambda p: p.vendor_group == record.vendor_group)

        for partner in partners:
            # Domain for posted move lines for this partner
            line_domain = [
                ('partner_id', '=', partner.id),
                ('move_id.state', '=', 'posted'),
                ('account_id.account_type', 'in', ['asset_receivable', 'liability_payable'])
            ]
            if record.date_from:
                line_domain.append(('date', '>=', record.date_from))
            if record.date_to:
                line_domain.append(('date', '<=', record.date_to))

            partner_lines = AccountMoveLine.search(line_domain)
            if not partner_lines:
                continue

            total_debit = sum(l.debit for l in partner_lines)
            total_credit = sum(l.credit for l in partner_lines)
            running_receivable = sum(l.debit - l.credit for l in partner_lines if l.account_id.account_type == 'asset_receivable')
            running_payable = sum(l.credit - l.debit for l in partner_lines if l.account_id.account_type == 'liability_payable')
            balance = running_receivable - running_payable

            sheet.write(row, 0, partner.name)
            sheet.write_number(row, 1, total_debit, money)
            sheet.write_number(row, 2, total_credit, money)
            sheet.write_number(row, 3, balance, money)
            row += 1

        workbook.close()
        output.seek(0)
        filename = "partner_totals_report.xlsx"

        return request.make_response(
            output.read(),
            headers=[
                ('Content-Disposition', f'attachment; filename={filename}'),
                ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            ]
        )
