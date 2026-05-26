from zk import ZK

# ตั้งค่า IP ของเครื่องสแกน ZKTeco
ZK_IP = '192.168.1.215'
ZK_PORT = 4370

def test_connection():
    zk = ZK(ZK_IP, port=ZK_PORT, timeout=15, password=123456, force_udp=False, ommit_ping=True)
    conn = None
    try:
        print(f"กำลังเชื่อมต่อไปที่ {ZK_IP}...")
        conn = zk.connect()
        print("เชื่อมต่อสำเร็จ! กำลังดึงข้อมูล...\n")
        
        # ดึงข้อมูล Log การสแกนทั้งหมด
        attendances = conn.get_attendance()
        
        if not attendances:
            print("เครื่องว่างเปล่า ยังไม่มีใครมาสแกนเลยครับ")
            return

        print(f"พบข้อมูลการสแกนทั้งหมด {len(attendances)} รายการ:")
        print("-" * 50)
        
        # วนลูปพ่นข้อมูลออกมาดูทีละบรรทัด
        for att in attendances:
            print(f"รหัสพนักงาน: {att.user_id} | เวลาสแกน: {att.timestamp}")
            
    except Exception as e:
        print(f"เกิดข้อผิดพลาด: {e}")
        print("เช็คให้ชัวร์ว่าคอมพิวเตอร์กับเครื่องสแกนต่อเน็ต/Wi-Fi วงเดียวกันไหม")
    finally:
        if conn:
            conn.disconnect()

if __name__ == "__main__":
    test_connection()