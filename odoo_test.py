"""
ทดสอบเชื่อมต่อ Odoo + ดึงรายชื่อ Employee
"""
import xmlrpc.client
import ssl
import os
from dotenv import load_dotenv

load_dotenv()

ODOO_URL = os.getenv("ODOO_URL")
ODOO_DB = os.getenv("ODOO_DB")
ODOO_USERNAME = os.getenv("ODOO_USERNAME")
ODOO_API_KEY = os.getenv("ODOO_API_KEY")

# ===== SSL Context =====
# ปิด SSL verify เพราะ dev.pako.co.th ใช้ self-signed / internal CA cert
# OK สำหรับ internal server ที่เรา trust แล้ว
SSL_CONTEXT = ssl._create_unverified_context()


def main():
    print(f"กำลังเชื่อมต่อ {ODOO_URL} (db: {ODOO_DB})...\n")

    # ===== STEP A: Authenticate =====
    common = xmlrpc.client.ServerProxy(
        f"{ODOO_URL}/xmlrpc/2/common", context=SSL_CONTEXT
    )

    version_info = common.version()
    print(f"Odoo version: {version_info['server_version']}")

    uid = common.authenticate(ODOO_DB, ODOO_USERNAME, ODOO_API_KEY, {})

    if not uid:
        print("[X] Login ไม่ผ่าน — เช็ค username/api_key/db ใน .env")
        return

    print(f"[OK] Login สำเร็จ! user_id = {uid}\n")

    # ===== STEP B: เรียก execute_kw ดึง employees =====
    models = xmlrpc.client.ServerProxy(
        f"{ODOO_URL}/xmlrpc/2/object", context=SSL_CONTEXT
    )

    employees = models.execute_kw(
        ODOO_DB, uid, ODOO_API_KEY,
        'hr.employee',
        'search_read',
        [[]],
        {'fields': ['id', 'name', 'pin', 'work_email'], 'limit': 50}
    )

    if not employees:
        print("ยังไม่มี Employee ใน Odoo")
        return

    print(f"พบ Employee {len(employees)} คน:")
    print("-" * 70)
    print(f"{'id':<6}{'pin':<8}{'name':<30}{'email':<30}")
    print("-" * 70)
    for emp in employees:
        print(f"{emp['id']:<6}{str(emp.get('pin') or '-'):<8}"
              f"{(emp['name'] or '-')[:28]:<30}"
              f"{str(emp.get('work_email') or '-')[:28]:<30}")


if __name__ == "__main__":
    main()
