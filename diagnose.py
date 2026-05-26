import socket

ZK_IP = '192.168.1.215'
PORTS = [4370, 80, 8080, 443, 4011, 5005, 5200]

def test_tcp(ip, port, timeout=3):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((ip, port))
        return "OPEN"
    except socket.timeout:
        return "TIMEOUT"
    except ConnectionRefusedError:
        return "REFUSED"
    except Exception as e:
        return f"ERROR: {e}"
    finally:
        s.close()

def test_udp(ip, port, timeout=3):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    try:
        s.sendto(b'\x50\x50\x82\x7d\x13\x00\x00\x00\xe8\x03\x17\x9c\x00\x00\x00\x00', (ip, port))
        data, _ = s.recvfrom(1024)
        return f"REPLIED ({len(data)} bytes)"
    except socket.timeout:
        return "NO REPLY"
    except Exception as e:
        return f"ERROR: {e}"
    finally:
        s.close()

print(f"Scanning {ZK_IP}...\n")
print(f"{'PORT':<8}{'TCP':<25}{'UDP':<25}")
print("-" * 60)
for p in PORTS:
    tcp_result = test_tcp(ZK_IP, p)
    udp_result = test_udp(ZK_IP, p)
    print(f"{p:<8}{tcp_result:<25}{udp_result:<25}")
