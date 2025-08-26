from odoo import api, models, fields

class Beta(models.Model):
    _name = 'beta.mode'
    _description = "Mixed Uses"

    group = fields.Char(string="Vendor Group")

    