"""
Sync ข้อมูล attendance จากเครื่องสแกน ZKTeco → Odoo

Logic:
1. ดึง scan ทั้งหมดจาก ZK
2. ดึง employees จาก Odoo สร้าง map: PIN → employee_id
3. จัดกลุ่ม scans ตาม user เรียงเวลา → คู่ check_in/check_out
4. ส่งเข้า Odoo (skip ถ้า duplicate)
"""
import xmlrpc.client
import ssl
import os
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from zk import ZK

# ZK ส่งเวลาเป็น local time (ไทย UTC+7) แต่ Odoo เก็บ UTC → ต้อง convert
# ใช้ fixed offset เพราะไทยไม่มี DST
LOCAL_TZ = timezone(timedelta(hours=7))
UTC_TZ = timezone.utc


def to_odoo_utc_str(local_dt):
    """แปลง datetime ไทย (naive) → UTC string สำหรับส่งเข้า Odoo"""
    return (
        local_dt.replace(tzinfo=LOCAL_TZ)
        .astimezone(UTC_TZ)
        .strftime('%Y-%m-%d %H:%M:%S')
    )

load_dotenv()

# ===== Config =====
ZK_IP = os.getenv("ZK_IP")
ZK_PORT = int(os.getenv("ZK_PORT", 4370))
ZK_PASSWORD = int(os.getenv("ZK_PASSWORD", 0))

ODOO_URL = os.getenv("ODOO_URL")
ODOO_DB = os.getenv("ODOO_DB")
ODOO_USERNAME = os.getenv("ODOO_USERNAME")
ODOO_API_KEY = os.getenv("ODOO_API_KEY")

SSL_CONTEXT = ssl._create_unverified_context()


# ============================================================
# 1. ZK functions
# ============================================================
def fetch_zk_attendance():
    """ดึง attendance records ทั้งหมดจากเครื่องสแกน"""
    print(f"[ZK] เชื่อมต่อ {ZK_IP}...")
    zk = ZK(ZK_IP, port=ZK_PORT, timeout=15, password=ZK_PASSWORD,
            force_udp=False, ommit_ping=True)
    conn = None
    try:
        conn = zk.connect()
        attendances = conn.get_attendance()
        print(f"[ZK] ดึงมาได้ {len(attendances)} records")
        return attendances
    finally:
        if conn:
            conn.disconnect()


# ============================================================
# 2. Odoo functions
# ============================================================
def odoo_login():
    """Login Odoo คืน (uid, models_proxy)"""
    common = xmlrpc.client.ServerProxy(
        f"{ODOO_URL}/xmlrpc/2/common", context=SSL_CONTEXT
    )
    uid = common.authenticate(ODOO_DB, ODOO_USERNAME, ODOO_API_KEY, {})
    if not uid:
        raise Exception("Odoo login fail — เช็ค .env")
    print(f"[Odoo] login OK (uid={uid})")
    models = xmlrpc.client.ServerProxy(
        f"{ODOO_URL}/xmlrpc/2/object", context=SSL_CONTEXT
    )
    return uid, models


def get_pin_to_employee_map(uid, models):
    """ดึง employees ทั้งหมด สร้าง dict: pin -> employee_id"""
    employees = models.execute_kw(
        ODOO_DB, uid, ODOO_API_KEY,
        'hr.employee', 'search_read',
        [[['pin', '!=', False]]],
        {'fields': ['id', 'name', 'pin']}
    )
    pin_map = {}
    for emp in employees:
        if emp['pin']:
            pin_map[str(emp['pin'])] = {'id': emp['id'], 'name': emp['name']}
    print(f"[Odoo] พบ employee ที่มี PIN {len(pin_map)} คน")
    return pin_map


def attendance_exists(uid, models, employee_id, check_in_str):
    """เช็คว่ามี attendance record นี้แล้วหรือยัง (กัน duplicate)"""
    ids = models.execute_kw(
        ODOO_DB, uid, ODOO_API_KEY,
        'hr.attendance', 'search',
        [[
            ['employee_id', '=', employee_id],
            ['check_in', '=', check_in_str],
        ]],
        {'limit': 1}
    )
    return bool(ids)


def create_attendance(uid, models, employee_id, check_in, check_out=None):
    """สร้าง hr.attendance record ใหม่ใน Odoo (convert เวลาไทย → UTC)"""
    vals = {
        'employee_id': employee_id,
        'check_in': to_odoo_utc_str(check_in),
    }
    if check_out:
        vals['check_out'] = to_odoo_utc_str(check_out)

    return models.execute_kw(
        ODOO_DB, uid, ODOO_API_KEY,
        'hr.attendance', 'create',
        [vals]
    )


# ============================================================
# 3. Pairing logic — จับคู่ check_in/check_out
# ============================================================
def pair_scans(scans):
    """
    รับ list ของ scan ที่เรียงเวลาแล้ว
    คืน list ของ tuple (check_in, check_out)
    ถ้าจำนวนคี่ → record สุดท้ายมีแค่ check_in (ยังไม่ออก)
    """
    pairs = []
    i = 0
    while i < len(scans):
        check_in = scans[i].timestamp
        check_out = scans[i + 1].timestamp if i + 1 < len(scans) else None
        pairs.append((check_in, check_out))
        i += 2
    return pairs


# ============================================================
# 4. Main sync logic
# ============================================================
def main():
    print("=" * 60)
    print("SYNC ZK → Odoo")
    print("=" * 60)

    # ---- ดึงข้อมูลจาก ZK ----
    zk_attendances = fetch_zk_attendance()
    if not zk_attendances:
        print("ไม่มี scan ใน ZK")
        return

    # ---- Login Odoo ----
    uid, models = odoo_login()
    pin_map = get_pin_to_employee_map(uid, models)

    if not pin_map:
        print("[X] ไม่มี employee ใน Odoo ที่ตั้ง PIN — ต้องไปสร้างก่อน")
        return

    # ---- จัดกลุ่ม scan ตาม user_id ----
    scans_by_user = defaultdict(list)
    for att in zk_attendances:
        scans_by_user[str(att.user_id)].append(att)

    # เรียงตามเวลา
    for uid_key in scans_by_user:
        scans_by_user[uid_key].sort(key=lambda a: a.timestamp)

    # ---- Sync แต่ละคน ----
    print("\n" + "-" * 60)
    total_created = 0
    total_skipped = 0
    total_missing = 0

    for zk_user_id, scans in scans_by_user.items():
        emp = pin_map.get(zk_user_id)
        if not emp:
            print(f"[!] ZK user_id={zk_user_id} ไม่มี employee ตรงใน Odoo (skip)")
            total_missing += len(scans)
            continue

        pairs = pair_scans(scans)
        print(f"\n[Sync] {emp['name']} (pin={zk_user_id}) → {len(pairs)} record(s)")

        for check_in, check_out in pairs:
            check_in_utc = to_odoo_utc_str(check_in)
            check_in_display = check_in.strftime('%Y-%m-%d %H:%M:%S')

            if attendance_exists(uid, models, emp['id'], check_in_utc):
                print(f"   - SKIP (มีอยู่แล้ว) {check_in_display}")
                total_skipped += 1
                continue

            new_id = create_attendance(uid, models, emp['id'], check_in, check_out)
            out_str = check_out.strftime('%H:%M:%S') if check_out else '(ยังไม่ออก)'
            print(f"   + CREATE id={new_id}  {check_in_display} → {out_str}")
            total_created += 1

    print("\n" + "=" * 60)
    print(f"SUMMARY: created={total_created}  skipped={total_skipped}  "
          f"missing_employee={total_missing}")
    print("=" * 60)


if __name__ == "__main__":
    main()
