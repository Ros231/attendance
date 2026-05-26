from zk import ZK

ZK_IP = '192.168.1.215'
ZK_PORT = 4370
ZK_PASSWORD = 123456

def list_users():
    zk = ZK(ZK_IP, port=ZK_PORT, timeout=15, password=ZK_PASSWORD,
            force_udp=False, ommit_ping=True)
    conn = None
    try:
        print(f"เชื่อมต่อ {ZK_IP}...")
        conn = zk.connect()
        print("เชื่อมต่อสำเร็จ! กำลังดึงรายชื่อ user...\n")

        users = conn.get_users()

        if not users:
            print("ยังไม่มี user ในเครื่อง — ไปลงทะเบียนที่หน้าเครื่องก่อน")
            return

        print(f"พบ user ทั้งหมด {len(users)} คน:")
        print("-" * 70)
        print(f"{'user_id':<10}{'name':<25}{'privilege':<12}{'card':<12}")
        print("-" * 70)
        for u in users:
            priv = 'Admin' if u.privilege == 14 else 'User'
            print(f"{u.user_id:<10}{u.name:<25}{priv:<12}{u.card:<12}")

    except Exception as e:
        print(f"เกิดข้อผิดพลาด: {e}")
    finally:
        if conn:
            conn.disconnect()

if __name__ == "__main__":
    list_users()
