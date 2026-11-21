"""
Module Quản lý Cơ sở dữ liệu SQLite cho Hệ thống Quản lý Tồn Kho Bigcom.
Lý do chọn SQLite: 
- Lưu trữ dữ liệu dạng tệp tin cục bộ duy nhất (vattu_donghoa.db), không cần cài đặt SQL Server/Postgres cồng kềnh.
- Dễ dàng sao lưu, sao chép hoặc di chuyển giữa máy văn phòng và máy dự phòng.
- Đảm bảo tính toàn vẹn dữ liệu (ACID transactions) khi nhiều thao tác nhập xuất xảy ra đồng thời.
"""

import sqlite3
import os
import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from werkzeug.security import generate_password_hash, check_password_hash

# Cấu hình logging để ghi lại các lỗi phát sinh trong quá trình truy vấn
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

DATABASE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vattu_donghoa.db")


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_database() -> None:
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # 1. Bảng Danh mục vật tư (Materials)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS materials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                category_code TEXT,
                brand TEXT,
                unit TEXT NOT NULL,
                contract_qty REAL DEFAULT 0.0,
                requested_qty REAL DEFAULT 0.0,
                audit_qty REAL DEFAULT NULL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # 2. Bảng Phiếu Nhập kho (Receipts)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS receipts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                voucher_code TEXT NOT NULL,
                voucher_date TEXT NOT NULL,
                material_code TEXT NOT NULL,
                quantity REAL NOT NULL,
                supplier TEXT,
                request_code TEXT,
                notes TEXT,
                created_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (material_code) REFERENCES materials(code) ON UPDATE CASCADE
            );
            """)

            # 3. Bảng Phiếu Xuất kho (Issues)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                voucher_code TEXT NOT NULL,
                voucher_date TEXT NOT NULL,
                material_code TEXT NOT NULL,
                quantity REAL NOT NULL,
                receiver TEXT,
                team TEXT NOT NULL,
                notes TEXT,
                created_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (material_code) REFERENCES materials(code) ON UPDATE CASCADE
            );
            """)

            # 4. Bảng Mua vào & Chi phí (Purchases)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                voucher_code TEXT,
                purchase_date TEXT,
                material_code TEXT,
                quantity REAL DEFAULT 0.0,
                unit_price REAL DEFAULT 0.0,
                total_amount REAL DEFAULT 0.0,
                supplier TEXT,
                inspection_record TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # 5. Bảng Người dùng & Phân quyền (Users)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT NOT NULL,
                role TEXT NOT NULL,
                project TEXT DEFAULT 'Đồng Hòa',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # 6. Bảng Đề nghị vật tư (Material Requests - ĐNVT / Đối soát CĐT)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS material_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                voucher_code TEXT NOT NULL,
                request_date TEXT NOT NULL,
                material_code TEXT NOT NULL,
                requested_qty REAL DEFAULT 0.0,
                received_qty REAL DEFAULT 0.0,
                difference_qty REAL DEFAULT 0.0,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # 7. Bảng Tổ đội thi công (Teams) - Mở rộng linh hoạt không giới hạn
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS teams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                leader TEXT,
                phone TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # Tự động nạp sẵn các tổ đội mặc định
            default_teams = ["Dũng", "Tổ 1", "Tổ 2", "Tổ 3"]
            for t_name in default_teams:
                cursor.execute("INSERT OR IGNORE INTO teams (name) VALUES (?);", (t_name,))

            conn.commit()
            logger.info("Cơ sở dữ liệu SQLite đã được khởi tạo thành công.")
    except Exception as exc:
        logger.error(f"Lỗi khi khởi tạo cơ sở dữ liệu: {exc}", exc_info=True)
        raise exc


def get_next_voucher_code(voucher_type: str = "receipt") -> str:
    """
    Tự động tính toán số phiếu tiếp theo:
    - receipt: GM... -> GM03
    - issue: PXK... -> PXK07
    - request: PYC... -> PYC02
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            if voucher_type == "receipt":
                cursor.execute("SELECT voucher_code FROM receipts WHERE voucher_code LIKE 'GM%';")
                codes = [r[0] for r in cursor.fetchall() if r[0]]
                prefix = "GM"
            elif voucher_type == "issue":
                cursor.execute("SELECT voucher_code FROM issues WHERE voucher_code LIKE 'PXK%';")
                codes = [r[0] for r in cursor.fetchall() if r[0]]
                prefix = "PXK"
            elif voucher_type == "request":
                cursor.execute("SELECT voucher_code FROM material_requests WHERE voucher_code LIKE 'PYC%';")
                codes = [r[0] for r in cursor.fetchall() if r[0]]
                prefix = "PYC"
            else:
                return "01"

            nums = []
            for c in codes:
                m = re.search(rf"{prefix}(\d+)", c, re.IGNORECASE)
                if m:
                    nums.append(int(m.group(1)))
            next_num = (max(nums) + 1) if nums else 1
            return f"{prefix}{next_num:02d}"
    except Exception as exc:
        logger.error(f"Lỗi khi tính số phiếu tiếp theo ({voucher_type}): {exc}", exc_info=True)
        return "GM01" if voucher_type == "receipt" else ("PXK01" if voucher_type == "issue" else "PYC01")


def get_all_materials() -> List[Dict[str, Any]]:
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT code, name, category_code, brand, unit, contract_qty, requested_qty, audit_qty, notes
                FROM materials
                ORDER BY code ASC;
            """)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception as exc:
        logger.error(f"Lỗi khi lấy danh mục vật tư: {exc}", exc_info=True)
        return []


def get_all_brands() -> List[str]:
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT brand FROM materials WHERE brand IS NOT NULL AND brand != '' ORDER BY brand ASC;")
            rows = cursor.fetchall()
            return [row["brand"] for row in rows]
    except Exception as exc:
        logger.error(f"Lỗi khi lấy danh sách hãng: {exc}", exc_info=True)
        return []


def get_all_request_vouchers() -> List[str]:
    """
    Lấy danh sách các số phiếu yêu cầu (PYC) có trong hệ thống để lọc.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT voucher_code FROM material_requests ORDER BY voucher_code ASC;")
            rows = cursor.fetchall()
            return [row["voucher_code"] for row in rows if row["voucher_code"]]
    except Exception as exc:
        logger.error(f"Lỗi khi lấy danh sách phiếu yêu cầu: {exc}", exc_info=True)
        return []


def get_all_teams() -> List[str]:
    """
    Lấy danh sách tất cả các tổ đội từ bảng teams.
    Hỗ trợ thêm bớt linh hoạt theo yêu cầu người dùng.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM teams ORDER BY id ASC;")
            teams = [row["name"].strip() for row in cursor.fetchall() if row["name"] and row["name"].strip()]
            if not teams:
                return ["Dũng", "Tổ 1", "Tổ 2", "Tổ 3"]
            return teams
    except Exception as exc:
        logger.error(f"Lỗi khi lấy danh sách tổ đội: {exc}", exc_info=True)
        return ["Dũng", "Tổ 1", "Tổ 2", "Tổ 3"]


def add_team(name: str) -> Tuple[bool, str]:
    """
    Thêm mới một tổ đội vào bảng teams.
    """
    if not name or not name.strip():
        return False, "Tên tổ đội không được để trống."
    clean_name = name.strip()
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM teams WHERE LOWER(TRIM(name)) = LOWER(TRIM(?));", (clean_name,))
            if cursor.fetchone():
                return False, f"Tổ đội '{clean_name}' đã có trong danh sách."
            cursor.execute("INSERT INTO teams (name) VALUES (?);", (clean_name,))
            conn.commit()
            return True, f"Đã thêm tổ đội '{clean_name}' thành công."
    except Exception as exc:
        logger.error(f"Lỗi khi thêm tổ đội {clean_name}: {exc}", exc_info=True)
        return False, f"Lỗi hệ thống: {str(exc)}"


def delete_team(name: str) -> Tuple[bool, str]:
    """
    Xóa bớt một tổ đội khỏi bảng teams.
    """
    if not name or not name.strip():
        return False, "Tên tổ đội không hợp lệ."
    clean_name = name.strip()
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM teams WHERE LOWER(TRIM(name)) = LOWER(TRIM(?));", (clean_name,))
            conn.commit()
            return True, f"Đã xóa tổ đội '{clean_name}' khỏi danh sách."
    except Exception as exc:
        logger.error(f"Lỗi khi xóa tổ đội {clean_name}: {exc}", exc_info=True)
        return False, f"Lỗi hệ thống: {str(exc)}"


def add_team_if_not_exists(name: str) -> bool:
    """
    Tự động ghi nhận một tổ đội mới vào bảng teams nếu chưa tồn tại.
    """
    success, _ = add_team(name)
    return success


def is_material_code_exists(code: str) -> bool:
    """
    Kiểm tra nhanh xem mã vật tư đã tồn tại trong danh mục hay chưa (không phân biệt chữ hoa/thường).
    """
    if not code or not code.strip():
        return False
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM materials WHERE LOWER(TRIM(code)) = LOWER(TRIM(?));", (code.strip(),))
            return cursor.fetchone() is not None
    except Exception as exc:
        logger.error(f"Lỗi khi kiểm tra mã vật tư {code}: {exc}", exc_info=True)
        return False


def add_material_strict(code: str, name: str, brand: str = "", unit: str = "Cái",
                        contract_qty: float = 0.0, requested_qty: float = 0.0,
                        category_code: str = "", notes: str = "") -> Tuple[bool, str]:
    """
    Thêm mới một mã vật tư vào hệ thống với quy tắc nghiêm ngặt:
    - Nếu mã đã tồn tại: Cảnh báo "Đã có mã trong danh mục", tuyệt đối KHÔNG ghi đè, KHÔNG tạo mã mới.
    - Chỉ cho phép thêm khi mã vật tư hoàn toàn chưa tồn tại.
    """
    code = (code or "").strip()
    name = (name or "").strip()
    if not code:
        return False, "Mã vật tư không được để trống."
    if not name:
        return False, "Tên vật tư không được để trống."

    brand = (brand or "").strip() or "Khác"
    unit = (unit or "").strip() or "Cái"
    notes = (notes or "").strip()

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name FROM materials WHERE LOWER(TRIM(code)) = LOWER(TRIM(?));", (code,))
            existing = cursor.fetchone()

            if existing:
                # Tuyệt đối không cho phép ghi đè hoặc tự tạo mã mới
                return False, "Đã có mã trong danh mục"

            cursor.execute("""
                INSERT INTO materials (code, name, brand, unit, contract_qty, requested_qty, category_code, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """, (code, name, brand, unit, contract_qty, requested_qty, category_code, notes))
            conn.commit()
            return True, f"Đã thêm mới thành công mã vật tư '{code}' ({name})."
    except Exception as exc:
        logger.error(f"Lỗi khi thêm vật tư {code}: {exc}", exc_info=True)
        return False, f"Lỗi hệ thống: {str(exc)}"


# Định nghĩa alias để mọi vị trí gọi hàm đều áp dụng quy tắc chống ghi đè nghiêm ngặt này
add_or_update_material = add_material_strict


def get_inventory_dashboard_data(search_query: Optional[str] = None, brand_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    try:
        all_teams = get_all_teams()

        with get_db_connection() as conn:
            cursor = conn.cursor()

            # 1. Truy vấn toàn bộ khối lượng xuất kho theo từng tổ đội
            cursor.execute("""
                SELECT material_code, team, SUM(quantity) AS team_out
                FROM issues
                WHERE team IS NOT NULL AND TRIM(team) != ''
                GROUP BY material_code, team;
            """)
            team_out_rows = cursor.fetchall()
            team_issues_map = {}
            for tr in team_out_rows:
                m_code = tr["material_code"].strip() if tr["material_code"] else ""
                t_name = tr["team"].strip() if tr["team"] else ""
                team_issues_map[(m_code, t_name)] = round(tr["team_out"])

            # 2. Truy vấn danh sách vật tư và tổng hợp nhập/xuất
            query = """
                SELECT 
                    m.id,
                    m.code,
                    m.name,
                    m.brand,
                    m.unit,
                    ROUND(m.contract_qty) AS contract_qty,
                    ROUND(m.requested_qty) AS requested_qty,
                    m.audit_qty,
                    ROUND(COALESCE(rec.total_in, 0.0)) AS total_imported,
                    ROUND(COALESCE(iss.total_out, 0.0)) AS total_exported,
                    ROUND(COALESCE(rec.total_in, 0.0) - COALESCE(iss.total_out, 0.0)) AS current_stock
                FROM materials m
                LEFT JOIN (
                    SELECT material_code, SUM(quantity) AS total_in
                    FROM receipts
                    GROUP BY material_code
                ) rec ON m.code = rec.material_code
                LEFT JOIN (
                    SELECT material_code, SUM(quantity) AS total_out
                    FROM issues
                    GROUP BY material_code
                ) iss ON m.code = iss.material_code
            """
            conditions = []
            params = []

            if search_query:
                conditions.append("(m.code LIKE ? OR m.name LIKE ? OR m.brand LIKE ?)")
                like_term = f"%{search_query.strip()}%"
                params.extend([like_term, like_term, like_term])

            if brand_filter and brand_filter.strip() and brand_filter != "--Tất cả--":
                conditions.append("m.brand = ?")
                params.append(brand_filter.strip())

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY m.id ASC;"

            cursor.execute(query, params)
            rows = cursor.fetchall()

            result = []
            for row in rows:
                item = dict(row)
                m_code = item["code"]

                # Gán khối lượng xuất cho từng tổ đội động
                item["team_exports"] = {}
                for t in all_teams:
                    item["team_exports"][t] = team_issues_map.get((m_code, t), 0)

                # Giữ thuộc tính tương thích ngược cho tổ Dũng
                item["team_dung_exported"] = item["team_exports"].get("Dũng", 0)

                if item["current_stock"] <= 0 and item["total_imported"] > 0:
                    item["status"] = "Hết hàng"
                    item["status_class"] = "danger"
                elif item["current_stock"] < (item["contract_qty"] * 0.1) and item["current_stock"] > 0:
                    item["status"] = "Sắp hết"
                    item["status_class"] = "warning"
                elif item["total_imported"] == 0:
                    item["status"] = "Chưa nhập"
                    item["status_class"] = "secondary"
                else:
                    item["status"] = "An toàn"
                    item["status_class"] = "success"
                result.append(item)

            return result
    except Exception as exc:
        logger.error(f"Lỗi khi tính toán bảng tồn kho: {exc}", exc_info=True)
        return []


def get_cdt_reconciliation_data(voucher_filter: Optional[str] = None,
                                brand_filter: Optional[str] = None,
                                search_query: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Tính toán bảng Đối Soát CĐT / Thầu Chính (tương ứng Sheet 'ĐNVT').
    Công thức nghiệp vụ chuẩn:
    - SL Yêu cầu: Khối lượng công trường đề xuất trong phiếu PYC.
    - SL Thực nhận: Tổng số lượng trong bảng receipts có cùng material_code VÀ request_code = mr.voucher_code.
    - Chênh lệch = SL Thực nhận - SL Yêu cầu.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            query = """
                SELECT 
                    mr.id,
                    mr.voucher_code,
                    mr.request_date,
                    mr.material_code,
                    m.name AS material_name,
                    m.category_code,
                    m.brand,
                    m.unit,
                    ROUND(mr.requested_qty) AS requested_qty,
                    ROUND(COALESCE(rec.total_received, 0.0)) AS received_qty,
                    ROUND(COALESCE(rec.total_received, 0.0) - mr.requested_qty) AS diff_qty,
                    mr.notes
                FROM material_requests mr
                LEFT JOIN materials m ON mr.material_code = m.code
                LEFT JOIN (
                    SELECT material_code, request_code, SUM(quantity) AS total_received
                    FROM receipts
                    GROUP BY material_code, request_code
                ) rec ON mr.material_code = rec.material_code AND mr.voucher_code = rec.request_code
            """
            conditions = []
            params = []

            if voucher_filter and voucher_filter.strip() and voucher_filter != "--Tất cả--":
                conditions.append("mr.voucher_code = ?")
                params.append(voucher_filter.strip())

            if brand_filter and brand_filter.strip() and brand_filter != "--Tất cả--":
                conditions.append("m.brand = ?")
                params.append(brand_filter.strip())

            if search_query:
                conditions.append("(mr.material_code LIKE ? OR m.name LIKE ? OR mr.voucher_code LIKE ?)")
                like_term = f"%{search_query.strip()}%"
                params.extend([like_term, like_term, like_term])

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY mr.voucher_code ASC, mr.id ASC;"

            cursor.execute(query, params)
            rows = cursor.fetchall()

            result = []
            for row in rows:
                item = dict(row)
                diff = item["diff_qty"]
                rec = item["received_qty"]

                if diff >= 0 and rec > 0:
                    item["status"] = "Đã cấp đủ 100%"
                    item["status_color"] = "text-emerald-700 bg-emerald-100"
                elif rec > 0 and diff < 0:
                    item["status"] = "CĐT đang cấp dở"
                    item["status_color"] = "text-amber-800 bg-amber-100"
                else:
                    item["status"] = "Chưa giao hàng"
                    item["status_color"] = "text-red-700 bg-red-100"
                result.append(item)

            return result
    except Exception as exc:
        logger.error(f"Lỗi khi tính toán đối soát CĐT: {exc}", exc_info=True)
        return []


def add_material_request_entry(voucher_code: str, request_date: str, material_code: str,
                               requested_qty: float, notes: str) -> bool:
    """
    Lưu phiếu yêu cầu vật tư gửi CĐT mới (ĐNVT).
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO material_requests (voucher_code, request_date, material_code, requested_qty, received_qty, difference_qty, notes)
                VALUES (?, ?, ?, ?, 0.0, ?, ?);
            """, (voucher_code.strip(), request_date.strip(), material_code.strip(),
                  round(float(requested_qty)), -round(float(requested_qty)), notes.strip() if notes else ""))
            conn.commit()
            return True
    except Exception as exc:
        logger.error(f"Lỗi khi thêm ĐNVT: {exc}", exc_info=True)
        return False


def get_material_current_stock(material_code: str) -> float:
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    ROUND(COALESCE((SELECT SUM(quantity) FROM receipts WHERE material_code = ?), 0.0) -
                          COALESCE((SELECT SUM(quantity) FROM issues WHERE material_code = ?), 0.0)) AS stock;
            """, (material_code, material_code))
            row = cursor.fetchone()
            return float(row["stock"]) if row and row["stock"] is not None else 0.0
    except Exception as exc:
        logger.error(f"Lỗi khi lấy tồn kho của {material_code}: {exc}", exc_info=True)
        return 0.0


def get_material_detail_with_history(material_code: str) -> Dict[str, Any]:
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT code, name, category_code, brand, unit, ROUND(contract_qty) as contract_qty, ROUND(requested_qty) as requested_qty
                FROM materials WHERE code = ?;
            """, (material_code,))
            mat_row = cursor.fetchone()
            if not mat_row:
                return {}

            mat = dict(mat_row)

            cursor.execute("""
                SELECT voucher_code, voucher_date, ROUND(quantity) as quantity, supplier, notes, created_by
                FROM receipts WHERE material_code = ?
                ORDER BY voucher_date DESC, id DESC;
            """, (material_code,))
            receipts = [dict(r) for r in cursor.fetchall()]

            cursor.execute("""
                SELECT voucher_code, voucher_date, ROUND(quantity) as quantity, receiver, team, notes, created_by
                FROM issues WHERE material_code = ?
                ORDER BY voucher_date DESC, id DESC;
            """, (material_code,))
            issues = [dict(r) for r in cursor.fetchall()]

            total_in = round(sum(r["quantity"] for r in receipts))
            total_out = round(sum(i["quantity"] for i in issues))
            current_stock = total_in - total_out

            return {
                "material": mat,
                "current_stock": current_stock,
                "total_in": total_in,
                "total_out": total_out,
                "receipts": receipts,
                "issues": issues
            }
    except Exception as exc:
        logger.error(f"Lỗi khi lấy chi tiết vật tư {material_code}: {exc}", exc_info=True)
        return {}


def add_receipt_entry(voucher_code: str, voucher_date: str, material_code: str,
                      quantity: float, supplier: str, request_code: str,
                      notes: str, created_by: str) -> bool:
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO receipts (voucher_code, voucher_date, material_code, quantity, supplier, request_code, notes, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """, (voucher_code.strip(), voucher_date.strip(), material_code.strip(),
                  round(float(quantity)), supplier.strip() if supplier else "",
                  request_code.strip() if request_code else "",
                  notes.strip() if notes else "", created_by))
            conn.commit()
            return True
    except Exception as exc:
        logger.error(f"Lỗi khi thêm phiếu nhập kho: {exc}", exc_info=True)
        return False


def add_issue_entry(voucher_code: str, voucher_date: str, material_code: str,
                    quantity: float, receiver: str, team: str,
                    notes: str, created_by: str) -> bool:
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO issues (voucher_code, voucher_date, material_code, quantity, receiver, team, notes, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """, (voucher_code.strip(), voucher_date.strip(), material_code.strip(),
                  round(float(quantity)), receiver.strip() if receiver else "",
                  team.strip() if team else "Tổ Dũng",
                  notes.strip() if notes else "", created_by))
            conn.commit()
            return True
    except Exception as exc:
        logger.error(f"Lỗi khi thêm phiếu xuất kho: {exc}", exc_info=True)
        return False


def get_all_receipts(search_query: Optional[str] = None,
                     supplier_filter: Optional[str] = None,
                     from_date: Optional[str] = None,
                     to_date: Optional[str] = None,
                     limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Truy vấn toàn bộ lịch sử nhập kho kết hợp thông tin vật tư (tên, hãng, ĐVT).
    Hỗ trợ lọc theo từ khóa, nhà cung cấp và khoảng ngày nhập.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT r.id, r.voucher_code, r.voucher_date, r.material_code, m.name AS material_name,
                       m.brand, m.unit, ROUND(r.quantity) as quantity, r.supplier, r.request_code, 
                       r.notes, r.created_by, r.created_at
                FROM receipts r
                LEFT JOIN materials m ON r.material_code = m.code
            """
            conditions = []
            params = []

            if search_query and search_query.strip():
                kw = f"%{search_query.strip()}%"
                conditions.append("(r.voucher_code LIKE ? OR r.material_code LIKE ? OR m.name LIKE ? OR r.request_code LIKE ? OR r.notes LIKE ?)")
                params.extend([kw, kw, kw, kw, kw])

            if supplier_filter and supplier_filter.strip() and supplier_filter != "--Tất cả--":
                conditions.append("r.supplier = ?")
                params.append(supplier_filter.strip())

            if from_date and from_date.strip():
                conditions.append("r.voucher_date >= ?")
                params.append(from_date.strip())

            if to_date and to_date.strip():
                conditions.append("r.voucher_date <= ?")
                params.append(to_date.strip())

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY r.voucher_date DESC, r.id DESC"

            if limit:
                query += " LIMIT ?"
                params.append(limit)

            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    except Exception as exc:
        logger.error(f"Lỗi khi lấy danh sách lịch sử nhập kho: {exc}", exc_info=True)
        return []


def get_all_suppliers() -> List[str]:
    """
    Lấy danh sách các nhà cung cấp / đối tác đã từng giao hàng nhập kho.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT supplier FROM receipts WHERE supplier IS NOT NULL AND TRIM(supplier) != '' ORDER BY supplier ASC;")
            suppliers = [row["supplier"].strip() for row in cursor.fetchall() if row["supplier"] and row["supplier"].strip()]
            default_suppliers = ["Bạch Đằng", "Hùng Cường", "Sino", "Cadisun", "Xuân Lộc Thọ"]
            for s in default_suppliers:
                if s not in suppliers:
                    suppliers.append(s)
            return sorted(suppliers)
    except Exception as exc:
        logger.error(f"Lỗi khi lấy danh sách nhà cung cấp: {exc}", exc_info=True)
        return ["Bạch Đằng", "Hùng Cường", "Sino", "Cadisun", "Xuân Lộc Thọ"]


def get_recent_receipts(limit: int = 50) -> List[Dict[str, Any]]:
    return get_all_receipts(limit=limit)


def get_all_issues(search_query: Optional[str] = None,
                   team_filter: Optional[str] = None,
                   from_date: Optional[str] = None,
                   to_date: Optional[str] = None,
                   limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Truy vấn toàn bộ lịch sử xuất kho kèm thông tin chi tiết vật tư (Tên, Hãng, ĐVT).
    Hỗ trợ lọc theo từ khóa, tổ đội nhận và khoảng ngày xuất.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT i.id, i.voucher_code, i.voucher_date, i.material_code, m.name AS material_name,
                       m.brand, m.unit, ROUND(i.quantity) as quantity, i.receiver, i.team, i.notes, 
                       i.created_by, i.created_at
                FROM issues i
                LEFT JOIN materials m ON i.material_code = m.code
            """
            conditions = []
            params = []

            if search_query and search_query.strip():
                kw = f"%{search_query.strip()}%"
                conditions.append("(i.voucher_code LIKE ? OR i.material_code LIKE ? OR m.name LIKE ? OR i.receiver LIKE ? OR i.team LIKE ? OR i.notes LIKE ?)")
                params.extend([kw, kw, kw, kw, kw, kw])

            if team_filter and team_filter.strip() and team_filter != "--Tất cả--":
                conditions.append("i.team = ?")
                params.append(team_filter.strip())

            if from_date and from_date.strip():
                conditions.append("i.voucher_date >= ?")
                params.append(from_date.strip())

            if to_date and to_date.strip():
                conditions.append("i.voucher_date <= ?")
                params.append(to_date.strip())

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY i.voucher_date DESC, i.id DESC"

            if limit:
                query += " LIMIT ?"
                params.append(limit)

            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    except Exception as exc:
        logger.error(f"Lỗi khi lấy danh sách lịch sử xuất kho: {exc}", exc_info=True)
        return []


def get_recent_issues(limit: int = 50) -> List[Dict[str, Any]]:
    return get_all_issues(limit=limit)


def get_reconciliation_summary() -> List[Dict[str, Any]]:
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    m.code,
                    m.name,
                    m.unit,
                    ROUND(COALESCE(rec.total_in, 0.0)) AS site_import_qty,
                    ROUND(COALESCE(pur.total_pur, 0.0)) AS office_purchase_qty,
                    ROUND(COALESCE(rec.total_in, 0.0) - COALESCE(pur.total_pur, 0.0)) AS diff_import,
                    ROUND(COALESCE(iss.total_out, 0.0)) AS site_export_qty,
                    ROUND(COALESCE(iss.total_out, 0.0)) AS office_export_qty,
                    0.0 AS diff_export
                FROM materials m
                LEFT JOIN (
                    SELECT material_code, SUM(quantity) AS total_in FROM receipts GROUP BY material_code
                ) rec ON m.code = rec.material_code
                LEFT JOIN (
                    SELECT material_code, SUM(quantity) AS total_pur FROM purchases GROUP BY material_code
                ) pur ON m.code = pur.material_code
                LEFT JOIN (
                    SELECT material_code, SUM(quantity) AS total_out FROM issues GROUP BY material_code
                ) iss ON m.code = iss.material_code
                WHERE COALESCE(rec.total_in, 0.0) > 0 OR COALESCE(iss.total_out, 0.0) > 0 OR COALESCE(pur.total_pur, 0.0) > 0
                ORDER BY m.code ASC;
            """)
            return [dict(row) for row in cursor.fetchall()]
    except Exception as exc:
        logger.error(f"Lỗi khi truy vấn đối soát: {exc}", exc_info=True)
        return []


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, username, password_hash, full_name, role, project FROM users WHERE username = ?;", (username.strip(),))
            row = cursor.fetchone()
            return dict(row) if row else None
    except Exception as exc:
        logger.error(f"Lỗi khi tìm người dùng {username}: {exc}", exc_info=True)
        return None


def create_or_update_user(username: str, password_raw: str, full_name: str, role: str) -> bool:
    try:
        password_hash = generate_password_hash(password_raw)
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO users (username, password_hash, full_name, role)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(username) DO UPDATE SET
                    password_hash = excluded.password_hash,
                    full_name = excluded.full_name,
                    role = excluded.role;
            """, (username.strip(), password_hash, full_name.strip(), role.strip()))
            conn.commit()
            return True
    except Exception as exc:
        logger.error(f"Lỗi khi tạo người dùng {username}: {exc}", exc_info=True)
        return False
