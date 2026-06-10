from shi.binout import binout

print("--- Demo 1: Slices and Combined View ---")
# 0x12345678
val = 0x12345678
fields = {"High Word": slice(16, 32), "Low Word": slice(0, 16)}
binout(val, bits=32, fields=fields)

print("\n--- Demo 2: Inverse Value ---")
# 0xFF00AA55
val2 = 0xFF00AA55
binout(val2, bits=32)

print("\n--- Demo 3: Network Header with Slices ---")
# Mock IP Header: Version(4), IHL(4), DSCP(6), ECN(2), Total Length(16)
# 0x45000054
ip_header = 0x45000054
fields_ip = {
    "Version": (28, 4, "red"),
    "IHL": (24, 4, "blue"),
    "DSCP": slice(18, 24),  # Using slice for DSCP
    "ECN": slice(16, 18),  # Using slice for ECN
    "Total Length": slice(0, 16),
}
binout(ip_header, bits=32, fields=fields_ip)
