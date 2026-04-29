from odoo import models, fields, api

class ServiceOrderLine(models.Model):
    # _name: Tên bảng lưu trữ các dòng chi tiết. Trong database sẽ là 'service_order_line'.
    _name = 'service.order.line'
    _description = 'Service Order Line'

    # --- ĐỊNH NGHĨA CÁC MỐI QUAN HỆ (RELATIONS) ---

    # fields.Many2one: Liên kết 'N-1' ngược lại đơn hàng cha.
    # ondelete='cascade': Đây là quy tắc dọn dẹp database.
    # Ý nghĩa: Nếu bạn xóa đơn hàng cha (Service Order), các dòng con này sẽ tự động bị xóa theo. 
    # Nếu không có dòng này, database sẽ bị lỗi 'rác' (dòng con mồ côi).
    order_id = fields.Many2one(
        'service.order', 
        string='Service Order', 
        ondelete='cascade', 
        required=True # Bắt buộc phải thuộc về một đơn hàng nào đó.
    )
    
    # product_id: Liên kết đến danh mục sản phẩm của Odoo.
    # domain=[('type', '=', 'service')]: Bộ lọc thông minh. 
    # Nó chỉ cho phép chọn những sản phẩm được đánh dấu là 'Dịch vụ' (Service), ẩn các hàng hóa vật lý.
    product_id = fields.Many2one(
        'product.product', 
        string='Product', 
        domain=[('type', '=', 'service')]
    )
    
    # fields.Selection: Phân loại nhanh loại hình dịch vụ.
    # Giúp bạn sau này có thể thống kê: "Tháng này có bao nhiêu đơn Sửa chữa, bao nhiêu đơn Lắp đặt?".
    service_type = fields.Selection([
        ('installation', 'Lắp đặt'),
        ('repair', 'Sửa chữa'),
        ('consulting', 'Tư vấn'),
    ], string='Loại', required=True, default='installation')

    # fields.Text: Mô tả chi tiết công việc cụ thể cho dòng này.
    name = fields.Text(string='Description')
    
    # --- THÔNG SỐ VÀ GIÁ CẢ ---
    
    # digits='Product Unit of Measure': Quy định số chữ số thập phân sau dấu phẩy (ví dụ: 1.000).
    # Odoo sẽ lấy cấu hình này từ phần Settings của hệ thống.
    quantity = fields.Float(string='Quantity', default=1.0, digits='Product Unit of Measure')
    
    # digits='Product Price': Tương tự như trên nhưng áp dụng cho đơn giá tiền tệ.
    price_unit = fields.Float(string='Unit Price', digits='Product Price', default=0.0)
    
    # fields.Float: Giảm giá theo tỷ lệ phần trăm (%).
    discount = fields.Float(string='Discount (%)', default=0.0)
    
    # related='order_id.currency_id': Đây là tính năng 'Đồng bộ dữ liệu'.
    # Ý nghĩa: Dòng con sẽ tự động lấy loại tiền tệ (VNĐ, USD) từ đơn hàng cha. 
    # Bạn không cần phải chọn lại tiền tệ cho từng dòng.
    # store=True: Lưu vào DB để hỗ trợ tính toán nhanh hơn.
    currency_id = fields.Many2one(related='order_id.currency_id', store=True, string='Currency', readonly=True)
    
    # fields.Monetary: Thành tiền sau khi đã trừ chiết khấu.
    price_subtotal = fields.Monetary(compute='_compute_amount', string='Subtotal', store=True)

    # --- CÁC HÀM XỬ LÝ TỰ ĐỘNG (TRIGGERS) ---

    # @api.onchange: Đây là hàm 'Tương tác thời gian thực' (Real-time).
    # Nó chạy ngay khi bạn vừa chọn sản phẩm trên màn hình (chưa cần bấm Save).
    @api.onchange('product_id')
    def _onchange_product_id(self):
        """Tự động điền thông tin khi người dùng chọn một dịch vụ"""
        if self.product_id:
            # get_product_multiline_description_sale(): Hàm tiêu chuẩn của Odoo 
            # để lấy mô tả đầy đủ của sản phẩm (bao gồm cả các ghi chú bán hàng).
            self.name = self.product_id.get_product_multiline_description_sale()
            
            # lst_price: Giá bán niêm yết trong danh mục sản phẩm.
            self.price_unit = self.product_id.lst_price
        else:
            # Nếu xóa sản phẩm thì reset giá về 0.
            self.price_unit = 0.0

    # @api.depends: Hàm tính toán 'Thành tiền'.
    # Nó sẽ chạy lại mỗi khi 1 trong 3 trường (Số lượng, Đơn giá, Giảm giá) bị thay đổi.
    @api.depends('quantity', 'price_unit', 'discount')
    def _compute_amount(self):
        """Công thức tính toán: (Số lượng * Đơn giá) - Tỷ lệ giảm giá"""
        for line in self:
            # Công thức: Thành tiền = (Số lượng * Giá) * (100% - %Giảm giá)
            line.price_subtotal = line.quantity * line.price_unit * (1 - line.discount / 100)
