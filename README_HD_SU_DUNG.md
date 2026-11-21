# HƯỚNG DẪN SỬ DỤNG HỆ THỐNG QUẢN LÝ VẬT TƯ & TỒN KHO CÔNG TRÌNH

Hệ thống được thiết kế theo **Phương án B (Chạy trên máy tính văn phòng, kết nối thông suốt từ công trường về văn phòng)**.

---

## 1. KHỞI ĐỘNG HỆ THỐNG TẠI VĂN PHÒNG

Chỉ cần **bấm đúp chuột vào file `start_server.bat`** trong thư mục `E:\TON KHO`.
Cửa sổ màu đen hiện lên thông báo:
- Đường dẫn truy cập tại máy văn phòng: `http://localhost:5000`
- Đường dẫn truy cập trong mạng LAN văn phòng: `http://[IP_MÁY_BẠN]:5000`

---

## 2. DANH SÁCH TÀI KHOẢN & PHÂN QUYỀN

Hệ thống đã tạo sẵn 4 nhóm tài khoản tương ứng với các bộ phận:

| Tên Đăng Nhập | Mật Khẩu | Vai Trò | Phạm Vi Quyền Hạn |
|:---|:---|:---|:---|
| **`admin`** | `admin123` | **Quản Trị Viên (Admin)** | Toàn quyền xem, thêm, sửa, xóa, cấu hình và xem toàn bộ đơn giá, chi phí. |
| **`ketoan`** | `ketoan123` | **Kế Toán / Văn Phòng** | Xem và quản lý bảng Mua vào, Đơn giá, Hợp đồng CĐT, phê duyệt ĐNVT, kiểm soát đối soát kho. |
| **`thukho`** | `thukho123` | **Thủ Kho Công Trường** | Nhập kho (nhập form, upload Excel, quét PDF scan), Lập phiếu xuất cho tổ đội, kiểm kê. **Tự động ẩn toàn bộ đơn giá & thành tiền.** |
| **`kythuat`** | `kythuat123` | **Kỹ Sư Công Trường** | Lập phiếu ĐNVT, theo dõi tiến độ cấp hàng, tra cứu tồn kho thực tế (ẩn đơn giá). |
| **`viewer`** | `viewer123` | **Chỉ Xem (Tổ Đội Dũng...)** | Chỉ xem danh mục vật tư, tồn kho và lịch sử cấp phát cho tổ đội, không được chỉnh sửa. |

*(Trên màn hình Đăng nhập, có sẵn các nút bấm chọn nhanh tài khoản để kiểm thử thuận tiện)*

---

## 3. HƯỚNG DẪN 3 PHƯƠNG THỨC NHẬP LIỆU

### Phương thức 1: Quét file PDF Scan hoặc Ảnh Chụp phiếu giao hàng (AI OCR)
1. Tại menu, chọn **"Nhập Kho & Quét PDF Scan"**.
2. Bấm nút **"Chọn File PDF Scan Hoặc Ảnh Chụp"** (có thể dùng điện thoại chụp trực tiếp phiếu giao hàng từ nhà cung cấp Sino, Bạch Đằng...).
3. Hệ thống tự động bóc tách: Số phiếu, Ngày, Nhà cung cấp, và tự động điền danh sách mã vật tư, tên, số lượng vào form.
4. Thủ kho đối soát nhanh và bấm nút **"LƯU PHIẾU NHẬP & CẬP NHẬT TỒN KHO"**.

### Phương thức 2: Tải lên file Excel hàng loạt
1. Tại khung **"Kênh 2: Tải Lên File Excel Hàng Loạt"**, chọn file Excel (tương thích mẫu file `BẢNG THEO DÕI VẬT TƯ ĐỒNG HÒA.xlsx` hiện có).
2. Bấm nút **"Tải lên"**, hệ thống tự động nạp toàn bộ các dòng nhập kho mới vào cơ sở dữ liệu.

### Phương thức 3: Nhập tay trực tiếp (Web Form)
1. Điền Số phiếu (e.g. `GM02`), ngày nhập, chọn Nhà cung cấp.
2. Tại bảng chi tiết, gõ 2-3 ký tự mã vật tư (e.g. `olsp20`, `vc1x4`...), hệ thống sẽ hiển thị gợi ý autocomplete thông minh để chọn.
3. Nhập số lượng thực nhận và bấm **Lưu**.

---

## 4. HƯỚNG DẪN XUẤT KHO CHO TỔ ĐỘI (CHỐNG XUẤT ÂM)

1. Tại menu, chọn **"Xuất Kho Cho Tổ Đội"**.
2. Chọn Tổ đội nhận (e.g. `Dũng`), người nhận (`Biên`).
3. Chọn mã vật tư: Hệ thống sẽ tự động tra cứu tồn kho khả dụng hiện tại (ví dụ: đang còn `6,278 m`).
4. Nhập số lượng xuất: Hệ thống tự động tính số tồn còn lại. Nếu nhập vượt quá số tồn kho hiện có, hệ thống sẽ báo đỏ cảnh báo và chặn xuất âm.
5. Bấm **"Xác Nhận Xuất Kho Cho Tổ Đội"** để trừ kho tức thì.

---

## 5. HƯỚNG DẪN KẾT NỐI CHO ANH EM Ở CÔNG TRƯỜNG TRUY CẬP (INTERNET / 4G)

Để kỹ sư, thủ kho ở công trường dùng điện thoại/tablet/laptop mở được web máy chủ văn phòng từ xa mà không cần mở cổng modem (Port Forwarding) hay mua IP tĩnh, bạn có thể dùng **Cloudflare Tunnel (Hoàn toàn miễn phí, bảo mật cao)**:

1. Tải công cụ miễn phí **`cloudflared.exe`** từ Cloudflare (https://github.com/cloudflare/cloudflared/releases).
2. Mở cửa sổ Command Prompt trên máy văn phòng và chạy lệnh:
   ```cmd
   cloudflared tunnel --url http://localhost:5000
   ```
3. Cloudflare sẽ tạo ra một đường link HTTPS an toàn miễn phí (ví dụ: `https://vat-tu-dong-hoa.trycloudflare.com`).
4. Bạn chỉ cần gửi đường link này qua Zalo cho anh em công trường là có thể mở web trên điện thoại để tra cứu tồn kho và quét phiếu nhập kho ngay tại công trường!

