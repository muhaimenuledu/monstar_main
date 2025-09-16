from odoo import http
from odoo.http import request
import io
import xlsxwriter


class PartyStockSummaryExportController(http.Controller):

    @http.route('/party_stock_summary/export_xlsx', type='http', auth='user')
    def export_xlsx(self, record_id=None, **kwargs):
        record = request.env['party.stock.summary'].sudo().browse(int(record_id))
        if not record:
            return request.not_found()

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Stock Summary')

        bold = workbook.add_format({'bold': True})
        money = workbook.add_format({'num_format': '#,##0.00'})

        # === Write header row ===
        row = 0
        sheet.write(row, 0, "Partner", bold)
        sheet.write(row, 1, "Product", bold)
        sheet.write(row, 2, "Category", bold)
        sheet.write(row, 3, "Quantity Bought From", bold)
        sheet.write(row, 4, "Buying Price", bold)
        sheet.write(row, 5, "Quantity Sold To", bold)
        sheet.write(row, 6, "Selling Price", bold)
        row += 1

        SaleOrderLine = request.env["sale.order.line"].sudo()
        PurchaseOrderLine = request.env["purchase.order.line"].sudo()

        # === Domains ===
        sale_domain = [("order_id.state", "in", ["sale", "done"])]
        purchase_domain = [("order_id.state", "in", ["purchase", "done"])]

        if record.date_from:
            sale_domain.append(("order_id.date_order", ">=", record.date_from))
            purchase_domain.append(("order_id.date_order", ">=", record.date_from))
        if record.date_to:
            sale_domain.append(("order_id.date_order", "<=", record.date_to))
            purchase_domain.append(("order_id.date_order", "<=", record.date_to))
        if record.partner_id:
            sale_domain.append(("order_id.partner_id", "=", record.partner_id.id))
            purchase_domain.append(("order_id.partner_id", "=", record.partner_id.id))
        if record.product_id:
            sale_domain.append(("product_id", "=", record.product_id.id))
            purchase_domain.append(("product_id", "=", record.product_id.id))

        sale_lines = SaleOrderLine.search(sale_domain)
        purchase_lines = PurchaseOrderLine.search(purchase_domain)

        # === Build summary dict ===
        summary = {}
        for line in sale_lines:
            partner, product = line.order_id.partner_id, line.product_id
            if not partner or not product:
                continue
            summary.setdefault(partner, {})
            if product not in summary[partner]:
                summary[partner][product] = {"sold_qty": 0.0, "bought_qty": 0.0,
                                             "sold_price": 0.0, "bought_price": 0.0}
            summary[partner][product]["sold_qty"] += line.product_uom_qty
            summary[partner][product]["sold_price"] += line.product_uom_qty * line.price_unit

        for line in purchase_lines:
            partner, product = line.order_id.partner_id, line.product_id
            if not partner or not product:
                continue
            summary.setdefault(partner, {})
            if product not in summary[partner]:
                summary[partner][product] = {"sold_qty": 0.0, "bought_qty": 0.0,
                                             "sold_price": 0.0, "bought_price": 0.0}
            summary[partner][product]["bought_qty"] += line.product_qty
            summary[partner][product]["bought_price"] += line.product_qty * line.price_unit

        # === Write data ===
        for partner, products in summary.items():
            # Partner header row
            sheet.write(row, 0, partner.display_name, bold)
            row += 1

            for product, vals in products.items():
                sheet.write(row, 0, "")  # partner column empty for detail rows
                sheet.write(row, 1, product.display_name)
                sheet.write(row, 2, product.categ_id.name or "N/A")
                sheet.write(row, 3, vals["bought_qty"])
                sheet.write(row, 4, vals["bought_price"], money)
                sheet.write(row, 5, vals["sold_qty"])
                sheet.write(row, 6, vals["sold_price"], money)
                row += 1

            row += 1  # blank line after each partner

        workbook.close()
        output.seek(0)
        return request.make_response(
            output.read(),
            headers=[
                ("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
                ("Content-Disposition", 'attachment; filename="party_stock_summary.xlsx"'),
            ]
        )
