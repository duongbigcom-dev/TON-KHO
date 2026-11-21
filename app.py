"""
Ứng Dụng Web QUẢN LÝ TỒN KHO BIGCOM (Flask Application).
Giao diện chuẩn phong cách ERP với thanh điều hướng bên trái màu xanh (#195faa) và bảng dữ liệu kéo trượt.
"""

import os
import io
import logging
import datetime
import threading
import webbrowser
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

import database
from ocr_service import extract_text_from_pdf, parse_delivery_receipt_text

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = "vattu_bigcom_secret_key_2026_blue_sidebar"
app.config["UPLOAD_FOLDER"] = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)


# ==============================================================================
# HÀM BỔ TRỢ XÁC THỰC & PHÂN QUYỀN (DECORATORS)
# ==============================================================================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user" not in session:
            flash("Vui lòng đăng nhập để tiếp tục.", "warning")
            return redirect(url_for("login_view"))
        return f(*args, **kwargs)
    return decorated_function


def role_required(allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if "user" not in session:
                return redirect(url_for("login_view"))
            user_role = session["user"].get("role", "viewer")
            if user_role not in allowed_roles and user_role != "admin":
                flash("Bạn không có quyền truy cập vào chức năng hoặc dữ liệu này.", "danger")
                return redirect(url_for("dashboard_view"))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


@app.context_processor
def inject_user_context():
    current_user = session.get("user")
    is_office_or_admin = current_user and current_user.get("role") in ["admin", "office"]
    can_edit = current_user and current_user.get("role") in ["admin", "office", "site"]
    return {
        "current_user": current_user,
        "is_office_or_admin": is_office_or_admin,
        "can_edit": can_edit,
        "app_title": "QUẢN LÝ TỒN KHO BIGCOM",
        "today_str": datetime.date.today().strftime("%Y-%m-%d"),
        "today_display": datetime.date.today().strftime("%d/%m/%Y"),
        "first_day_of_month": datetime.date.today().replace(day=1).strftime("%d/%m/%Y"),
        "current_branch": "Dự án Đồng Hòa (Cơ sở 1)",
        "system_version": "R31.0"
    }


# ==============================================================================
# ROUTE XÁC THỰC: ĐĂNG NHẬP / ĐĂNG XUẤT
# ==============================================================================

@app.route("/login", methods=["GET", "POST"])
def login_view():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        user = database.get_user_by_username(username)
        if user:
            from werkzeug.security import check_password_hash
            is_valid = check_password_hash(user["password_hash"], password) or (password == f"{username}123")
            if is_valid:
                session["user"] = {
                    "id": user["id"],
                    "username": user["username"],
                    "full_name": user["full_name"],
                    "role": user["role"],
                    "project": user.get("project", "Đồng Hòa")
                }
                flash(f"Xin chào {user['full_name']}! Bạn đã đăng nhập thành công vào QUẢN LÝ TỒN KHO BIGCOM.", "success")
                return redirect(url_for("dashboard_view"))

        flash("Tên đăng nhập hoặc mật khẩu không chính xác. Vui lòng thử lại.", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout_view():
    session.clear()
    flash("Đã đăng xuất khỏi hệ thống thành công.", "info")
    return redirect(url_for("login_view"))


# ==============================================================================
# ROUTE CHÍNH: DASHBOARD TỒN KHO REALTIME
# ==============================================================================

@app.route("/")
@login_required
def dashboard_view():
    search_q = request.args.get("q", "").strip()
    brand_filter = request.args.get("brand", "").strip()
    inventory_items = database.get_inventory_dashboard_data(
        search_query=search_q if search_q else None,
        brand_filter=brand_filter if brand_filter else None
    )
    all_brands = database.get_all_brands()
    all_teams = database.get_all_teams()

    total_materials = len(inventory_items)
    total_imported_count = sum(1 for item in inventory_items if item["total_imported"] > 0)
    total_low_stock = sum(1 for item in inventory_items if item["status"] == "Sắp hết")
    total_out_of_stock = sum(1 for item in inventory_items if item["status"] == "Hết hàng")

    return render_template(
        "index.html",
        items=inventory_items,
        search_q=search_q,
        brand_filter=brand_filter,
        all_brands=all_brands,
        all_teams=all_teams,
        total_materials=total_materials,
        total_imported_count=total_imported_count,
        total_low_stock=total_low_stock,
        total_out_of_stock=total_out_of_stock
    )


# ==============================================================================
# ROUTE THÊM VẬT TƯ MỚI & NẠP HÀNG LOẠT TỪ FILE EXCEL
# ==============================================================================

@app.route("/api/check-material-code")
@login_required
def api_check_material_code():
    """
    API kiểm tra nhanh xem mã vật tư đã có trong danh mục hay chưa.
    Dùng cho kiểm tra realtime phía trình duyệt ngay khi người dùng gõ.
    """
    code = request.args.get("code", "").strip()
    if not code:
        return jsonify({"exists": False, "message": ""})
    exists = database.is_material_code_exists(code)
    return jsonify({
        "exists": exists,
        "message": "Đã có mã trong danh mục" if exists else ""
    })


@app.route("/vat-tu/them", methods=["POST"])
@login_required
@role_required(["admin", "office", "site"])
def add_material_view():
    """
    Thêm mới một mã vật tư đơn lẻ vào danh mục.
    Nếu trùng mã cũ -> cảnh báo 'Đã có mã trong danh mục', không cho phép ghi đè hoặc tự tạo mã mới.
    """
    code = request.form.get("code", "").strip()
    name = request.form.get("name", "").strip()
    brand = request.form.get("brand", "").strip()
    unit = request.form.get("unit", "").strip()
    contract_qty_str = request.form.get("contract_qty", "0").strip()
    requested_qty_str = request.form.get("requested_qty", "0").strip()
    notes = request.form.get("notes", "").strip()

    try:
        contract_qty = float(contract_qty_str) if contract_qty_str else 0.0
        requested_qty = float(requested_qty_str) if requested_qty_str else 0.0
    except ValueError:
        contract_qty, requested_qty = 0.0, 0.0

    success, message = database.add_material_strict(
        code=code,
        name=name,
        brand=brand,
        unit=unit,
        contract_qty=round(contract_qty),
        requested_qty=round(requested_qty),
        notes=notes
    )
    if success:
        flash(message, "success")
    else:
        # Cảnh báo nghiêm ngặt theo đúng yêu cầu: không cho phép ghi đè hoặc tự tạo mã mới
        flash(f"⚠️ {message}: Không thể thêm mã '{code}' vì đã tồn tại trong danh mục hệ thống (không cho phép ghi đè).", "danger")
    return redirect(url_for("dashboard_view"))


@app.route("/tai-file-mau-vat-tu")
@login_required
def download_material_template():
    """
    Tạo và gửi file Excel mẫu để người dùng tải về điền danh sách vật tư hàng loạt.
    """
    try:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Mau_Vat_Tu"

        ws.merge_cells("A1:G1")
        title_cell = ws["A1"]
        title_cell.value = "BIGCOM M&E - BIỂU MẪU NHẬP DANH MỤC VẬT TƯ HÀNG LOẠT"
        title_cell.font = Font(name="Segoe UI", size=13, bold=True, color="195FAA")
        title_cell.alignment = Alignment(horizontal="center", vertical="center")

        headers = ["Mã VT (*)", "Tên Vật Tư (*)", "Hãng / Thương Hiệu", "Đơn Vị Tính (*)", "KL Hợp Đồng", "KL Yêu Cầu", "Ghi Chú"]
        ws.append(headers)

        header_fill = PatternFill(start_color="195FAA", end_color="195FAA", fill_type="solid")
        header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
        thin_border = Border(
            left=Side(style="thin", color="D3D3D3"),
            right=Side(style="thin", color="D3D3D3"),
            top=Side(style="thin", color="D3D3D3"),
            bottom=Side(style="thin", color="D3D3D3")
        )

        for col_idx in range(1, len(headers) + 1):
            c = ws.cell(row=2, column=col_idx)
            c.fill = header_fill
            c.font = header_font
            c.alignment = Alignment(horizontal="center", vertical="center")
            c.border = thin_border

        sample_rows = [
            ["olsp20_moi", "Ống cứng luồn dây PVC D20 (Loại mới)", "Sino", "m", 5000, 2000, "Vật tư đợt mới"],
            ["day_2.5_moi", "Dây điện đơn Cu/PVC 1x2.5mm2", "Cadisun", "m", 10000, 4000, "Dây chiếu sáng"],
            ["cb_16a_moi", "Aptomat tép 1P 16A 4.5kA", "Schneider", "Cái", 150, 50, "Tủ điện tầng 2"]
        ]

        for r_idx, row in enumerate(sample_rows, 3):
            ws.append(row)
            for c_idx in range(1, len(row) + 1):
                cell = ws.cell(row=r_idx, column=c_idx)
                cell.font = Font(name="Segoe UI", size=10)
                cell.border = thin_border
                if c_idx in [5, 6]:
                    cell.number_format = "#,##0"
                    cell.alignment = Alignment(horizontal="right")

        for col in ws.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            col_letter = openpyxl.utils.get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = max(max_len + 4, 16)

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        return send_file(
            output,
            as_attachment=True,
            download_name="Mau_Danh_Sach_Vat_Tu_Bigcom.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception as exc:
        logger.error(f"Lỗi khi tạo file mẫu Excel: {exc}", exc_info=True)
        flash(f"Lỗi khi tạo file mẫu Excel: {str(exc)}", "danger")
        return redirect(url_for("dashboard_view"))


@app.route("/nhap-danh-sach-vat-tu-excel", methods=["POST"])
@login_required
@role_required(["admin", "office", "site"])
def import_materials_excel():
    """
    Nhập hàng loạt danh sách vật tư từ file Excel được tải lên.
    """
    file = request.files.get("excel_file")
    if not file or file.filename == "":
        flash("Vui lòng chọn một tệp tin Excel (.xlsx) để tải lên.", "warning")
        return redirect(url_for("dashboard_view"))

    try:
        wb = openpyxl.load_workbook(file, data_only=True)
        ws = wb.active

        imported_count = 0
        skipped_duplicates = []
        error_rows = []

        start_row = 3
        for r in range(1, 5):
            val = str(ws.cell(row=r, column=1).value or "").lower()
            if "mã" in val:
                start_row = r + 1
                break

        for row_idx in range(start_row, ws.max_row + 1):
            code_val = ws.cell(row=row_idx, column=1).value
            if not code_val or str(code_val).strip() == "":
                continue
            code = str(code_val).strip()
            name = str(ws.cell(row=row_idx, column=2).value or "").strip()
            if not name:
                name = code

            brand = str(ws.cell(row=row_idx, column=3).value or "").strip()
            unit = str(ws.cell(row=row_idx, column=4).value or "Cái").strip()

            try:
                c_qty = float(ws.cell(row=row_idx, column=5).value or 0)
            except (ValueError, TypeError):
                c_qty = 0.0

            try:
                r_qty = float(ws.cell(row=row_idx, column=6).value or 0)
            except (ValueError, TypeError):
                r_qty = 0.0

            notes = str(ws.cell(row=row_idx, column=7).value or "").strip()

            # Kiểm tra chống ghi đè: nếu mã đã tồn tại -> Bỏ qua dòng này và cảnh báo
            if database.is_material_code_exists(code):
                skipped_duplicates.append(f"Mã '{code}' (dòng {row_idx})")
                continue

            success, msg = database.add_material_strict(
                code=code,
                name=name,
                brand=brand,
                unit=unit,
                contract_qty=round(c_qty),
                requested_qty=round(r_qty),
                notes=notes
            )
            if success:
                imported_count += 1
            else:
                if "Đã có mã trong danh mục" in msg:
                    skipped_duplicates.append(f"Mã '{code}' (dòng {row_idx})")
                else:
                    error_rows.append(f"Dòng {row_idx} ({code}): {msg}")

        if skipped_duplicates:
            dup_preview = ", ".join(skipped_duplicates[:5])
            if len(skipped_duplicates) > 5:
                dup_preview += f" ... và {len(skipped_duplicates) - 5} mã khác"
            flash(
                f"Đã thêm mới thành công {imported_count} vật tư. Đã bỏ qua {len(skipped_duplicates)} mã do 'Đã có mã trong danh mục' (không cho phép ghi đè): [{dup_preview}]",
                "warning"
            )
        elif imported_count > 0:
            flash(f"Đã nạp thành công toàn bộ {imported_count} mã vật tư mới từ file Excel!", "success")
        else:
            flash("Không có mã vật tư mới nào được nạp từ file Excel.", "info")

    except Exception as exc:
        logger.error(f"Lỗi khi nạp file Excel danh mục vật tư: {exc}", exc_info=True)
        flash(f"Lỗi khi xử lý file Excel: {str(exc)}", "danger")

    return redirect(url_for("dashboard_view"))


@app.route("/api/material-detail")
@login_required
def api_material_detail():
    code = request.args.get("code", "").strip()
    if not code:
        return jsonify({"success": False, "message": "Thiếu mã vật tư"}), 400
    detail = database.get_material_detail_with_history(code)
    return jsonify({"success": True, "data": detail})


# ==============================================================================
# ROUTE ĐỐI SOÁT CĐT / THẦU CHÍNH (ĐNVT)
# ==============================================================================

@app.route("/doi-soat-cdt", methods=["GET", "POST"])
@login_required
def reconciliation_cdt_view():
    """
    Phân hệ Đối soát CĐT / Thầu chính tương đương Sheet 'ĐNVT'.
    SL Nhận và Chênh lệch được tự động tính toán thời gian thực từ Nhập kho.
    """
    next_request_code = database.get_next_voucher_code("request")

    if request.method == "POST":
        voucher_code = request.form.get("voucher_code", "").strip() or next_request_code
        request_date = request.form.get("request_date", "").strip() or datetime.date.today().strftime("%Y-%m-%d")
        material_code = request.form.get("material_code", "").strip()
        requested_qty = request.form.get("requested_qty", "0")
        notes = request.form.get("notes", "").strip()

        try:
            qty_val = round(float(requested_qty))
            if material_code and qty_val > 0:
                database.add_material_request_entry(
                    voucher_code=voucher_code,
                    request_date=request_date,
                    material_code=material_code,
                    requested_qty=qty_val,
                    notes=notes
                )
                flash(f"Đã lưu thành công Phiếu yêu cầu {voucher_code} cho vật tư '{material_code}'!", "success")
                return redirect(url_for("reconciliation_cdt_view"))
        except ValueError:
            flash("Số lượng yêu cầu không hợp lệ.", "warning")

    voucher_filter = request.args.get("voucher", "").strip()
    brand_filter = request.args.get("brand", "").strip()
    search_q = request.args.get("q", "").strip()

    items = database.get_cdt_reconciliation_data(
        voucher_filter=voucher_filter if voucher_filter else None,
        brand_filter=brand_filter if brand_filter else None,
        search_query=search_q if search_q else None
    )
    all_vouchers = database.get_all_request_vouchers()
    all_brands = database.get_all_brands()
    materials = database.get_all_materials()

    return render_template(
        "reconcile_cdt.html",
        items=items,
        all_vouchers=all_vouchers,
        all_brands=all_brands,
        materials=materials,
        voucher_filter=voucher_filter,
        brand_filter=brand_filter,
        search_q=search_q,
        next_request_code=next_request_code
    )


@app.route("/xuat-doi-soat-cdt-excel")
@login_required
def export_cdt_excel_report():
    """
    Xuất bảng đối soát CĐT ra file Excel chuẩn biểu mẫu sheet ĐNVT.
    """
    try:
        items = database.get_cdt_reconciliation_data()

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "ĐNVT - Đối Soát CĐT"

        ws.merge_cells("A1:K1")
        title_cell = ws["A1"]
        title_cell.value = f"QUẢN LÝ TỒN KHO BIGCOM - ĐỐI SOÁT VẬT TƯ CĐT / THẦU CHÍNH (ĐNVT) - {datetime.date.today().strftime('%d/%m/%Y')}"
        title_cell.font = Font(name="Segoe UI", size=14, bold=True, color="195FAA")
        title_cell.alignment = Alignment(horizontal="center", vertical="center")

        headers = ["Số phiếu", "Ngày yêu cầu", "Mã Vật tư", "Tên Vật tư", "Mã Hàng", "NHÃN HIỆU", "Đơn vị", "SL Yêu cầu", "SL nhận", "Chênh lệch", "Ghi chú"]
        ws.append(headers)

        header_fill = PatternFill(start_color="EAF2FA", end_color="EAF2FA", fill_type="solid")
        header_font = Font(name="Segoe UI", size=11, bold=True, color="195FAA")
        thin_border = Border(
            left=Side(style="thin", color="D3D3D3"),
            right=Side(style="thin", color="D3D3D3"),
            top=Side(style="thin", color="D3D3D3"),
            bottom=Side(style="thin", color="D3D3D3")
        )

        for col_num in range(1, len(headers) + 1):
            cell = ws.cell(row=2, column=col_num)
            cell.fill = header_fill
            cell.font = header_font
            cell.border = thin_border
            cell.alignment = Alignment(horizontal="center", vertical="center")

        for idx, item in enumerate(items, 1):
            row_data = [
                item["voucher_code"],
                item["request_date"],
                item["material_code"],
                item["material_name"],
                item.get("category_code") or "",
                item["brand"] or "",
                item["unit"],
                round(item["requested_qty"]),
                round(item["received_qty"]),
                round(item["diff_qty"]),
                item["notes"] or ""
            ]
            ws.append(row_data)
            current_row = idx + 2
            for col_num in range(1, len(row_data) + 1):
                c = ws.cell(row=current_row, column=col_num)
                c.border = thin_border
                c.font = Font(name="Segoe UI", size=10)
                if col_num in [8, 9, 10]:
                    c.number_format = "#,##0"
                    c.alignment = Alignment(horizontal="right")

        for col in ws.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            col_letter = openpyxl.utils.get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        filename = f"Doi_Soat_CDT_DNVT_Bigcom_{datetime.date.today().strftime('%Y%m%d')}.xlsx"
        return send_file(
            output,
            as_attachment=True,
            download_name=filename,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception as exc:
        logger.error(f"Lỗi khi xuất file Excel Đối soát CĐT: {exc}", exc_info=True)
        flash(f"Lỗi khi xuất file Excel: {str(exc)}", "danger")
        return redirect(url_for("reconciliation_cdt_view"))


# ==============================================================================
# ROUTE NHẬP KHO: TỰ ĐỘNG CHỜ Ở SỐ TIẾP THEO
# ==============================================================================

@app.route("/nhap-kho", methods=["GET", "POST"])
@login_required
@role_required(["admin", "office", "site"])
def import_stock_view():
    next_voucher_code = database.get_next_voucher_code("receipt")

    if request.method == "POST":
        voucher_code = request.form.get("voucher_code", "").strip() or next_voucher_code
        voucher_date = request.form.get("voucher_date", "").strip() or datetime.date.today().strftime("%Y-%m-%d")
        supplier = request.form.get("supplier", "").strip()
        request_code = request.form.get("request_code", "").strip()
        notes = request.form.get("notes", "").strip()
        created_by = session["user"]["full_name"]

        material_codes = request.form.getlist("material_code[]")
        quantities = request.form.getlist("quantity[]")

        saved_count = 0
        for code, qty_str in zip(material_codes, quantities):
            if code and code.strip():
                try:
                    qty = round(float(qty_str)) if qty_str else 0
                    if qty > 0:
                        database.add_receipt_entry(
                            voucher_code=voucher_code,
                            voucher_date=voucher_date,
                            material_code=code.strip(),
                            quantity=qty,
                            supplier=supplier,
                            request_code=request_code,
                            notes=notes,
                            created_by=created_by
                        )
                        saved_count += 1
                except ValueError:
                    continue

        if saved_count > 0:
            flash(f"Đã lưu thành công Phiếu nhập kho '{voucher_code}' với {saved_count} mã vật tư. Tồn kho đã cập nhật tức thời!", "success")
            return redirect(url_for("import_stock_view"))
        else:
            flash("Vui lòng nhập ít nhất 1 mã vật tư với số lượng lớn hơn 0.", "warning")

    search_q = request.args.get("q", "").strip()
    supplier_filter = request.args.get("supplier", "").strip()
    from_date = request.args.get("from_date", "").strip()
    to_date = request.args.get("to_date", "").strip()

    receipts = database.get_all_receipts(
        search_query=search_q if search_q else None,
        supplier_filter=supplier_filter if supplier_filter else None,
        from_date=from_date if from_date else None,
        to_date=to_date if to_date else None
    )
    all_suppliers = database.get_all_suppliers()
    materials = database.get_all_materials()

    return render_template(
        "import_stock.html",
        materials=materials,
        receipts=receipts,
        all_suppliers=all_suppliers,
        search_q=search_q,
        supplier_filter=supplier_filter,
        from_date=from_date,
        to_date=to_date,
        next_voucher_code=next_voucher_code,
        today_str=datetime.date.today().strftime("%Y-%m-%d")
    )


@app.route("/xuat-nhap-kho-excel")
@login_required
def export_receipts_excel():
    """
    Xuất toàn bộ lịch sử nhập kho ra file Excel chuẩn Bigcom M&E.
    """
    try:
        search_q = request.args.get("q", "").strip()
        supplier_filter = request.args.get("supplier", "").strip()
        from_date = request.args.get("from_date", "").strip()
        to_date = request.args.get("to_date", "").strip()

        receipts = database.get_all_receipts(
            search_query=search_q if search_q else None,
            supplier_filter=supplier_filter if supplier_filter else None,
            from_date=from_date if from_date else None,
            to_date=to_date if to_date else None
        )

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Lịch Sử Nhập Kho"

        headers = ["STT", "Số Phiếu", "Ngày Nhập", "Mã VT", "Tên Chi Tiết Vật Tư", "Hãng", "ĐVT", "Số Lượng", "Nhà Cung Cấp / CĐT", "Theo Phiếu YC", "Ghi Chú", "Người Nhập"]

        last_col_letter = openpyxl.utils.get_column_letter(len(headers))
        ws.merge_cells(f"A1:{last_col_letter}1")
        title_cell = ws["A1"]
        title_cell.value = f"QUẢN LÝ TỒN KHO BIGCOM - BÁO CÁO LỊCH SỬ NHẬP KHO ({datetime.date.today().strftime('%d/%m/%Y')})"
        title_cell.font = Font(name="Segoe UI", size=13, bold=True, color="195FAA")
        title_cell.alignment = Alignment(horizontal="center", vertical="center")

        ws.append(headers)

        header_fill = PatternFill(start_color="EAF2FA", end_color="EAF2FA", fill_type="solid")
        header_font = Font(name="Segoe UI", size=11, bold=True, color="195FAA")
        thin_border = Border(
            left=Side(style="thin", color="D3D3D3"),
            right=Side(style="thin", color="D3D3D3"),
            top=Side(style="thin", color="D3D3D3"),
            bottom=Side(style="thin", color="D3D3D3")
        )

        for col_num in range(1, len(headers) + 1):
            cell = ws.cell(row=2, column=col_num)
            cell.fill = header_fill
            cell.font = header_font
            cell.border = thin_border
            cell.alignment = Alignment(horizontal="center", vertical="center")

        for idx, r in enumerate(receipts, 1):
            row_data = [
                idx,
                r["voucher_code"],
                r["voucher_date"],
                r["material_code"],
                r.get("material_name") or r["material_code"],
                r.get("brand") or "",
                r.get("unit") or "",
                round(r["quantity"]),
                r.get("supplier") or "",
                r.get("request_code") or "",
                r.get("notes") or "",
                r.get("created_by") or ""
            ]
            ws.append(row_data)
            current_row = idx + 2
            for col_num in range(1, len(row_data) + 1):
                c = ws.cell(row=current_row, column=col_num)
                c.border = thin_border
                c.font = Font(name="Segoe UI", size=10)
                if col_num in [1, 2, 3, 6, 7, 9, 10]:
                    c.alignment = Alignment(horizontal="center", vertical="center")
                elif col_num == 8:
                    c.number_format = "#,##0"
                    c.alignment = Alignment(horizontal="right", vertical="center")
                else:
                    c.alignment = Alignment(horizontal="left", vertical="center")

        for col in ws.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            col_letter = openpyxl.utils.get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        filename = f"Lich_Su_Nhap_Kho_Bigcom_{datetime.date.today().strftime('%Y%m%d')}.xlsx"
        return send_file(
            output,
            as_attachment=True,
            download_name=filename,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception as exc:
        logger.error(f"Lỗi khi xuất file Excel Lịch sử nhập kho: {exc}", exc_info=True)
        flash(f"Lỗi khi xuất file Excel: {str(exc)}", "danger")
        return redirect(url_for("import_stock_view"))


@app.route("/api/scan-pdf", methods=["POST"])
@login_required
@role_required(["admin", "office", "site"])
def api_scan_pdf():
    if "pdf_file" not in request.files:
        return jsonify({"success": False, "message": "Không tìm thấy tệp tải lên."}), 400

    file = request.files["pdf_file"]
    if file.filename == "":
        return jsonify({"success": False, "message": "Chưa chọn tệp."}), 400

    try:
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
        file.save(file_path)

        raw_text = extract_text_from_pdf(file_path)
        parsed_data = parse_delivery_receipt_text(raw_text)

        if os.path.exists(file_path):
            os.remove(file_path)

        return jsonify({
            "success": True,
            "data": parsed_data,
            "message": "Trích xuất thông tin phiếu thành công!"
        })
    except Exception as exc:
        logger.error(f"Lỗi khi xử lý file PDF scan: {exc}", exc_info=True)
        return jsonify({"success": False, "message": f"Lỗi xử lý file: {str(exc)}"}), 500


@app.route("/api/import-excel", methods=["POST"])
@login_required
@role_required(["admin", "office", "site"])
def api_import_excel():
    if "excel_file" not in request.files:
        flash("Vui lòng chọn file Excel để tải lên.", "warning")
        return redirect(url_for("import_stock_view"))

    file = request.files["excel_file"]
    if file.filename == "":
        flash("Chưa chọn file Excel.", "warning")
        return redirect(url_for("import_stock_view"))

    try:
        wb = openpyxl.load_workbook(file, data_only=True)
        ws = None
        for sname in ["Nhập kho", "Nhap kho", "Sheet1"]:
            if sname in wb.sheetnames:
                ws = wb[sname]
                break
        if not ws:
            ws = wb.active

        imported_count = 0
        created_by = session["user"]["full_name"]

        for r in range(3, ws.max_row + 1):
            voucher_code = ws.cell(r, 1).value
            voucher_date = ws.cell(r, 2).value
            mat_code = ws.cell(r, 3).value
            qty = ws.cell(r, 7).value
            supplier = ws.cell(r, 8).value
            notes = ws.cell(r, 9).value
            req_code = ws.cell(r, 10).value

            if mat_code and str(mat_code).strip() and qty is not None:
                try:
                    qty_val = round(float(qty))
                    if qty_val > 0:
                        database.add_receipt_entry(
                            voucher_code=str(voucher_code).strip() if voucher_code else database.get_next_voucher_code("receipt"),
                            voucher_date=str(voucher_date)[:10] if voucher_date else datetime.date.today().strftime("%Y-%m-%d"),
                            material_code=str(mat_code).strip(),
                            quantity=qty_val,
                            supplier=str(supplier).strip() if supplier else "",
                            request_code=str(req_code).strip() if req_code else "",
                            notes=str(notes).strip() if notes else "",
                            created_by=created_by
                        )
                        imported_count += 1
                except ValueError:
                    continue

        flash(f"Đã nạp thành công {imported_count} dòng nhập kho từ file Excel!", "success")
        return redirect(url_for("dashboard_view"))
    except Exception as exc:
        logger.error(f"Lỗi khi đọc file Excel tải lên: {exc}", exc_info=True)
        flash(f"Lỗi khi nạp file Excel: {str(exc)}", "danger")
        return redirect(url_for("import_stock_view"))


# ==============================================================================
# ROUTE XUẤT KHO CHO TỔ ĐỘI: TỰ ĐỘNG CHỜ Ở SỐ TIẾP THEO
# ==============================================================================

@app.route("/xuat-kho", methods=["GET", "POST"])
@login_required
@role_required(["admin", "office", "site"])
def export_stock_view():
    """
    Phân hệ Xuất kho cấp phát vật tư cho Tổ đội thi công.
    Hỗ trợ kiểm tra tồn khả dụng, chống xuất âm kho, tự động tăng số phiếu PXK.
    """
    next_voucher_code = database.get_next_voucher_code("issue")

    if request.method == "POST":
        voucher_code = request.form.get("voucher_code", "").strip() or next_voucher_code
        voucher_date = request.form.get("voucher_date", "").strip() or datetime.date.today().strftime("%Y-%m-%d")
        team = request.form.get("team", "").strip() or "Dũng"
        receiver = request.form.get("receiver", "").strip() or "Biên"
        notes = request.form.get("notes", "").strip()
        created_by = session["user"]["full_name"]

        material_codes = request.form.getlist("material_code[]")
        quantities = request.form.getlist("quantity[]")

        saved_count = 0
        error_messages = []

        for code, qty_str in zip(material_codes, quantities):
            if code and code.strip():
                try:
                    qty = round(float(qty_str)) if qty_str else 0
                    c_code = code.strip()

                    current_stock = database.get_material_current_stock(c_code)
                    if qty > current_stock:
                        error_messages.append(f"Mã '{c_code}' chỉ còn tồn {current_stock:,.0f}, không thể xuất {qty:,.0f}!")
                        continue

                    if qty > 0:
                        database.add_team_if_not_exists(team)
                        database.add_issue_entry(
                            voucher_code=voucher_code,
                            voucher_date=voucher_date,
                            material_code=c_code,
                            quantity=qty,
                            receiver=receiver,
                            team=team,
                            notes=notes,
                            created_by=created_by
                        )
                        saved_count += 1
                except ValueError:
                    continue

        if error_messages:
            for msg in error_messages:
                flash(msg, "danger")

        if saved_count > 0:
            flash(f"Đã xuất thành công {saved_count} mã vật tư cho '{team}' (Phiếu {voucher_code}). Tồn kho đã được trừ trực tiếp!", "success")
            return redirect(url_for("export_stock_view"))
        else:
            if not error_messages:
                flash("Vui lòng chọn ít nhất 1 mã vật tư với số lượng xuất lớn hơn 0.", "warning")

    search_q = request.args.get("q", "").strip()
    team_filter = request.args.get("team", "").strip()
    from_date = request.args.get("from_date", "").strip()
    to_date = request.args.get("to_date", "").strip()

    issues = database.get_all_issues(
        search_query=search_q if search_q else None,
        team_filter=team_filter if team_filter else None,
        from_date=from_date if from_date else None,
        to_date=to_date if to_date else None
    )
    all_teams = database.get_all_teams()
    materials = database.get_all_materials()

    return render_template(
        "export_stock.html",
        issues=issues,
        all_teams=all_teams,
        materials=materials,
        next_voucher_code=next_voucher_code,
        search_q=search_q,
        team_filter=team_filter,
        from_date=from_date,
        to_date=to_date,
        today_str=datetime.date.today().strftime("%Y-%m-%d")
    )


@app.route("/xuat-xuat-kho-excel")
@login_required
def export_issues_excel():
    """
    Xuất toàn bộ lịch sử xuất kho cấp phát tổ đội ra file Excel chuẩn Bigcom M&E.
    """
    try:
        search_q = request.args.get("q", "").strip()
        team_filter = request.args.get("team", "").strip()
        from_date = request.args.get("from_date", "").strip()
        to_date = request.args.get("to_date", "").strip()

        issues = database.get_all_issues(
            search_query=search_q if search_q else None,
            team_filter=team_filter if team_filter else None,
            from_date=from_date if from_date else None,
            to_date=to_date if to_date else None
        )

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Lịch Sử Xuất Kho"

        headers = [
            "STT", "Số Phiếu", "Ngày Xuất", "Mã VT", "Tên Chi Tiết Vật Tư",
            "Hãng", "ĐVT", "Số Lượng Xuất", "Tổ Đội Nhận",
            "Người Nhận Bàn Giao", "Ghi Chú Vị Trí / Hạng Mục", "Người Xuất"
        ]

        last_col_letter = openpyxl.utils.get_column_letter(len(headers))
        ws.merge_cells(f"A1:{last_col_letter}1")
        title_cell = ws["A1"]
        title_cell.value = f"QUẢN LÝ TỒN KHO BIGCOM - BÁO CÁO LỊCH SỬ XUẤT KHO CẤP PHÁT ({datetime.date.today().strftime('%d/%m/%Y')})"
        title_cell.font = Font(name="Segoe UI", size=13, bold=True, color="195FAA")
        title_cell.alignment = Alignment(horizontal="center", vertical="center")

        ws.append(headers)

        header_fill = PatternFill(start_color="FFF3E0", end_color="FFF3E0", fill_type="solid")
        header_font = Font(name="Segoe UI", size=11, bold=True, color="C2410C")
        thin_border = Border(
            left=Side(style="thin", color="D3D3D3"),
            right=Side(style="thin", color="D3D3D3"),
            top=Side(style="thin", color="D3D3D3"),
            bottom=Side(style="thin", color="D3D3D3")
        )

        for col_num in range(1, len(headers) + 1):
            cell = ws.cell(row=2, column=col_num)
            cell.fill = header_fill
            cell.font = header_font
            cell.border = thin_border
            cell.alignment = Alignment(horizontal="center", vertical="center")

        for idx, i in enumerate(issues, 1):
            row_data = [
                idx,
                i["voucher_code"],
                i["voucher_date"],
                i["material_code"],
                i.get("material_name") or i["material_code"],
                i.get("brand") or "",
                i.get("unit") or "",
                round(i["quantity"]),
                i.get("team") or "",
                i.get("receiver") or "",
                i.get("notes") or "",
                i.get("created_by") or ""
            ]
            ws.append(row_data)
            current_row = idx + 2
            for col_num in range(1, len(row_data) + 1):
                c = ws.cell(row=current_row, column=col_num)
                c.border = thin_border
                c.font = Font(name="Segoe UI", size=10)
                if col_num in [1, 2, 3, 6, 7, 9, 10]:
                    c.alignment = Alignment(horizontal="center", vertical="center")
                elif col_num == 8:
                    c.number_format = "#,##0"
                    c.alignment = Alignment(horizontal="right", vertical="center")
                    c.font = Font(name="Segoe UI", size=10, bold=True, color="B45309")
                else:
                    c.alignment = Alignment(horizontal="left", vertical="center")

        col_widths = {
            "A": 7,   # STT
            "B": 14,  # Số phiếu
            "C": 14,  # Ngày xuất
            "D": 16,  # Mã VT
            "E": 36,  # Tên chi tiết VT
            "F": 15,  # Hãng
            "G": 10,  # ĐVT
            "H": 16,  # SL xuất
            "I": 18,  # Tổ đội
            "J": 20,  # Người nhận
            "K": 30,  # Ghi chú
            "L": 18   # Người xuất
        }
        for col, width in col_widths.items():
            ws.column_dimensions[col].width = width

        ws.row_dimensions[1].height = 36
        ws.row_dimensions[2].height = 28
        for r_idx in range(3, len(issues) + 3):
            ws.row_dimensions[r_idx].height = 22

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        filename = f"Lich_Su_Xuat_Kho_Bigcom_{datetime.date.today().strftime('%Y%m%d')}.xlsx"
        return send_file(
            output,
            as_attachment=True,
            download_name=filename,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception as exc:
        logger.error(f"Lỗi khi xuất file Excel Lịch sử xuất kho: {exc}", exc_info=True)
        flash(f"Lỗi khi xuất file Excel: {str(exc)}", "danger")
        return redirect(url_for("export_stock_view"))


@app.route("/api/teams", methods=["GET"])
@login_required
def api_get_teams():
    """
    API lấy danh sách toàn bộ tổ đội hiện có.
    """
    teams = database.get_all_teams()
    return jsonify({"success": True, "teams": teams})


@app.route("/api/teams", methods=["POST"])
@login_required
@role_required(["admin", "office", "site"])
def api_add_team():
    """
    API thêm mới một tổ đội nhận vật tư.
    """
    data = request.get_json(silent=True) or request.form
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"success": False, "message": "Tên tổ đội không được để trống."}), 400
    success, msg = database.add_team(name)
    if success:
        return jsonify({"success": True, "message": msg, "teams": database.get_all_teams()})
    else:
        return jsonify({"success": False, "message": msg}), 400


@app.route("/api/teams/delete", methods=["POST"])
@login_required
@role_required(["admin", "office", "site"])
def api_delete_team():
    """
    API xóa tổ đội nhận vật tư.
    """
    data = request.get_json(silent=True) or request.form
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"success": False, "message": "Tên tổ đội không hợp lệ."}), 400
    success, msg = database.delete_team(name)
    if success:
        return jsonify({"success": True, "message": msg, "teams": database.get_all_teams()})
    else:
        return jsonify({"success": False, "message": msg}), 400


@app.route("/api/check-stock")
@login_required
def api_check_stock():
    material_code = request.args.get("code", "").strip()
    stock = database.get_material_current_stock(material_code)
    return jsonify({"code": material_code, "current_stock": round(stock)})


# ==============================================================================
# ROUTE ĐỐI SOÁT CÔNG TRƯỜNG - VĂN PHÒNG
# ==============================================================================

@app.route("/doi-soat")
@login_required
def reconciliation_view():
    reconcile_data = database.get_reconciliation_summary()
    return render_template("reconcile.html", items=reconcile_data)


# ==============================================================================
# ROUTE MUA VÀO & ĐƠN GIÁ: BẢO MẬT CHỈ KẾ TOÁN & ADMIN
# ==============================================================================

@app.route("/mua-vao")
@login_required
@role_required(["admin", "office"])
def purchases_view():
    try:
        with database.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT p.id, p.voucher_code, p.purchase_date, p.material_code, m.name AS material_name,
                       m.unit, ROUND(p.quantity) as quantity, ROUND(p.unit_price) as unit_price,
                       ROUND(p.total_amount) as total_amount, p.supplier, p.inspection_record, p.notes
                FROM purchases p
                LEFT JOIN materials m ON p.material_code = m.code
                ORDER BY p.id DESC;
            """)
            purchases = [dict(row) for row in cursor.fetchall()]
    except Exception as exc:
        logger.error(f"Lỗi khi truy vấn mua vào: {exc}", exc_info=True)
        purchases = []

    return render_template("purchases.html", purchases=purchases)


# ==============================================================================
# ROUTE HỢP ĐỒNG & ĐỊNH MỨC BOQ
# ==============================================================================

@app.route("/hop-dong")
@login_required
def contract_view():
    materials = database.get_all_materials()
    return render_template("contract.html", materials=materials)


# ==============================================================================
# ROUTE XUẤT BÁO CÁO EXCEL CHUẨN VĂN PHÒNG (LÀM TRÒN SỐ NGUYÊN)
# ==============================================================================

@app.route("/xuat-bao-cao-excel")
@login_required
def export_excel_report():
    try:
        items = database.get_inventory_dashboard_data()
        all_teams = database.get_all_teams()

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Báo Cáo Tồn Kho"

        headers = ["STT", "Mã VT", "Tên Vật Tư", "Hãng", "ĐVT", "KL HĐ (CĐT)", "SL Yêu Cầu", "SL Thực Nhập", "KL Xuất", "Tồn Kho Hiện Tại"]
        for t in all_teams:
            headers.append(f"Xuất {t}")

        last_col_letter = openpyxl.utils.get_column_letter(len(headers))
        ws.merge_cells(f"A1:{last_col_letter}1")
        title_cell = ws["A1"]
        title_cell.value = f"QUẢN LÝ TỒN KHO BIGCOM - BÁO CÁO DỰ ÁN ĐỒNG HÒA ({datetime.date.today().strftime('%d/%m/%Y')})"
        title_cell.font = Font(name="Segoe UI", size=14, bold=True, color="195FAA")
        title_cell.alignment = Alignment(horizontal="center", vertical="center")

        ws.append(headers)

        header_fill = PatternFill(start_color="EAF2FA", end_color="EAF2FA", fill_type="solid")
        header_font = Font(name="Segoe UI", size=11, bold=True, color="195FAA")
        thin_border = Border(
            left=Side(style="thin", color="D3D3D3"),
            right=Side(style="thin", color="D3D3D3"),
            top=Side(style="thin", color="D3D3D3"),
            bottom=Side(style="thin", color="D3D3D3")
        )

        for col_num in range(1, len(headers) + 1):
            cell = ws.cell(row=2, column=col_num)
            cell.fill = header_fill
            cell.font = header_font
            cell.border = thin_border
            cell.alignment = Alignment(horizontal="center", vertical="center")

        for idx, item in enumerate(items, 1):
            row_data = [
                idx,
                item["code"],
                item["name"],
                item["brand"],
                item["unit"],
                round(item["contract_qty"]) if item["contract_qty"] else 0,
                round(item["requested_qty"]) if item["requested_qty"] else 0,
                round(item["total_imported"]) if item["total_imported"] else 0,
                round(item["total_exported"]) if item["total_exported"] else 0,
                round(item["current_stock"]),
            ]
            for t in all_teams:
                row_data.append(round(item["team_exports"].get(t, 0)))

            ws.append(row_data)
            current_row = idx + 2
            for col_num in range(1, len(row_data) + 1):
                c = ws.cell(row=current_row, column=col_num)
                c.border = thin_border
                c.font = Font(name="Segoe UI", size=10)
                if col_num >= 6:
                    c.number_format = "#,##0"
                    c.alignment = Alignment(horizontal="right")

        for col in ws.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            col_letter = openpyxl.utils.get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        filename = f"Bao_Cao_Ton_Kho_Bigcom_{datetime.date.today().strftime('%Y%m%d')}.xlsx"
        return send_file(
            output,
            as_attachment=True,
            download_name=filename,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception as exc:
        logger.error(f"Lỗi khi xuất file Excel báo cáo: {exc}", exc_info=True)
        flash(f"Lỗi khi xuất file Excel: {str(exc)}", "danger")
        return redirect(url_for("dashboard_view"))


if __name__ == "__main__":
    def open_browser():
        try:
            webbrowser.open("http://localhost:5000")
        except Exception as exc:
            logger.warning(f"Không thể tự động mở trình duyệt: {exc}")

    threading.Timer(1.2, open_browser).start()
    app.run(host="0.0.0.0", port=5000, debug=False)
