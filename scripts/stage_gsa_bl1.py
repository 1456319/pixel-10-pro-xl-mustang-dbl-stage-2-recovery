#!/usr/bin/env python3
import sys
import time
import usb.core
import usb.util

def main():
    print("[*] Searching for Google Pixel (18d1:4ee0) in DBL recovery mode...")
    dev = usb.core.find(idVendor=0x18d1, idProduct=0x4ee0)
    if dev is None:
        print("[-] Device 18d1:4ee0 not found on USB bus.")
        return 1

    print(f"[+] Found device: Bus {dev.bus} Device {dev.address}")
    
    cfg = dev.get_active_configuration()
    intf = cfg[(0, 0)]

    ep_out = usb.util.find_descriptor(
        intf,
        custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT
    )
    ep_in = usb.util.find_descriptor(
        intf,
        custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN
    )

    if not ep_out or not ep_in:
        print("[-] Could not find Bulk OUT (0x01) and Bulk IN (0x81) endpoints.")
        return 1

    print(f"[+] Bulk Endpoints: OUT=0x{ep_out.bEndpointAddress:02x}, IN=0x{ep_in.bEndpointAddress:02x}")

    def send_cmd(cmd_bytes, timeout=2000):
        ep_out.write(cmd_bytes, timeout=timeout)
        resp = bytes(ep_in.read(512, timeout=timeout))
        return resp

    # 1. Query initial stage variables
    for var in [b"product", b"boot-stage", b"next-boot-stage"]:
        resp = send_cmd(b"getvar:" + var)
        print(f"[*] getvar:{var.decode()} -> {resp.decode(errors='replace')}")

    # 2. Read gsa_bl1.img
    img_path = "/home/deck/Downloads/extracted_ota/gsa_bl1.img"
    with open(img_path, "rb") as f:
        payload = f.read()

    size = len(payload)
    print(f"[*] Loaded {img_path} ({size} bytes, expected 32768)")
    assert size == 0x8000, f"Payload size must be 0x8000, got {size}"

    # 3. Handshake download
    cmd = f"download:{size:08x}".encode("ascii")
    print(f"[*] Sending {cmd.decode()}...")
    resp = send_cmd(cmd)
    print(f"[*] Handshake response: {resp.decode(errors='replace')}")

    if not resp.startswith(b"DATA"):
        print(f"[-] Device rejected download: {resp}")
        usb.util.dispose_resources(dev)
        return 1

    # 4. Stream full payload in a single contiguous transfer
    print("[*] Writing contiguous 32768-byte payload to EP OUT...")
    bytes_written = ep_out.write(payload, timeout=5000)
    print(f"[+] Contiguous write complete: {bytes_written} bytes transferred.")

    # 5. Cleanly release USB resources (DBL exits fastboot immediately without OKAY)
    print("[*] Disposing USB interface resources to allow DBL handoff to GSA...")
    usb.util.dispose_resources(dev)
    print("[+] Resources released cleanly. Awaiting DBL / GSA verification...")
    time.sleep(1.0)
    return 0

if __name__ == "__main__":
    sys.exit(main())
