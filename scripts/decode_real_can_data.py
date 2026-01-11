#!/usr/bin/env python3
"""
Decode real CAN data from 2013 Leaf capture to understand message structure
"""

# Sample 0x1CB frames from initialscan.csv
frames_1cb = [
    "00 09 FF CE 60 00 80",
    "00 09 FF CE 60 01 05",
    "00 09 FF CE 60 02 0F",
    "00 09 FF CE 60 03 8A",
    "00 01 FF CE 60 00 A9",
    "00 01 FF CE 60 01 2C",
    "00 01 FF CE 60 02 26",
    "00 01 FF CE 60 03 A3",
]

# Sample 0x1CC frames
frames_1cc = [
    "00 3F F5 CA",
    "00 3F F5 DB",
    "00 3F F5 E8",
    "00 3F F5 F9",
    "00 3F F5 06",
    "00 3F F5 17",
]

# 0x5B3 frame (we know this one!)
frame_5b3 = "64 58 FF FB C0 7E 5E 0A"

print("="*80)
print("Decoding 0x1CB (Unknown battery/brake message)")
print("="*80)

for frame in frames_1cb:
    bytes_list = [int(b, 16) for b in frame.split()]

    # Try different interpretations
    b0 = bytes_list[0]
    b1 = bytes_list[1]
    b0_b1 = (bytes_list[0] << 8) | bytes_list[1]

    b2 = bytes_list[2]
    b3 = bytes_list[3]
    b2_b3 = (bytes_list[2] << 8) | bytes_list[3]

    b4 = bytes_list[4]

    b5 = bytes_list[5]
    b6 = bytes_list[6]
    b5_b6 = (bytes_list[5] << 8) | bytes_list[6]

    print(f"\nFrame: {frame}")
    print(f"  Byte 0-1: 0x{b0:02X}{b1:02X} = {b0_b1} dec")
    print(f"  Byte 2-3: 0x{b2:02X}{b3:02X} = {b2_b3} dec  (if voltage * 0.5 = {b2_b3 * 0.5:.1f}V)")
    print(f"  Byte 4:   0x{b4:02X} = {b4} dec")
    print(f"  Byte 5-6: 0x{b5:02X}{b6:02X} = {b5_b6} dec")

print("\n" + "="*80)
print("Decoding 0x1CC (Temperature?)")
print("="*80)

for frame in frames_1cc:
    bytes_list = [int(b, 16) for b in frame.split()]

    b0 = bytes_list[0]
    b1 = bytes_list[1]
    b2 = bytes_list[2]
    b3 = bytes_list[3]

    b2_b3 = (bytes_list[2] << 8) | bytes_list[3]

    print(f"\nFrame: {frame}")
    print(f"  Byte 0: 0x{b0:02X} = {b0} dec")
    print(f"  Byte 1: 0x{b1:02X} = {b1} dec")
    print(f"  Byte 2: 0x{b2:02X} = {b2} dec")
    print(f"  Byte 3: 0x{b3:02X} = {b3} dec (if temp: {b3 - 40}°C)")
    print(f"  Byte 2-3: 0x{b2_b3:04X} = {b2_b3} dec")

print("\n" + "="*80)
print("Decoding 0x5B3 (Known: SOH & GIDs)")
print("="*80)

bytes_list = [int(b, 16) for b in frame_5b3.split()]
byte_b = bytes_list[1]
byte_f = bytes_list[5]

soh = byte_b >> 1
gids = byte_f
capacity_wh = gids * 80

print(f"Frame: {frame_5b3}")
print(f"  Byte 1 (B): 0x{byte_b:02X} = {byte_b} → SOH = {byte_b} >> 1 = {soh}%")
print(f"  Byte 5 (F): 0x{byte_f:02X} = {byte_f} → GIDs = {gids} → {capacity_wh} Wh = {capacity_wh/1000:.2f} kWh")
print(f"\n  → Battery: {soh}% SOH, {capacity_wh/1000:.2f} kWh remaining")
