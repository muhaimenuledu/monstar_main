from odoo import models, fields, api

class ResPartner(models.Model):
    _inherit = "res.partner"

    vendor_group = fields.Selection(
        selection=lambda self: self._get_vendor_groups(),
        string="Vendor Group",
        help="Select a group name for this vendor."
    )

    @api.model
    def _get_vendor_groups(self):
        groups = self.env['beta.mode'].search([])
        return [(g.id, g.group) for g in groups if g.group]
