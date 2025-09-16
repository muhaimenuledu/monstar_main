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

        for rec in self:
            # Base domains
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

            # Query lines
            sale_lines = SaleOrderLine.search(sale_domain)
            purchase_lines = PurchaseOrderLine.search(purchase_domain)

            # Grouped summary per partner
            summary = {}
            # Sales
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

            # Purchases
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

            # Render HTML row by row
            html_sections = ""
            for partner, products in summary.items():
                html_sections += (
                    "<div style='margin: 10px 0; padding: 10px; background: #f5f5f5; "
                    "border: 1px solid #ccc; border-radius: 5px;'>"
                )
                html_sections += (
                    f"<h4 style='margin: 0 0 10px 0; padding: 6px; background: #e0e0e0;'>{partner.display_name}</h4>"
                )
                html_sections += (
                    "<table border='1' cellpadding='4' cellspacing='0' "
                    "style='border-collapse: collapse; font-size: 12px; width: 100%; text-align: left;'>"
                )
                html_sections += (
                    "<tr style='background:#a0c4ff;'>"
                    "<th>Product</th>"
                    "<th>Category</th>"
                    "<th>Quantity Bought From</th>"
                    "<th>Buying Price</th>"
                    "<th>Quantity Sold To</th>"
                    "<th>Selling Price</th>"
                    "</tr>"
                )
                for product, vals in products.items():
                    html_sections += (
                        "<tr>"
                        f"<td>{product.display_name}</td>"
                        f"<td>{product.categ_id.name or 'N/A'}</td>"
                        f"<td>{vals['bought_qty']:.2f}</td>"
                        f"<td>{vals['bought_price']:.2f}</td>"
                        f"<td>{vals['sold_qty']:.2f}</td>"
                        f"<td>{vals['sold_price']:.2f}</td>"
                        "</tr>"
                    )
                html_sections += "</table></div>"

            rec.stock_summary_html = (
                f"<div style='display: block; width: 100%;'>{html_sections}</div>"
                or "<p>No data found.</p>"
            )

    def action_export_xlsx(self):
        return {
            "type": "ir.actions.act_url",
            "url": f"/party_stock_summary/export_xlsx?record_id={self.id}",
            "target": "self",
        }
