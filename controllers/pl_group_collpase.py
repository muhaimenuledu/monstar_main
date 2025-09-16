from odoo import http
from odoo.http import request
import io
import xlsxwriter


class PartnerLedgerCollapseXlsxController(http.Controller):
    """Controller to export Partner Ledger totals XLSX (with opening balance and date range)"""

    @http.route('/group_party/export_totals_xlsx', type='http', auth='user')
    def export_totals_xlsx(self, record_id):
        record = request.env['group.party'].browse(int(record_id))
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Partner Totals')

        # Formats
        bold = workbook.add_format({'bold': True, 'bg_color': '#F0F0F0'})
        money = workbook.add_format({'num_format': '#,##0.00'})
        header = workbook.add_format({'bold': True, 'font_size': 12})
        total_fmt = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3', 'num_format': '#,##0.00'})

        row = 0

        # ---------------- Report Date Range ----------------
        date_from = record.date_from.strftime("%Y-%m-%d") if record.date_from else ""
        date_to = record.date_to.strftime("%Y-%m-%d") if record.date_to else ""
        date_range_text = f"Report Date Range: {date_from or '...'} to {date_to or '...'}"
        sheet.merge_range(row, 0, row, 4, date_range_text, header)
        row += 2  # leave one empty row before table
        # ---------------------------------------------------

        # Column headers
        sheet.write(row, 0, "Partner", bold)
        sheet.write(row, 1, "Opening Balance", bold)
        sheet.write(row, 2, "Total Debit", bold)
        sheet.write(row, 3, "Total Credit", bold)
        sheet.write(row, 4, "Balance", bold)
        row += 1

        AccountMoveLine = request.env['account.move.line'].sudo()
        partners = request.env['res.partner'].sudo().search(
            ['|', ('customer_rank', '>', 0), ('supplier_rank', '>', 0)]
        )

        if record.partner_id:
            partners = partners.filtered(lambda p: p.id == record.partner_id.id)
        if record.vendor_group:
            partners = partners.filtered(lambda p: p.vendor_group == record.vendor_group)

        # Totals accumulators
        total_opening_balance = 0.0
        total_debit_sum = 0.0
        total_credit_sum = 0.0
        total_balance_sum = 0.0

        for partner in partners:
            # Domain for posted move lines for this partner (in-period)
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

            if not partner_lines and not record.date_from:
                continue

            # ---------------- Opening Balance ----------------
            opening_balance = 0.0
            if record.date_from:
                base_opening_domain = [
                    ('partner_id', '=', partner.id),
                    ('move_id.state', '=', 'posted'),
                    ('date', '<', record.date_from),
                    ('account_id.account_type', 'in', ['asset_receivable', 'liability_payable']),
                ]
                opening_lines = AccountMoveLine.search(base_opening_domain)

                receivable_open = sum(l.debit - l.credit for l in opening_lines if l.account_id.account_type == 'asset_receivable')
                payable_open = sum(l.credit - l.debit for l in opening_lines if l.account_id.account_type == 'liability_payable')
                opening_balance = receivable_open - payable_open
            # -------------------------------------------------

            # Period totals
            total_debit = sum(l.debit for l in partner_lines)
            total_credit = sum(l.credit for l in partner_lines)
            running_receivable = sum(l.debit - l.credit for l in partner_lines if l.account_id.account_type == 'asset_receivable')
            running_payable = sum(l.credit - l.debit for l in partner_lines if l.account_id.account_type == 'liability_payable')
            balance = opening_balance + (running_receivable - running_payable)

            # Accumulate totals
            total_opening_balance += opening_balance
            total_debit_sum += total_debit
            total_credit_sum += total_credit
            total_balance_sum += balance

            # Write row
            sheet.write(row, 0, partner.name)
            sheet.write_number(row, 1, opening_balance, money)
            sheet.write_number(row, 2, total_debit, money)
            sheet.write_number(row, 3, total_credit, money)
            sheet.write_number(row, 4, balance, money)
            row += 1

        # ---------------- Totals Row ----------------
        sheet.write(row, 0, "TOTAL", bold)
        sheet.write_number(row, 1, total_opening_balance, total_fmt)
        sheet.write_number(row, 2, total_debit_sum, total_fmt)
        sheet.write_number(row, 3, total_credit_sum, total_fmt)
        sheet.write_number(row, 4, total_balance_sum, total_fmt)
        # --------------------------------------------

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
