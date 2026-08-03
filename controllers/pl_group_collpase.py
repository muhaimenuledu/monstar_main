# -*- coding: utf-8 -*-
import io
import xlsxwriter
from odoo import http
from odoo.http import request


class PartnerLedgerXlsxController(http.Controller):

    # -------------------------------------------------------------
    # 1. EXPORT DETAILED PARTNER LEDGER
    # -------------------------------------------------------------
    @http.route('/group_party/export_xlsx', type='http', auth='user', website=False)
    def export_xlsx(self, record_id, **kwargs):
        record = request.env['group.party'].browse(int(record_id))
        if not record.exists():
            return request.not_found()

        # Fetch data using group.py's centralized method
        report_data, all_totals = record._get_report_data()

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Partner Ledger Detail')

        # Formats
        bold = workbook.add_format({'bold': True, 'bg_color': '#F0F0F0'})
        money = workbook.add_format({'num_format': '#,##0.00'})
        header = workbook.add_format({'bold': True, 'font_size': 12})
        sub_bold = workbook.add_format({'bold': True, 'bg_color': '#DDD'})
        partner_header = workbook.add_format({'bold': True, 'bg_color': '#EAEAEA'})
        total_fmt = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3', 'num_format': '#,##0.00'})

        row = 0

        date_from_str = str(record.date_from) if record.date_from else ""
        date_to_str = str(record.date_to) if record.date_to else ""
        sheet.merge_range(row, 0, row, 7, f"Company: {all_totals['company_name']} | Date Range: {date_from_str or '...'} to {date_to_str or '...'}", header)
        row += 2

        cols = ["Date", "Journal", "Account", "Reference", "Due Date", "Debit", "Credit", "Balance"]
        for idx, col_name in enumerate(cols):
            sheet.write(row, idx, col_name, bold)
        row += 1

        for pdata in report_data:
            partner = pdata['partner']

            # Partner Block Header
            sheet.merge_range(row, 0, row, 7, partner.name or '', partner_header)
            row += 1

            # Initial Balance Row
            sheet.write(row, 3, "Initial Balance", sub_bold)
            sheet.write_number(row, 5, pdata['opening_debit_sum'], money)
            sheet.write_number(row, 6, pdata['opening_credit_sum'], money)
            sheet.write_number(row, 7, pdata['opening_balance'], money)
            row += 1

            # Move Lines
            for line in pdata['lines']:
                sheet.write(row, 0, line['date'])
                sheet.write(row, 1, line['journal'])
                sheet.write(row, 2, line['account'])
                sheet.write(row, 3, line['reference'])
                sheet.write(row, 4, line['due_date'])
                sheet.write_number(row, 5, line['debit'], money)
                sheet.write_number(row, 6, line['credit'], money)
                sheet.write_number(row, 7, line['balance'], money)
                row += 1

            # Subtotal Row
            sheet.write(row, 3, f"Total {partner.name or ''}", sub_bold)
            sheet.write_number(row, 5, pdata['period_total_debit'], total_fmt)
            sheet.write_number(row, 6, pdata['period_total_credit'], total_fmt)
            sheet.write_number(row, 7, pdata['final_balance'], total_fmt)
            row += 2

        # Grand Totals
        sheet.write(row, 0, "ALL PARTNERS TOTAL", bold)
        sheet.write_number(row, 5, all_totals['debit'], total_fmt)
        sheet.write_number(row, 6, all_totals['credit'], total_fmt)
        sheet.write_number(row, 7, all_totals['balance'], total_fmt)

        workbook.close()
        output.seek(0)
        return request.make_response(
            output.read(),
            headers=[
                ('Content-Disposition', 'attachment; filename=partner_ledger_details.xlsx'),
                ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                ('Cache-Control', 'no-cache, no-store, must-revalidate'),
                ('Pragma', 'no-cache'),
                ('Expires', '0'),
            ]
        )

    # -------------------------------------------------------------
    # 2. EXPORT TOTALS ONLY PARTNER LEDGER
    # -------------------------------------------------------------
    @http.route('/group_party/export_totals_xlsx', type='http', auth='user', website=False)
    def export_totals_xlsx(self, record_id, **kwargs):
        record = request.env['group.party'].browse(int(record_id))
        if not record.exists():
            return request.not_found()

        report_data, all_totals = record._get_report_data()

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Partner Totals')

        bold = workbook.add_format({'bold': True, 'bg_color': '#F0F0F0'})
        money = workbook.add_format({'num_format': '#,##0.00'})
        header = workbook.add_format({'bold': True, 'font_size': 12})
        total_fmt = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3', 'num_format': '#,##0.00'})

        row = 0

        date_from_str = str(record.date_from) if record.date_from else ""
        date_to_str = str(record.date_to) if record.date_to else ""

        sheet.merge_range(row, 0, row, 4, f"Company: {all_totals['company_name']} | Date Range: {date_from_str or '...'} to {date_to_str or '...'}", header)
        row += 2

        sheet.write(row, 0, "Partner", bold)
        sheet.write(row, 1, "Opening Balance", bold)
        sheet.write(row, 2, "Total Debit", bold)
        sheet.write(row, 3, "Total Credit", bold)
        sheet.write(row, 4, "Balance", bold)
        row += 1

        for pdata in report_data:
            sheet.write(row, 0, pdata['partner'].name or '')
            sheet.write_number(row, 1, pdata['opening_balance'], money)
            sheet.write_number(row, 2, pdata['period_total_debit'], money)
            sheet.write_number(row, 3, pdata['period_total_credit'], money)
            sheet.write_number(row, 4, pdata['final_balance'], money)
            row += 1

        # Grand Totals Row
        sheet.write(row, 0, "TOTAL", bold)
        sheet.write_number(row, 1, all_totals['opening'], total_fmt)
        sheet.write_number(row, 2, all_totals['debit'], total_fmt)
        sheet.write_number(row, 3, all_totals['credit'], total_fmt)
        sheet.write_number(row, 4, all_totals['balance'], total_fmt)

        workbook.close()
        output.seek(0)

        return request.make_response(
            output.read(),
            headers=[
                ('Content-Disposition', 'attachment; filename=partner_totals_report.xlsx'),
                ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                ('Cache-Control', 'no-cache, no-store, must-revalidate'),
                ('Pragma', 'no-cache'),
                ('Expires', '0'),
            ]
        )
