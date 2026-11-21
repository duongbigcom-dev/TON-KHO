@echo off
chcp 65001 > nul
title QUẢN LÝ TỒN KHO BIGCOM - MÁY CHỦ VĂN PHÒNG
echo ================================================================
echo                   QUẢN LÝ TỒN KHO BIGCOM
echo       HỆ THỐNG ĐỒNG BỘ THỜI GIAN THỰC CÔNG TRƯỜNG ⇄ VĂN PHÒNG
echo ================================================================
echo.
echo [1] Đang kiểm tra cơ sở dữ liệu...
if not exist "vattu_donghoa.db" (
    echo Chưa tìm thấy CSDL, tiến hành nạp dữ liệu từ file Excel...
    python import_excel_initial.py
) else (
    echo CSDL đã sẵn sàng!
)

echo.
echo [2] Lấy địa chỉ IP máy tính văn phòng trong mạng nội bộ...
for /f "tokens=4" %%a in ('route print ^| findstr 0.0.0.0 ^| findstr /v "255.255.255.255"') do (
    set LOCAL_IP=%%a
    goto :found_ip
)
:found_ip

echo.
echo [3] Đang tự động mở trình duyệt web của bạn...
start /b "" cmd /c "timeout /t 2 /nobreak > nul & start http://localhost:5000"

echo.
echo ================================================================
echo    MÁY CHỦ BIGCOM ĐANG HOẠT ĐỘNG!
echo.
echo    - Trình duyệt đang tự động mở tại: http://localhost:5000
echo    - Truy cập qua mạng LAN nội bộ:    http://%LOCAL_IP%:5000
echo.
echo    Tài khoản kiểm thử:
echo      + Admin:    admin   / admin123  (Toàn quyền hệ thống)
echo      + Kế toán:  ketoan  / ketoan123 (Văn phòng, xem giá & HĐ)
echo      + Thủ kho:  thukho  / thukho123 (Công trường, nhập/xuất/scan)
echo      + Chỉ xem:  viewer  / viewer123 (Tổ đội)
echo.
echo    (Nhấn Ctrl+C trong cửa sổ này để dừng máy chủ khi không sử dụng)
echo ================================================================
echo.

python app.py
pause
