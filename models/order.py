# -- Import các thư viện cần thiết từ core Odoo --
from odoo import models, fields, api
from odoo.exceptions import ValidationError

class ServiceOrder(models.Model):
    # _name: Định danh model trong toàn hệ thống Odoo. 
    # Khi cài module, Odoo sẽ tạo bảng 'service_order' (thay '.' bằng '_') trong database PostgreSQL.
    _name = 'service.order'
    
    # _description: Tên mô tả của model, dùng trong các thông báo lỗi hoặc log hệ thống.
    _description = 'Service Order'
    
    # _inherit: Kế thừa tính năng từ các module khác.
    # - 'mail.thread': Cung cấp khả năng lưu lịch sử (Chatter) và gửi email.
    # - 'mail.activity.mixin': Cung cấp khả năng tạo lịch nhắc việc (Activities) như Gọi điện, Họp.
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    # _order: Cách sắp xếp danh sách bản ghi. 'id desc' nghĩa là bản ghi mới nhất hiện lên đầu.
    _order = 'id desc'

    # --- ĐỊNH NGHĨA CÁC TRƯỜNG DỮ LIỆU (FIELDS) ---

    # fields.Char: Kiểu chuỗi ký tự ngắn.
    # copy=False: Khi nhân bản (Duplicate) đơn hàng, trường này sẽ KHÔNG được copy sang đơn mới.
    # readonly=True: Chỉ đọc, ngăn người dùng nhập tay để tránh làm sai lệch số thứ tự hệ thống.
    name = fields.Char(
        string='Order Code', 
        required=True, 
        copy=False, 
        readonly=True, 
        default='New' # Giá trị tạm thời trước khi được gán số thực tế
    )
    
    # fields.Many2one: Tạo mối quan hệ N-1 (Nhiều đơn hàng có thể thuộc về 1 khách hàng).
    # tracking=True: Bật tính năng 'Theo dõi'. Mỗi khi đổi khách hàng, Chatter sẽ tự động ghi lại log.
    partner_id = fields.Many2one(
        'service.order.partner', 
        string='Customer', 
        tracking=True # Log lại: "Khách hàng: A -> B"
    )

    # fields.Datetime: Lưu trữ cả ngày và giờ.
    # default=fields.Datetime.now: Gọi hàm lấy giờ hiện tại mỗi khi bấm 'Tạo mới'.
    # Tại sao dùng hàm này mà không dùng datetime.now(): Vì Odoo sẽ tính toán đúng múi giờ của user.
    order_date = fields.Datetime(
        string='Order Date', 
        default=fields.Datetime.now, 
        tracking=True
    )
    
    # fields.Selection: Tạo danh sách chọn cố định.
    # Mỗi tuple gồm (Giá trị lưu DB, Tên hiển thị).
    state = fields.Selection([
        ('draft', 'Draft'),         # Nháp: Đang soạn thảo, chưa có hiệu lực.
        ('sent', 'Sent'),           # Đã gửi: Đã gửi email báo giá cho khách hàng.
        ('confirmed', 'Confirmed'), # Đã xác nhận: Khách hàng đã đồng ý, bắt đầu thực hiện.
        ('cancelled', 'Cancelled'), # Đã hủy: Đơn lỗi hoặc khách từ chối.
    ], string='Status', default='draft', tracking=True)

    # fields.One2many: Tạo mối quan hệ 1-N (1 đơn hàng có nhiều dòng chi tiết).
    # 'order_id': Tên trường Many2one bên model 'service.order.line' dùng để liên kết ngược lại.
    line_ids = fields.One2many(
        'service.order.line', 
        'order_id', 
        string='Service Lines', 
        copy=True # Khi nhân bản đơn hàng, các dòng chi tiết cũng được nhân bản theo.
    )

    # fields.Monetary: Kiểu dữ liệu tiền tệ chuyên dụng. 
    # Nó sẽ tự động đi kèm ký hiệu tiền tệ (đ, $, €) dựa trên currency_id.
    currency_id = fields.Many2one(
        'res.currency', 
        string='Currency', 
        # lambda self: Một hàm ẩn danh chạy ngay lập tức để lấy tiền tệ mặc định của công ty user.
        default=lambda self: self.env.company.currency_id 
    )
    
    # compute='_amount_all': Trường tính toán. Odoo sẽ gọi hàm _amount_all để điền giá trị.
    # store=True: Lưu kết quả vào database. Rất quan trọng để có thể Group-by hoặc làm báo cáo Pivot.
    amount_untaxed = fields.Monetary(string='Untaxed Amount', store=True, compute='_amount_all', tracking=True)
    amount_tax = fields.Monetary(string='Taxes', store=True, compute='_amount_all', tracking=True)
    amount_total = fields.Monetary(string='Total', store=True, compute='_amount_all', tracking=True)
    
    note = fields.Text(string='Note') # fields.Text: Kiểu văn bản dài (ghi chú).

    # --- CÁC HÀM XỬ LÝ LOGIC (METHODS) ---

    # @api.depends: Trang trí cho hàm compute.
    # Nó báo cho Odoo: "Này, nếu bất kỳ dòng con (line_ids) nào bị thay đổi thành tiền (price_subtotal), hãy chạy lại hàm này ngay!".
    @api.depends('line_ids.price_subtotal')
    def _amount_all(self):
        """Hàm tính toán tổng tiền của đơn hàng"""
        for rec in self:
            # sum(): Cộng dồn tất cả price_subtotal của danh sách dòng chi tiết.
            untaxed = sum(line.price_subtotal for line in rec.line_ids)
            tax = untaxed * 0.01  # Tính thuế 1% (Thuế Ato).
            
            # rec.update: Cập nhật giá trị vào các trường compute. 
            # Dùng update() sẽ nhanh hơn gán trực tiếp (rec.field = value) khi cập nhật nhiều trường.
            rec.update({
                'amount_untaxed': untaxed,
                'amount_tax': tax,
                'amount_total': untaxed + tax,
            })

    # @api.model_create_multi: Tối ưu hóa hiệu năng khi tạo nhiều bản ghi cùng lúc.
    @api.model_create_multi
    def create(self, vals_list):
        """Hàm chạy khi nhấn nút Save lần đầu tiên"""
        for vals in vals_list:
            # Kiểm tra nếu name đang là 'New' thì mới sinh số mới.
            if vals.get('name', 'New') == 'New':
                # self.env['ir.sequence']: Gọi đến bộ sinh số tự động trong Odoo.
                vals['name'] = self.env['ir.sequence'].next_by_code('service.order') or 'New'
        
        # super(): Gọi hàm create gốc của Odoo để thực hiện việc lưu vào database.
        return super(ServiceOrder, self).create(vals_list)

    def action_confirm(self):
        """Hàm xử lý khi bấm nút Confirm"""
        for rec in self:
            if not rec.line_ids:
                # raise ValidationError: Bật thông báo lỗi màu đỏ trên màn hình và chặn không cho thực hiện tiếp.
                raise ValidationError("Please add at least one service line before confirming!")
            
            # Thay đổi trạng thái
            rec.state = 'confirmed'
            
            # Gửi thông báo tự động (Hàm này đã được viết để post vào Chatter)
            rec._send_notification('service_order.email_template_confirm')

    def action_send(self):
        """Hàm xử lý khi bấm nút Send"""
        for rec in self:
            if not rec.partner_id:
                raise ValidationError('Please select a Customer before sending!')
            rec.state = 'sent'
            rec._send_notification('service_order.email_template_send')

    def action_cancel(self):
        # self.write: Cách cập nhật dữ liệu hàng loạt cho nhiều bản ghi cùng lúc.
        self.write({'state': 'cancelled'})

    def action_reset(self):
        self.write({'state': 'draft'})

    def _send_notification(self, template_xml_id):
        """Hàm tiện ích dùng để đăng nội dung Email vào Chatter"""
        for rec in self:
            # self.env.ref: Tìm kiếm bản ghi email template dựa trên ID đã khai báo trong XML.
            template = self.env.ref(template_xml_id, raise_if_not_found=False)
            if template:
                # message_post_with_source: Tính năng cao cấp của Odoo.
                # Nó sẽ render template (điền tên khách, mã đơn...) rồi 'Dán' vào Chatter như một tin nhắn.
                rec.message_post_with_source(
                    template,
                    subtype_xmlid='mail.mt_comment',
                )
