from odoo import http
from odoo.http import request
import io
import xlsxwriter


class PartnerLedgerCollapseXlsxController(http.Controller):
    """Controller to export Partner Ledger totals XLSX (with opening balance and date range)"""

    @http.route('/group_party/export_totals_xlsx', type='http', auth='user')
    def export_totals_xlsx(self, record_id):
        record = request.env['group.party'].sudo().browse(int(record_id))
        if not record:
            return request.not_found()

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

        # Apply filters exactly like in the model
        if record.partner_id:
            partners = partners.filtered(lambda p: p.id == record.partner_id.id)
        if record.vendor_group:
            partners = partners.filtered(lambda p: p.vendor_group == record.vendor_group)

        # Detect account type field (compatibility)
        acct_model = request.env['account.account']
        atype_field = 'account_type' if 'account_type' in acct_model._fields else 'internal_type'
        AR_VALUE = 'asset_receivable' if atype_field == 'account_type' else 'receivable'
        AP_VALUE = 'liability_payable' if atype_field == 'account_type' else 'payable'

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
                (f'account_id.{atype_field}', 'in', [AR_VALUE, AP_VALUE]),
            ]
            if record.date_from:
                line_domain.append(('date', '>=', record.date_from))
            if record.date_to:
                line_domain.append(('date', '<=', record.date_to))

            partner_lines = AccountMoveLine.search(line_domain)

            # ---------------- Opening Balance ----------------
            opening_balance = 0.0
            opening_debit_sum = 0.0
            opening_credit_sum = 0.0
            if record.date_from:
                base_opening_domain = [
                    ('partner_id', '=', partner.id),
                    ('move_id.state', '=', 'posted'),
                    ('date', '<', record.date_from),
                ]
                # Receivable
                ar_grp = AccountMoveLine.read_group(
                    base_opening_domain + [(f'account_id.{atype_field}', '=', AR_VALUE)],
                    ['debit:sum', 'credit:sum'], []
                )
                ar_d = float((ar_grp[0].get('debit', 0.0) if ar_grp else 0.0) or 0.0)
                ar_c = float((ar_grp[0].get('credit', 0.0) if ar_grp else 0.0) or 0.0)
                opening_ar = ar_d - ar_c

                # Payable
                ap_grp = AccountMoveLine.read_group(
                    base_opening_domain + [(f'account_id.{atype_field}', '=', AP_VALUE)],
                    ['debit:sum', 'credit:sum'], []
                )
                ap_d = float((ap_grp[0].get('debit', 0.0) if ap_grp else 0.0) or 0.0)
                ap_c = float((ap_grp[0].get('credit', 0.0) if ap_grp else 0.0) or 0.0)
                opening_ap = ap_c - ap_d

                opening_debit_sum = ar_d + ap_d
                opening_credit_sum = ar_c + ap_c
                opening_balance = opening_ar - opening_ap
            # -------------------------------------------------

            # Skip if no lines and no opening balance
            if not partner_lines and not opening_balance:
                continue

            # Period totals
            period_total_debit = sum(float(l.debit) for l in partner_lines)
            period_total_credit = sum(float(l.credit) for l in partner_lines)
            period_ar = sum((float(l.debit) - float(l.credit)) for l in partner_lines if getattr(l.account_id, atype_field) == AR_VALUE)
            period_ap = sum((float(l.credit) - float(l.debit)) for l in partner_lines if getattr(l.account_id, atype_field) == AP_VALUE)
            final_balance = opening_balance + (period_ar - period_ap)

            # Accumulate totals
            total_opening_balance += opening_balance
            total_debit_sum += period_total_debit
            total_credit_sum += period_total_credit
            total_balance_sum += final_balance

            # Write row
            sheet.write(row, 0, partner.name)
            sheet.write_number(row, 1, opening_balance, money)
            sheet.write_number(row, 2, period_total_debit, money)
            sheet.write_number(row, 3, period_total_credit, money)
            sheet.write_number(row, 4, final_balance, money)
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
