# -*- coding: utf-8 -*-
from odoo import api, fields, models
from datetime import date


class PartyStockSummary(models.Model):
    _name = "party.stock.summary"
    _description = "Partner Stock Summary (Purchase/Sales)"

    date_from = fields.Date(
        string="Start Date",
        default=lambda self: date.today().replace(month=1, day=1)
    )
    date_to = fields.Date(
        string="End Date",
        default=lambda self: date.today()
    )
    partner_id = fields.Many2one("res.partner", string="Partner (Optional)")
    product_id = fields.Many2one("product.product", string="Product (Optional)")
    stock_summary_html = fields.Html(
        string="Partner Stock Summary",
        compute="_compute_stock_summary",
        store=False
    )

    @api.depends("date_from", "date_to", "partner_id", "product_id")
    def _compute_stock_summary(self):
        SaleOrderLine = self.env["sale.order.line"].sudo()
        PurchaseOrderLine = self.env["purchase.order.line"].sudo()

        column_widths = ["20%", "15%", "15%", "15%", "15%", "20%"]  # total 100%

        for rec in self:
            sale_domain = [("order_id.state", "in", ["sale", "done"])]
            purchase_domain = [("order_id.state", "in", ["purchase", "done"])]

            if rec.date_from:
                sale_domain.append(("order_id.date_order", ">=", rec.date_from))
                purchase_domain.append(("order_id.date_order", ">=", rec.date_from))
            if rec.date_to:
                sale_domain.append(("order_id.date_order", "<=", rec.date_to))
                purchase_domain.append(("order_id.date_order", "<=", rec.date_to))
            if rec.partner_id:
                sale_domain.append(("order_id.partner_id", "=", rec.partner_id.id))
                purchase_domain.append(("order_id.partner_id", "=", rec.partner_id.id))
            if rec.product_id:
                sale_domain.append(("product_id", "=", rec.product_id.id))
                purchase_domain.append(("product_id", "=", rec.product_id.id))

            sale_lines = SaleOrderLine.search(sale_domain)
            purchase_lines = PurchaseOrderLine.search(purchase_domain)

            summary = {}
            for line in sale_lines:
                partner = line.order_id.partner_id
                product = line.product_id
                if not partner or not product:
                    continue
                summary.setdefault(partner, {})
                if product not in summary[partner]:
                    summary[partner][product] = {
                        "sold_qty": 0.0,
                        "bought_qty": 0.0,
                        "sold_price": 0.0,
                        "bought_price": 0.0,
                    }
                summary[partner][product]["sold_qty"] += line.product_uom_qty
                summary[partner][product]["sold_price"] += line.product_uom_qty * line.price_unit

            for line in purchase_lines:
                partner = line.order_id.partner_id
                product = line.product_id
                if not partner or not product:
                    continue
                summary.setdefault(partner, {})
                if product not in summary[partner]:
                    summary[partner][product] = {
                        "sold_qty": 0.0,
                        "bought_qty": 0.0,
                        "sold_price": 0.0,
                        "bought_price": 0.0,
                    }
                summary[partner][product]["bought_qty"] += line.product_qty
                summary[partner][product]["bought_price"] += line.product_qty * line.price_unit

            html_sections = ""
            for partner, products in summary.items():
                partner_bought_qty_total = 0.0
                partner_bought_price_total = 0.0
                partner_sold_qty_total = 0.0
                partner_sold_price_total = 0.0

                # Wrap table in a div with margin-bottom
                html_sections += "<div style='margin-bottom:20px;'>"

                # Grey row for partner name
                html_sections += (
                    "<table cellpadding='4' cellspacing='0' "
                    "style='border-collapse:collapse; font-size:12px; width:100%; text-align:left;'>"
                )
                html_sections += (
                    f"<tr style='background:#d9d9d9; font-weight:bold;'>"
                    f"<td colspan='6' style='border:1px solid black; padding:6px;'>{partner.display_name}</td>"
                    f"</tr>"
                )

                # Column headers
                html_sections += "<tr style='background:#f5f5f5; font-weight:bold;'>"
                headers = ["Product", "Category", "Quantity Bought From", "Buying Price", "Quantity Sold To", "Selling Price"]
                for idx, header in enumerate(headers):
                    html_sections += f"<th style='border:1px solid black; width:{column_widths[idx]};'>{header}</th>"
                html_sections += "</tr>"

                for product, vals in products.items():
                    partner_bought_qty_total += vals['bought_qty']
                    partner_bought_price_total += vals['bought_price']
                    partner_sold_qty_total += vals['sold_qty']
                    partner_sold_price_total += vals['sold_price']

                    html_sections += "<tr style='background:white;'>"
                    cells = [
                        product.display_name,
                        product.categ_id.name or 'N/A',
                        f"{vals['bought_qty']:.2f}",
                        f"{vals['bought_price']:.2f}",
                        f"{vals['sold_qty']:.2f}",
                        f"{vals['sold_price']:.2f}",
                    ]
                    for idx, cell in enumerate(cells):
                        html_sections += f"<td style='border:1px solid black; width:{column_widths[idx]};'>{cell}</td>"
                    html_sections += "</tr>"

                # Partner total row
                html_sections += "<tr style='background:white; font-weight:bold;'>"
                total_cells = [
                    "Total:",
                    "",
                    f"{partner_bought_qty_total:.2f}",
                    f"{partner_bought_price_total:.2f}",
                    f"{partner_sold_qty_total:.2f}",
                    f"{partner_sold_price_total:.2f}",
                ]
                for idx, cell in enumerate(total_cells):
                    html_sections += f"<td style='border:1px solid black; width:{column_widths[idx]}; text-align:{'right' if idx in [0,2,3,4,5] else 'left'};'>{cell}</td>"
                html_sections += "</tr>"

                html_sections += "</table>"
                html_sections += "</div>"  # margin-bottom wraps the table

            rec.stock_summary_html = (
                f"<div style='display:block; width:100%;'>{html_sections}</div>"
                or "<p>No data found.</p>"
            )


    def action_export_xlsx(self):
        return {
            "type": "ir.actions.act_url",
            "url": f"/party_stock_summary/export_xlsx?record_id={self.id}",
            "target": "self",
        }
