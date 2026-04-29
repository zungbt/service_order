from odoo import models, fields


class ServiceOrderPartner(models.Model):
    _name = 'service.order.partner'
    _description = 'Service Order Partner'

    name = fields.Char(string='Name', required=True)
    phone = fields.Char(string='Phone')
    email = fields.Char(string='Email')
    address = fields.Text(string='Address')
