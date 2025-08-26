from odoo import models, fields

class ResPartner(models.Model):
    _inherit = "res.partner"

    vendor_group = fields.Char(
        string="Vendor Group",
        help="Type a group name for this vendor."
    )
