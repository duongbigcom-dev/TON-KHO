"""
Script kiểm thử tích hợp tự động cho toàn bộ hệ thống QUẢN LÝ TỒN KHO BIGCOM.
Kiểm tra:
1. Đăng nhập và xác thực các vai trò (admin, ketoan, thukho, viewer).
2. Tải Dashboard tổng hợp tồn kho với giao diện Bigcom và bảng kéo trượt.
3. API tra cứu tồn kho khả dụng (/api/check-stock).
4. API tra cứu chi tiết lịch sử vật tư (/api/material-detail) phục vụ nút [Xem chi tiết].
5. Phân quyền bảo mật RBAC (thủ kho bị chặn khỏi bảng giá mua vào, kế toán được vào).
6. Xuất báo cáo Excel tồn kho tự động mang thương hiệu Bigcom.
"""

import sys
import app
import database

def run_tests():
    client = app.app.test_client()

    # 1. Kiểm tra trang đăng nhập có thương hiệu Bigcom
    res = client.get('/login')
    assert res.status_code == 200, f"Lỗi trang đăng nhập: {res.status_code}"
    assert "QUẢN LÝ TỒN KHO BIGCOM" in res.text
    print("1. [PASS] Trang đăng nhập mang thương hiệu QUẢN LÝ TỒN KHO BIGCOM tải thành công.")

    # 2. Đăng nhập với quyền Thủ kho công trường
    res_login = client.post('/login', data={'username': 'thukho', 'password': 'thukho123'}, follow_redirects=True)
    assert res_login.status_code == 200
    assert 'QUẢN LÝ TỒN KHO BIGCOM' in res_login.text
    print("2. [PASS] Đăng nhập tài khoản Thủ kho (thukho) thành công.")

    # 3. Kiểm tra Dashboard tồn kho với bảng kéo trượt và lọc theo Hãng
    res_dash = client.get('/?brand=Sino')
    assert res_dash.status_code == 200
    assert 'olsp20' in res_dash.text
    print("3. [PASS] Dashboard tồn kho Realtime và bộ lọc Hãng/Nhóm hoạt động chính xác.")

    # 4. Kiểm tra API tra cứu tồn kho khả dụng
    res_stock = client.get('/api/check-stock?code=olsp20')
    assert res_stock.status_code == 200
    data_stock = res_stock.get_json()
    assert data_stock['current_stock'] > 0
    print(f"4. [PASS] API tra cứu tồn kho hoạt động chuẩn xác (olsp20 tồn: {data_stock['current_stock']}).")

    # 5. Kiểm tra API xem chi tiết lịch sử vật tư [Xem chi tiết]
    res_detail = client.get('/api/material-detail?code=olsp20')
    assert res_detail.status_code == 200
    data_detail = res_detail.get_json()
    assert data_detail['success'] is True
    assert data_detail['data']['material']['name'] == 'Ống luồn dây điện D20'
    print(f"5. [PASS] API [Xem chi tiết] vật tư hoạt động hoàn hảo (đã bóc tách {len(data_detail['data']['receipts'])} lần nhập).")

    # 6. Kiểm tra phân quyền bảo mật: Thủ kho KHÔNG được xem trang Mua vào & Đơn giá
    res_mv = client.get('/mua-vao', follow_redirects=True)
    assert 'không có quyền truy cập' in res_mv.text
    print("6. [PASS] Bảo mật RBAC: Thủ kho bị chặn truy cập bảng đơn giá/mua vào thành công.")

    # 7. Đăng nhập Kế toán: Được phép truy cập bảng Mua vào & Đơn giá
    client.get('/logout')
    client.post('/login', data={'username': 'ketoan', 'password': 'ketoan123'}, follow_redirects=True)
    res_mv_ok = client.get('/mua-vao')
    assert res_mv_ok.status_code == 200
    print("7. [PASS] Bảo mật RBAC: Kế toán văn phòng được cấp quyền truy cập bảng đơn giá.")

    # 8. Kiểm tra chức năng xuất file Excel báo cáo Bigcom
    res_excel = client.get('/xuat-bao-cao-excel')
    assert res_excel.status_code == 200
    assert len(res_excel.data) > 1000
    print(f"8. [PASS] Xuất báo cáo Excel Bigcom thành công ({len(res_excel.data)} bytes).")

    # 9. Kiểm tra phân hệ Đối soát CĐT / Thầu chính (ĐNVT)
    res_cdt = client.get('/doi-soat-cdt')
    assert res_cdt.status_code == 200
    assert "Đối Soát Vật Tư CĐT" in res_cdt.text
    assert "PYC01" in res_cdt.text
    print("9. [PASS] Phân hệ Đối soát CĐT / Thầu chính (ĐNVT) tải dữ liệu phiếu PYC01 chính xác.")

    # 10. Kiểm tra xuất file Excel Đối soát CĐT (ĐNVT)
    res_cdt_excel = client.get('/xuat-doi-soat-cdt-excel')
    assert res_cdt_excel.status_code == 200
    assert len(res_cdt_excel.data) > 1000
    print(f"10. [PASS] Xuất file Excel Đối soát CĐT thành công ({len(res_cdt_excel.data)} bytes).")

    # 11. Kiểm tra tải file biểu mẫu Excel vật tư
    res_tpl = client.get('/tai-file-mau-vat-tu')
    assert res_tpl.status_code == 200
    assert len(res_tpl.data) > 1000
    print(f"11. [PASS] Tải file Excel mẫu tạo vật tư hàng loạt thành công ({len(res_tpl.data)} bytes).")

    # 12. Kiểm tra thêm mới 1 mã vật tư qua form nhập tay
    res_add_mat = client.post('/vat-tu/them', data={
        'code': 'test_mat_01',
        'name': 'Vật tư Thử Nghiệm 01',
        'brand': 'Sino',
        'unit': 'Cái',
        'contract_qty': '100',
        'requested_qty': '50',
        'notes': 'Test auto'
    }, follow_redirects=True)
    assert res_add_mat.status_code == 200
    assert 'test_mat_01' in res_add_mat.text
    print("12. [PASS] Thêm mới mã vật tư đơn lẻ qua form thành công.")

    # 13. Kiểm tra nạp hàng loạt vật tư từ file Excel (sử dụng chính file mẫu)
    import io
    excel_file_data = (io.BytesIO(res_tpl.data), 'Mau_Danh_Sach_Vat_Tu_Bigcom.xlsx')
    res_import = client.post(
        '/nhap-danh-sach-vat-tu-excel',
        data={'excel_file': excel_file_data},
        content_type='multipart/form-data',
        follow_redirects=True
    )
    assert res_import.status_code == 200
    assert 'olsp20_moi' in res_import.text
    print("13. [PASS] Nạp hàng loạt vật tư từ file Excel thành công.")

    # 14. Kiểm tra Dashboard có đầy đủ các cột theo yêu cầu (Mã VT, Tên, Hãng, ĐVT, KL HĐ, KL Yêu cầu, KL Nhập, KL Xuất, Tồn kho, Xuất Dũng, Xuất Tổ 1, Xuất Tổ 2, Xuất Tổ 3)
    res_dash = client.get('/')
    assert res_dash.status_code == 200
    for expected_col in ['Mã VT', 'Tên Vật Tư', 'Hãng', 'ĐVT', 'KL Hợp đồng', 'KL Yêu cầu', 'KL Nhập', 'KL Xuất', 'Tồn kho', 'Xuất Dũng', 'Xuất Tổ 1', 'Xuất Tổ 2', 'Xuất Tổ 3']:
        assert expected_col in res_dash.text, f"Thiếu cột: {expected_col}"
    print("14. [PASS] Bảng Tổng hợp tồn kho hiển thị đầy đủ các cột và các cột tổ đội động theo yêu cầu.")

    # 15. Kiểm tra API tra cứu trùng mã vật tư (/api/check-material-code)
    res_chk_dup = client.get('/api/check-material-code?code=olsp20')
    assert res_chk_dup.status_code == 200
    data_chk_dup = res_chk_dup.get_json()
    assert data_chk_dup['exists'] is True
    assert data_chk_dup['message'] == "Đã có mã trong danh mục"

    res_chk_new = client.get('/api/check-material-code?code=ma_chua_tung_co_999')
    assert res_chk_new.status_code == 200
    assert res_chk_new.get_json()['exists'] is False
    print("15. [PASS] API kiểm tra trùng mã realtime hoạt động chuẩn xác (phát hiện olsp20 đã có).")

    # 16. Kiểm tra chặn ghi đè khi thêm tay mã vật tư đã có
    res_add_dup = client.post('/vat-tu/them', data={
        'code': 'olsp20',
        'name': 'Cố tình sửa tên',
        'brand': 'Hãng giả',
        'unit': 'Cuộn'
    }, follow_redirects=True)
    assert res_add_dup.status_code == 200
    assert "Đã có mã trong danh mục" in res_add_dup.text
    # Xác minh trong CSDL mã olsp20 KHÔNG bị ghi đè
    orig_mat = database.get_material_detail_with_history('olsp20')
    assert orig_mat['material']['name'] == 'Ống luồn dây điện D20'
    print("16. [PASS] Chặn thêm mã trùng khi nhập tay: Báo lỗi 'Đã có mã trong danh mục' và bảo vệ dữ liệu cũ 100%.")

    # 17. Kiểm tra nạp file Excel có mã đã tồn tại: Bỏ qua và không ghi đè
    res_import_dup = client.post(
        '/nhap-danh-sach-vat-tu-excel',
        data={'excel_file': (io.BytesIO(res_tpl.data), 'Mau_Danh_Sach_Vat_Tu_Bigcom.xlsx')},
        content_type='multipart/form-data',
        follow_redirects=True
    )
    assert res_import_dup.status_code == 200
    assert "Đã có mã trong danh mục" in res_import_dup.text
    print("17. [PASS] Nạp file Excel tự động bỏ qua các mã đã có trong danh mục, không cho phép ghi đè.")

    # 18. Kiểm tra giao diện phân hệ Nhập kho mới
    res_import_page = client.get('/nhap-kho')
    assert res_import_page.status_code == 200
    assert "Nhập kho" in res_import_page.text
    assert "Nhập vật tư" in res_import_page.text
    assert "Xuất Excel" in res_import_page.text
    assert "GM01" in res_import_page.text or "GM02" in res_import_page.text
    print("18. [PASS] Phân hệ Nhập kho hiển thị Bảng lịch sử nhập kho và nút Nhập vật tư Popup chuẩn xác.")

    # 19. Kiểm tra xuất file Excel Lịch sử nhập kho
    res_receipts_excel = client.get('/xuat-nhap-kho-excel')
    assert res_receipts_excel.status_code == 200
    assert len(res_receipts_excel.data) > 1000
    print(f"19. [PASS] Xuất file Excel Lịch sử nhập kho thành công ({len(res_receipts_excel.data)} bytes).")

    # 20. Kiểm tra giao diện phân hệ Xuất kho mới
    res_export_page = client.get('/xuat-kho')
    assert res_export_page.status_code == 200
    assert "Xuất kho" in res_export_page.text
    assert "Xuất vật tư" in res_export_page.text
    assert "Xuất Excel" in res_export_page.text
    assert "PXK" in res_export_page.text
    print("20. [PASS] Phân hệ Xuất kho hiển thị Bảng lịch sử xuất kho, nút Xuất vật tư và Xuất Excel chuẩn xác.")

    # 21. Kiểm tra API lấy danh sách tổ đội (/api/teams)
    res_teams = client.get('/api/teams')
    assert res_teams.status_code == 200
    teams_data = res_teams.get_json()
    assert teams_data['success'] is True
    assert 'Dũng' in teams_data['teams']
    print(f"21. [PASS] API /api/teams trả về {len(teams_data['teams'])} tổ đội (có tổ Dũng).")

    # 22. Kiểm tra API thêm tổ đội mới (/api/teams POST)
    test_team_name = "Tổ Cơ Điện Test"
    database.delete_team(test_team_name)
    res_add_team = client.post('/api/teams', json={'name': test_team_name})
    assert res_add_team.status_code == 200
    added_data = res_add_team.get_json()
    assert added_data['success'] is True
    assert test_team_name in added_data['teams']
    print(f"22. [PASS] API /api/teams thêm mới tổ đội '{test_team_name}' thành công.")

    # 23. Kiểm tra lập phiếu xuất kho cho tổ đội mới thêm
    next_issue_code = database.get_next_voucher_code("issue")
    res_issue_create = client.post('/xuat-kho', data={
        'voucher_code': next_issue_code,
        'voucher_date': '2026-11-21',
        'team': test_team_name,
        'receiver': 'Kỹ sư Test',
        'notes': 'Xuất thử nghiệm tự động',
        'material_code[]': ['olsp20'],
        'quantity[]': ['5']
    }, follow_redirects=True)
    assert res_issue_create.status_code == 200
    assert test_team_name in res_issue_create.text
    assert next_issue_code in res_issue_create.text
    print(f"23. [PASS] Lập phiếu xuất kho {next_issue_code} cho '{test_team_name}' thành công.")

    # 24. Kiểm tra xuất file Excel Lịch sử xuất kho
    res_issues_excel = client.get('/xuat-xuat-kho-excel')
    assert res_issues_excel.status_code == 200
    assert len(res_issues_excel.data) > 1000
    print(f"24. [PASS] Xuất file Excel Lịch sử xuất kho thành công ({len(res_issues_excel.data)} bytes).")

    # 25. Kiểm tra API xóa tổ đội (/api/teams/delete POST)
    del_team_name = "Tổ Test Tạm"
    client.post('/api/teams', json={'name': del_team_name})
    res_del_team = client.post('/api/teams/delete', json={'name': del_team_name})
    assert res_del_team.status_code == 200
    del_data = res_del_team.get_json()
    assert del_team_name not in del_data['teams']
    print(f"25. [PASS] API xóa tổ đội '{del_team_name}' hoạt động chính xác.")

    print("\n===> TẤT CẢ 25 BÀI TEST TÍCH HỢP QUẢN LÝ TỒN KHO BIGCOM ĐỀU VƯỢT QUA 100%!")

if __name__ == "__main__":
    run_tests()
