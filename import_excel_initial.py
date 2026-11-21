"""
Script nạp toàn bộ dữ liệu khởi tạo từ file Excel 'BẢNG THEO DÕI VẬT TƯ ĐỒNG HÒA.xlsx' vào SQLite Database.
Bao gồm: materials, receipts, issues, purchases, material_requests (ĐNVT), users.
"""

import os
import logging
import openpyxl
import datetime
from database import init_database, get_db_connection, create_or_update_user

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

EXCEL_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "BẢNG THEO DÕI VẬT TƯ ĐỒNG HÒA.xlsx")


def parse_cell_date(cell_val) -> str:
    if isinstance(cell_val, (datetime.datetime, datetime.date)):
        return cell_val.strftime("%Y-%m-%d")
    elif cell_val:
        return str(cell_val).strip()[:10]
    return datetime.date.today().strftime("%Y-%m-%d")


def parse_cell_number(cell_val, default: float = 0.0) -> float:
    if isinstance(cell_val, (int, float)):
        return float(cell_val)
    elif cell_val:
        try:
            cleaned = str(cell_val).replace(",", "").strip()
            return float(cleaned)
        except ValueError:
            return default
    return default


def seed_data_from_excel():
    logger.info("Bắt đầu khởi tạo cấu trúc CSDL...")
    init_database()

    # 1. Tạo các tài khoản phân quyền mẫu ban đầu
    logger.info("Tạo các tài khoản người dùng mẫu...")
    default_users = [
        ("admin", "admin123", "Ban Quản Trị Hệ Thống", "admin"),
        ("ketoan", "ketoan123", "Kế Toán Văn Phòng", "office"),
        ("thukho", "thukho123", "Thủ Kho Công Trường", "site"),
        ("kythuat", "kythuat123", "Kỹ Sư Công Trường Đồng Hòa", "site"),
        ("viewer", "viewer123", "Tổ Đội / Người Chỉ Xem", "viewer")
    ]
    for username, pwd, full_name, role in default_users:
        create_or_update_user(username, pwd, full_name, role)

    if not os.path.exists(EXCEL_FILE_PATH):
        logger.error(f"Không tìm thấy file Excel tại {EXCEL_FILE_PATH}")
        return

    logger.info(f"Đang tải dữ liệu từ {EXCEL_FILE_PATH}...")
    wb = openpyxl.load_workbook(EXCEL_FILE_PATH, data_only=True)

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # 2. Đọc và nạp Danh mục vật tư từ sheet 'TH Tồn kho' và 'HỢP ĐỒNG'
        materials_dict = {}

        if "TH Tồn kho" in wb.sheetnames:
            ws_th = wb["TH Tồn kho"]
            logger.info("Đang đọc sheet 'TH Tồn kho'...")
            for r in range(3, ws_th.max_row + 1):
                code = ws_th.cell(r, 2).value
                name = ws_th.cell(r, 3).value
                category_code = ws_th.cell(r, 4).value
                brand = ws_th.cell(r, 5).value
                unit = ws_th.cell(r, 6).value
                kl_hd = ws_th.cell(r, 7).value
                sl_yc = ws_th.cell(r, 8).value
                audit_qty = ws_th.cell(r, 12).value

                if code and str(code).strip():
                    c_code = str(code).strip()
                    materials_dict[c_code] = {
                        "code": c_code,
                        "name": str(name).strip() if name else c_code,
                        "category_code": str(category_code).strip() if category_code else "",
                        "brand": str(brand).strip() if brand else "",
                        "unit": str(unit).strip() if unit else "Cái",
                        "contract_qty": parse_cell_number(kl_hd),
                        "requested_qty": parse_cell_number(sl_yc),
                        "audit_qty": parse_cell_number(audit_qty) if audit_qty is not None else None,
                        "notes": ""
                    }

        if "HỢP ĐỒNG" in wb.sheetnames:
            ws_hd = wb["HỢP ĐỒNG"]
            logger.info("Đang đọc bổ sung từ sheet 'HỢP ĐỒNG'...")
            for r in range(3, ws_hd.max_row + 1):
                code = ws_hd.cell(r, 1).value
                name = ws_hd.cell(r, 2).value
                unit = ws_hd.cell(r, 3).value
                qty = ws_hd.cell(r, 4).value

                if code and str(code).strip() not in ["A", "B", "C", "D", "E", "F", "G"]:
                    c_code = str(code).strip()
                    if c_code not in materials_dict:
                        materials_dict[c_code] = {
                            "code": c_code,
                            "name": str(name).strip() if name else c_code,
                            "category_code": "",
                            "brand": "",
                            "unit": str(unit).strip() if unit else "Cái",
                            "contract_qty": parse_cell_number(qty),
                            "requested_qty": 0.0,
                            "audit_qty": None,
                            "notes": "Nhập từ Hợp đồng"
                        }

        for m in materials_dict.values():
            cursor.execute("""
                INSERT INTO materials (code, name, category_code, brand, unit, contract_qty, requested_qty, audit_qty, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(code) DO UPDATE SET
                    name = excluded.name,
                    brand = excluded.brand,
                    unit = excluded.unit,
                    contract_qty = excluded.contract_qty;
            """, (m["code"], m["name"], m["category_code"], m["brand"], m["unit"],
                  m["contract_qty"], m["requested_qty"], m["audit_qty"], m["notes"]))

        logger.info(f"Đã lưu thành công {len(materials_dict)} danh mục vật tư chuẩn.")

        # 3. Đọc và nạp dữ liệu sheet 'Nhập kho'
        if "Nhập kho" in wb.sheetnames:
            ws_nk = wb["Nhập kho"]
            logger.info("Đang nạp dữ liệu sheet 'Nhập kho'...")
            cursor.execute("DELETE FROM receipts WHERE created_by = 'Excel Import';")
            imported_receipts = 0
            for r in range(3, ws_nk.max_row + 1):
                voucher_code = ws_nk.cell(r, 1).value
                voucher_date = ws_nk.cell(r, 2).value
                mat_code = ws_nk.cell(r, 3).value
                qty = ws_nk.cell(r, 7).value
                supplier = ws_nk.cell(r, 8).value
                notes = ws_nk.cell(r, 9).value
                req_code = ws_nk.cell(r, 10).value

                if mat_code and str(mat_code).strip() and qty is not None:
                    c_mat = str(mat_code).strip()
                    if c_mat not in materials_dict:
                        cursor.execute("""
                            INSERT OR IGNORE INTO materials (code, name, unit)
                            VALUES (?, ?, ?);
                        """, (c_mat, c_mat, "Cái"))
                        materials_dict[c_mat] = True

                    cursor.execute("""
                        INSERT INTO receipts (voucher_code, voucher_date, material_code, quantity, supplier, request_code, notes, created_by)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                    """, (
                        str(voucher_code).strip() if voucher_code else "GM01",
                        parse_cell_date(voucher_date),
                        c_mat,
                        round(parse_cell_number(qty)),
                        str(supplier).strip() if supplier else "",
                        str(req_code).strip() if req_code else "",
                        str(notes).strip() if notes else "",
                        "Excel Import"
                    ))
                    imported_receipts += 1
            logger.info(f"Đã nạp {imported_receipts} dòng phiếu nhập kho.")

        # 4. Đọc và nạp dữ liệu sheet 'Xuất kho'
        if "Xuất kho" in wb.sheetnames:
            ws_xk = wb["Xuất kho"]
            logger.info("Đang nạp dữ liệu sheet 'Xuất kho'...")
            cursor.execute("DELETE FROM issues WHERE created_by = 'Excel Import';")
            imported_issues = 0
            for r in range(3, ws_xk.max_row + 1):
                voucher_code = ws_xk.cell(r, 1).value
                voucher_date = ws_xk.cell(r, 2).value
                mat_code = ws_xk.cell(r, 3).value
                qty = ws_xk.cell(r, 7).value
                receiver = ws_xk.cell(r, 8).value
                team = ws_xk.cell(r, 9).value
                notes = ws_xk.cell(r, 10).value

                if mat_code and str(mat_code).strip() and qty is not None:
                    c_mat = str(mat_code).strip()
                    if c_mat not in materials_dict:
                        cursor.execute("""
                            INSERT OR IGNORE INTO materials (code, name, unit)
                            VALUES (?, ?, ?);
                        """, (c_mat, c_mat, "Cái"))
                        materials_dict[c_mat] = True

                    cursor.execute("""
                        INSERT INTO issues (voucher_code, voucher_date, material_code, quantity, receiver, team, notes, created_by)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                    """, (
                        str(voucher_code).strip() if voucher_code else "PXK01",
                        parse_cell_date(voucher_date),
                        c_mat,
                        round(parse_cell_number(qty)),
                        str(receiver).strip() if receiver else "Biên",
                        str(team).strip() if team else "Dũng",
                        str(notes).strip() if notes else "",
                        "Excel Import"
                    ))
                    imported_issues += 1
            logger.info(f"Đã nạp {imported_issues} dòng phiếu xuất kho cho tổ đội.")

        # 5. Đọc và nạp dữ liệu sheet 'ĐNVT' (Đối soát CĐT / Thầu chính)
        if "ĐNVT" in wb.sheetnames:
            ws_dnvt = wb["ĐNVT"]
            logger.info("Đang nạp dữ liệu sheet 'ĐNVT' (Đối soát CĐT)...")
            cursor.execute("DELETE FROM material_requests;")
            imported_dnvt = 0
            for r in range(3, ws_dnvt.max_row + 1):
                v_code = ws_dnvt.cell(r, 1).value
                req_date = ws_dnvt.cell(r, 2).value
                mat_code = ws_dnvt.cell(r, 3).value
                req_qty = ws_dnvt.cell(r, 8).value
                rec_qty = ws_dnvt.cell(r, 9).value
                diff_qty = ws_dnvt.cell(r, 10).value
                notes = ws_dnvt.cell(r, 11).value

                if v_code and mat_code and req_qty is not None:
                    c_mat = str(mat_code).strip()
                    if c_mat not in materials_dict:
                        cursor.execute("""
                            INSERT OR IGNORE INTO materials (code, name, unit)
                            VALUES (?, ?, ?);
                        """, (c_mat, c_mat, "Cái"))
                        materials_dict[c_mat] = True

                    cursor.execute("""
                        INSERT INTO material_requests (voucher_code, request_date, material_code, requested_qty, received_qty, difference_qty, notes)
                        VALUES (?, ?, ?, ?, ?, ?, ?);
                    """, (
                        str(v_code).strip(),
                        parse_cell_date(req_date),
                        c_mat,
                        round(parse_cell_number(req_qty)),
                        round(parse_cell_number(rec_qty)),
                        round(parse_cell_number(diff_qty)),
                        str(notes).strip() if notes else ""
                    ))
                    imported_dnvt += 1
            logger.info(f"Đã nạp thành công {imported_dnvt} dòng phiếu đề nghị vật tư ĐNVT.")

        # 6. Đọc và nạp dữ liệu sheet 'Mua vào'
        if "Mua vào" in wb.sheetnames:
            ws_mv = wb["Mua vào"]
            logger.info("Đang nạp dữ liệu sheet 'Mua vào'...")
            cursor.execute("DELETE FROM purchases;")
            imported_purchases = 0
            for r in range(3, ws_mv.max_row + 1):
                voucher_code = ws_mv.cell(r, 1).value
                purchase_date = ws_mv.cell(r, 2).value
                mat_code = ws_mv.cell(r, 3).value
                qty = ws_mv.cell(r, 8).value
                unit_price = ws_mv.cell(r, 9).value
                total_amount = ws_mv.cell(r, 10).value
                supplier = ws_mv.cell(r, 11).value
                notes = ws_mv.cell(r, 13).value
                inspection_record = ws_mv.cell(r, 14).value

                if mat_code and str(mat_code).strip() and str(mat_code).strip() != "#N/A" and qty is not None:
                    cursor.execute("""
                        INSERT INTO purchases (voucher_code, purchase_date, material_code, quantity, unit_price, total_amount, supplier, inspection_record, notes)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """, (
                        str(voucher_code).strip() if voucher_code else "",
                        parse_cell_date(purchase_date),
                        str(mat_code).strip(),
                        round(parse_cell_number(qty)),
                        round(parse_cell_number(unit_price)),
                        round(parse_cell_number(total_amount)),
                        str(supplier).strip() if supplier else "",
                        str(inspection_record).strip() if inspection_record else "",
                        str(notes).strip() if notes else ""
                    ))
                    imported_purchases += 1
            logger.info(f"Đã nạp {imported_purchases} dòng phiếu mua vào.")

        conn.commit()
    logger.info("Hoàn tất quá trình nạp dữ liệu khởi tạo!")


if __name__ == "__main__":
    seed_data_from_excel()
