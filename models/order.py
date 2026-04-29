from odoo import models, fields, api
from odoo.exceptions import ValidationError

class ServiceOrder(models.Model):
    _name = 'service.order'
    _description = 'Service Order'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(
        string='Order Code', 
        required=True, 
        copy=False, 
        readonly=True, 
        default='New'
    )
    
    partner_id = fields.Many2one(
        'service.order.partner', 
        string='Customer', 
        tracking=True
    )

    order_date = fields.Datetime(
        string='Order Date', 
        default=fields.Datetime.now, 
        tracking=True
    )
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    line_ids = fields.One2many(
        'service.order.line', 
        'order_id', 
        string='Service Lines', 
        copy=True
    )

    currency_id = fields.Many2one(
        'res.currency', 
        string='Currency', 
        default=lambda self: self.env.company.currency_id 
    )
    
    amount_untaxed = fields.Monetary(string='Untaxed Amount', store=True, compute='_amount_all', tracking=True)
    amount_tax = fields.Monetary(string='Taxes', store=True, compute='_amount_all', tracking=True)
    amount_total = fields.Monetary(string='Total', store=True, compute='_amount_all', tracking=True)
    
    note = fields.Text(string='Note')

    @api.depends('line_ids.price_subtotal')
    def _amount_all(self):
        for rec in self:
            untaxed = sum(line.price_subtotal for line in rec.line_ids)
            tax = untaxed * 0.01
            rec.update({
                'amount_untaxed': untaxed,
                'amount_tax': tax,
                'amount_total': untaxed + tax,
            })

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('service.order') or 'New'
        return super(ServiceOrder, self).create(vals_list)

    def action_confirm(self):
        for rec in self:
            if not rec.line_ids:
                raise ValidationError("Please add at least one service line before confirming!")
            rec.state = 'confirmed'
            rec._send_notification('service_order.email_template_confirm')

    def action_send(self):
        for rec in self:
            if not rec.partner_id:
                raise ValidationError('Please select a Customer before sending!')
            rec.state = 'sent'
            rec._send_notification('service_order.email_template_send')

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset(self):
        self.write({'state': 'draft'})

    def _send_notification(self, template_xml_id):
        for rec in self:
            template = self.env.ref(template_xml_id, raise_if_not_found=False)
            if template:
                rec.message_post_with_source(
                    template,
                    subtype_xmlid='mail.mt_comment',
                )


