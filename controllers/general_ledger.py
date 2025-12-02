from odoo import http
from odoo.http import request
import io
import xlsxwriter


class GeneralLedgerXlsxController(http.Controller):

    @http.route('/general_ledger/export_xlsx', type='http', auth='user')
    def export_xlsx(self, record_id):
        record = request.env['general.ledger'].browse(int(record_id))
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('General Ledger')

        bold = workbook.add_format({'bold': True})
        money = workbook.add_format({'num_format': '#,##0.00'})

        # Column headers
        row = 0
        sheet.write(row, 0, "Account", bold)
        sheet.write(row, 1, "Date", bold)
        sheet.write(row, 2, "Label", bold)
        sheet.write(row, 3, "Product Group", bold)
        sheet.write(row, 4, "Counter Account", bold)
        sheet.write(row, 5, "Debit", bold)
        sheet.write(row, 6, "Credit", bold)
        sheet.write(row, 7, "Balance", bold)
        row += 1

        AccountMoveLine = request.env['account.move.line'].sudo()
        Account = request.env['account.account'].sudo()

        accounts = (
            Account.search([('id', '=', record.account_id.id)])
            if record.account_id
            else Account.search([], order='code')
        )

        for account in accounts:
            # Domain for period transactions
            domain = [
                ('account_id', '=', account.id),
                ('move_id.state', '=', 'posted'),
            ]
            if record.date_from:
                domain.append(('date', '>=', record.date_from))
            if record.date_to:
                domain.append(('date', '<=', record.date_to))
            if getattr(record, 'partner_id', False):
                domain.append(('partner_id', '=', record.partner_id.id))

            move_lines = AccountMoveLine.search(domain, order='date, id')

            # ---------------------------------------------------------
            # Case 1: No transactions in the period → still show balance
            # ---------------------------------------------------------
            if not move_lines:
                # Keep original behavior if there is no date filter at all
                if not (record.date_from or record.date_to):
                    continue

                # Compute balance as of date_to (or before date_from) like in the model
                opening_domain = [
                    ('account_id', '=', account.id),
                    ('move_id.state', '=', 'posted'),
                ]
                if getattr(record, 'partner_id', False):
                    opening_domain.append(('partner_id', '=', record.partner_id.id))

                if record.date_to:
                    opening_domain.append(('date', '<=', record.date_to))
                    as_of_label = f"Balance as of {record.date_to}"
                elif record.date_from:
                    opening_domain.append(('date', '<', record.date_from))
                    as_of_label = f"Balance as of {record.date_from}"
                else:
                    as_of_label = "Balance"

                opening_lines = AccountMoveLine.search(opening_domain)
                balance = 0.0
                for ol in opening_lines:
                    balance += (ol.debit or 0.0) - (ol.credit or 0.0)

                # Account header row
                sheet.write(row, 0, f"{account.code} - {account.name}", bold)
                row += 1

                # Single summary row: only balance, no movement
                sheet.write(row, 0, "")           # Account column empty (header above)
                sheet.write(row, 1, "")           # Date empty
                sheet.write(row, 2, as_of_label)  # Label: "Balance as of ..."
                sheet.write(row, 3, "")           # Product Group
                sheet.write(row, 4, "")           # Counter Account
                sheet.write_number(row, 5, 0.0, money)  # Debit
                sheet.write_number(row, 6, 0.0, money)  # Credit
                sheet.write_number(row, 7, balance, money)  # Balance
                row += 1

                row += 1  # Blank line between accounts
                continue

            # ---------------------------------------------------------
            # Case 2: Account has transactions in the period (original logic)
            # ---------------------------------------------------------

            # Account header row
            sheet.write(row, 0, f"{account.code} - {account.name}", bold)
            row += 1

            balance = 0.0
            for line in move_lines:
                label = line.name or line.move_id.name or ""
                product_group = (
                    line.product_id.categ_id.name
                    if line.product_id and line.product_id.categ_id
                    else ""
                )
                counter_accounts = line.move_id.line_ids.filtered(
                    lambda l: l != line and l.account_id != line.account_id
                )
                counter = ', '.join(
                    set(f"{l.account_id.code} - {l.account_id.name}" for l in counter_accounts)
                )

                amount_dr = line.debit or 0.0
                amount_cr = line.credit or 0.0
                balance += amount_dr - amount_cr

                sheet.write(row, 0, "")  # Empty cell instead of account name
                sheet.write(row, 1, str(line.date))
                sheet.write(row, 2, label)
                sheet.write(row, 3, product_group)
                sheet.write(row, 4, counter)
                sheet.write_number(row, 5, amount_dr, money)
                sheet.write_number(row, 6, amount_cr, money)
                sheet.write_number(row, 7, balance, money)
                row += 1

            row += 1  # Blank line between accounts

        workbook.close()
        output.seek(0)
        filename = "general_ledger_report.xlsx"

        return request.make_response(
            output.read(),
            headers=[
                ('Content-Disposition', f'attachment; filename={filename}'),
                ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            ]
        )
# date filter wont discard account without transaction
