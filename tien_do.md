# NHẬT KÝ TIẾN ĐỘ TRIỂN KHAI PHẦN MỀM QUẢN LÝ TỒN KHO BIGCOM

---

## 1. TIẾN ĐỘ HIỆN TẠI (ĐÃ HOÀN THÀNH)

- [x] **Cơ chế Khởi động Tự động mở Trình duyệt**:
  - Cập nhật [start_server.bat](file:///e:/TON%20KHO/start_server.bat): Tự động bật trình duyệt mặc định đến `http://localhost:5000` ngay sau khi kích hoạt máy chủ.
  - Tích hợp bộ mở trình duyệt dự phòng thông minh `webbrowser` trong [app.py](file:///e:/TON%20KHO/app.py).
- [x] **Cập nhật Màu sắc Nhận diện Thương hiệu**:
  - Thanh Sidebar chuyển sang màu xanh dương thương hiệu Bigcom M&E (`#195faa`), kết hợp màu xanh đậm `#124782` khi hover/active.
  - Logo Bigcom M&E nổi bật trên nền trắng đầu sidebar.
- [x] **Đồng bộ duy nhất 1 Font chữ toàn hệ thống**:
  - Áp dụng font chữ chuẩn công sở `'Segoe UI', -apple-system, Roboto, sans-serif` đồng nhất cho toàn bộ giao diện, tiêu đề, bảng biểu, mã vật tư và các con số.
- [x] **Làm tròn số liệu (Không để số thập phân)**:
  - Toàn bộ số lượng tồn kho, hợp đồng, nhập kho, xuất kho, xuất tổ đội đều được làm tròn thành số nguyên và hiển thị có phân cách hàng nghìn (ví dụ: `7,227`, `14,600`).
  - File Excel xuất ra cũng được cấu hình định dạng `#,##0` nguyên bản.
- [x] **Số phiếu tự động chờ ở số tiếp theo**:
  - Phiếu nhập kho: Tự động phát hiện số lớn nhất trong CSDL và điền sẵn số kế tiếp (ví dụ: `GM03`, `GM04`...).
  - Phiếu xuất kho: Tự động phát hiện số lớn nhất và điền sẵn số kế tiếp (ví dụ: `PXK07`, `PXK08`...).
- [x] **Bảng dữ liệu kéo trượt 2 chiều**: Cố định tiêu đề khi cuộn dọc (Sticky Header), kéo trượt ngang mượt mà, nút `[ 📄 Xem chi tiết ]` mở Modal xem đầy đủ lịch sử.
- [x] **Phân hệ Đối soát CĐT / Thầu chính (ĐNVT)**:
  - Khởi tạo bảng `material_requests` lưu trữ toàn bộ các đợt Đề nghị vật tư gửi CĐT / Thầu chính (khởi đầu với 25 dòng từ phiếu `PYC01`).
  - Giao diện đối soát chuẩn mẫu sheet ĐNVT: hiển thị Đợt yêu cầu, Ngày đề nghị, Mã VT, Tên vật tư, ĐVT, Khối lượng Hợp đồng (BOQ), SL Yêu cầu, SL Thực nhận (tính thời gian thực từ Nhập kho liên kết mã phiếu) và Cột Chênh lệch (màu cảnh báo âm/dương).
  - Tự động gợi ý mã phiếu kế tiếp (`PYC02`), hỗ trợ thêm mới đợt yêu cầu và xuất Excel đối soát ĐNVT.
  - Tích hợp liên kết điều hướng trên Sidebar và thanh Tab phân hệ kho.
- [x] **Cập nhật Bảng 'Tổng hợp tồn kho' & Quản lý Tổ đội Mở rộng**:
  - Đầy đủ các cột chuẩn xác theo yêu cầu: `Mã VT` - `Tên Vật Tư` - `Hãng` - `Đơn vị` - `KL Hợp đồng` - `KL Yêu cầu` - `KL Nhập` - `KL Xuất` - `Tồn kho` - `Xuất Dũng`, `Xuất Tổ 1`, `Xuất Tổ 2`, `Xuất Tổ 3`... (cột tổ đội được thiết kế động, tự động mở rộng khi phát sinh thêm tổ đội mới mà không cần sửa code).
  - Tích hợp nút **`+ Thêm Mã Vật Tư`** mở Modal với 2 chế độ:
    + **Nhập tay 1 mã**: Bổ sung nhanh mã vật tư phát sinh ngoài công trường.
    + **Nạp hàng loạt từ Excel**: Tải file mẫu chuẩn Bigcom (`Mau_Danh_Sach_Vat_Tu_Bigcom.xlsx`), điền danh sách và tải lên để nạp hàng loạt mã chỉ trong 1 giây (tự động nhận diện và cập nhật nếu mã đã tồn tại).
  - Báo cáo xuất Excel (`/xuat-bao-cao-excel`) cũng được đồng bộ tự động xuất đầy đủ tất cả các cột tổ đội động với số liệu làm tròn số nguyên (`#,##0`).
- [x] **Cơ chế Chống Trùng Mã & Chặn Ghi Đè Nghiêm Ngặt**:
  - Khi thêm mã vật tư mới (cả nhập tay và nạp từ Excel), hệ thống tự động kiểm tra đối chiếu mã trong danh mục.
  - Nếu mã đã tồn tại: Cảnh báo chuẩn xác **"Đã có mã trong danh mục"**, tuyệt đối **KHÔNG cho phép ghi đè** dữ liệu cũ và **KHÔNG tự ý tạo mã mới**.
  - Kiểm tra tức thời (Real-time) trên Form nhập tay: Hiển thị cảnh báo đỏ và tự động khóa nút Lưu khi phát hiện mã trùng.
  - Khi nạp hàng loạt từ file Excel: Tự động bỏ qua các mã đã có, chỉ thêm các mã mới và thông báo danh sách chi tiết các mã bị bỏ qua để bảo vệ dữ liệu lịch sử.
- [x] **Cập nhật Phân hệ 'Nhập kho' & Cửa sổ Nhập Vật Tư Thông Minh**:
  - Đổi tên tiêu đề trang, breadcrumb, menu sidebar và thanh tab điều hướng thành **"Nhập kho"**.
  - Giao diện chính là **Bảng Lịch Sử Nhập Kho** rộng rãi, cuộn 2 chiều với Sticky Header, đầy đủ các cột: STT, Số Phiếu, Ngày Nhập, Mã VT, Tên Chi Tiết Vật Tư, Hãng, ĐVT, Số Lượng (làm tròn số nguyên), Nhà Cung Cấp / CĐT, Theo Phiếu YC, Ghi Chú, Người Nhập.
  - Tích hợp 2 nút hành động: **`+ Nhập vật tư`** (mở cửa sổ popup) và **`📥 Xuất Excel`** (xuất báo cáo lịch sử nhập kho chuẩn định dạng `#,##0`).
  - Cửa sổ Popup "Nhập vật tư" tích hợp 3 kênh: 1. Nhập trực tiếp form, 2. Tải file Excel, 3. Quét PDF scan / AI OCR.
  - Trong form nhập trực tiếp: Cho phép **nhập bằng Tên chi tiết vật tư** (gợi ý thông minh autocomplete từ khóa) hoặc Mã vật tư, tự động điền đồng bộ 2 chiều (Mã <-> Tên, Hãng, ĐVT).
  - Mở rộng kích thước Modal "Nhập vật tư vào kho" lên khổ lớn (`max-w-6xl`, chiều cao bảng `max-h-[50vh]`), thêm cột **STT** tự động đánh số 1, 2, 3... liên tục khi thêm hoặc xóa dòng vật tư.
  - Căn giữa ô (`text-center`) cho cột Tên Hãng và Nhà Cung Cấp / CĐT ở cả bảng hiển thị web và file Excel xuất ra.
- [x] **Cập nhật Phân hệ 'Xuất kho' & Quản Lý Tổ Đội Động Linh Hoạt**:
  - Đổi tên tiêu đề trang, breadcrumb, menu sidebar và thanh tab điều hướng thành **"Xuất kho"**.
  - Giao diện chính hiển thị **Bảng Lịch Sử Xuất Kho** chuyên nghiệp, cuộn 2 chiều với Sticky Header, đầy đủ các cột: STT, Số Phiếu, Ngày Xuất, Mã VT, Tên Chi Tiết Vật Tư, Hãng (căn giữa), ĐVT (căn giữa), Số Lượng Xuất (nổi bật màu hổ phách, làm tròn số nguyên `#,##0`), Tổ Đội Nhận (căn giữa), Người Nhận Bàn Giao (căn giữa), Ghi Chú Vị Trí / Hạng Mục, Người Xuất.
  - Tích hợp 2 nút hành động: **`+ Xuất vật tư`** (mở cửa sổ popup kích thước lớn) và **`📥 Xuất Excel`** (xuất toàn bộ lịch sử xuất kho cấp phát ra file Excel chuẩn Bigcom với định dạng `#,##0`).
  - Cửa sổ Popup "Xuất vật tư" mở rộng khổ lớn (`max-w-6xl`), có đầy đủ cột **STT** tự động cập nhật liên tục khi thêm hoặc xóa dòng, căn giữa cột Hãng và ĐVT.
  - Hỗ trợ nhập và tìm kiếm vật tư thông minh bằng cả **Tên chi tiết vật tư** lẫn **Mã vật tư** (đồng bộ 2 chiều dữ liệu tên, mã, hãng, đơn vị và kiểm tra số dư tồn khả dụng thời gian thực).
  - Tích hợp cơ chế **Chống Xuất Âm Kho**: Tự động tính toán số dư tồn sau xuất, hiển thị cảnh báo đỏ và khóa dòng xuất nếu số lượng xuất vượt quá tồn khả dụng.
  - **Quản lý Tổ đội nhận động**:
    + Nút `[ ⚙️ Quản lý Tổ đội ]` cho phép thêm mới và xóa bớt các tổ đội nhận vật tư theo nhu cầu thực tế ngoài công trường.
    + Khi thêm/xóa tổ đội, hệ thống lập tức cập nhật dữ liệu vào cơ sở dữ liệu và đồng bộ trực tiếp lên danh sách chọn, bộ lọc và các cột tổ đội của bảng Tổng hợp tồn kho mà không cần sửa code.
- [x] **Kiểm thử tự động (`test_app.py`)**: Toàn bộ 25/25 bài test tích hợp đều đạt tỷ lệ thành công 100%.

---

## 2. HƯỚNG DẪN KHỞI ĐỘNG 1 BẤM

Bạn chỉ cần **bấm đúp chuột vào file `start_server.bat`**, máy chủ sẽ tự khởi chạy và **tự động mở luôn trình duyệt web** đưa bạn vào trang đăng nhập của phần mềm mà không cần gõ địa chỉ thủ công!
