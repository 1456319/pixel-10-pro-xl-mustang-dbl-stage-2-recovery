# Forensic UFS In-Place Repair Specification
**Device:** Google Pixel 10 Pro XL (`mustang`)  
**SoC:** Google Tensor G5 (`lga`)  
**Security Co-Processor:** Titan M2  
**Storage:** Micron / Samsung UFS 4.0  
**Device Serial:** `2690e8f2b033600b85a6c95d72902a30`  
**Factory Firmware Baseline:** Summer 2025 Launch Baseline (`version-dbl: 13675915`)  
**Target:** 100% Zero-Loss Recovery of `/userdata` (FBE Crypto Wallet & Documents)

---

## 1. Executive Summary & Problem Definition

The phone is soft-bricked in Stage 2 DBL emergency USB mode (`18d1:4ee0`, `boot-stage: dbl`). The internal `/userdata` partition is completely intact but locked under Android File-Based Encryption (FBE).

### The Mathematical Deadlock on USB:
Comprehensive reverse-engineering of factory bootloader `dbl.img` (`13675915` and `14624666`) proved that pure-USB tethered booting is structurally impossible from this state:
1. **The PInfo Gate (`0x09003930`):** The unencrypted `PInfo` partition has a non-zero 16-bit flag word at offset `+0x06` (`0x09003924: ldrh w10, [sp, #0xb86]`), causing DBL to branch (`cbnz w10, #0x9003f50`) directly to the emergency Fastboot listener, bypassing slot exhaustion logic and bypassing the `bBootLunEn` clearing function (`0x09015240`).
2. **The Boot Medium Gate (`0x0900139c`):** Because `bBootLunEn` is never cleared on UFS, APROM (BootROM) boots DBL from UFS on every power cycle, setting `[BOOTCNTX + 0x14] = 2` (`0x200`). At `0x0900139c: cmp x8, #0x200; b.eq #0x9001364`, DBL unconditionally skips `0x1a7d0005` (SWITCH GSA TO RECOVERY MODE).
3. **The GSA Rejection:** With GSA in Normal Mode, GSA rejects in-memory `0x1a7d0001` (`gsa_bl1.img`), halting the CPU at `smc #0; b .` until the 26-second hardware watchdog bites.

**Conclusion:** Pure-USB software recovery is mathematically exhausted. The root cause is stored in two **unencrypted, plaintext partitions on UFS**: `devinfo` and `PInfo`.

---

## 2. Cryptographic Architecture & Constraints

> [!CRITICAL]
> **DO NOT SWAP MOTHERBOARDS. DO NOT SEPARATE UFS CHIP PERMANENTLY FROM SOC.**
> In Tensor G5, `/userdata` is encrypted with File-Based Encryption (FBE) utilizing hardware-wrapped keys derived from:
> 1. The hardware Root-of-Trust (RoT) burned into the **Tensor G5 SoC silicon UID**.
> 2. The secure element hardware secret inside the **Titan M2 security chip**.
> 3. The user's **knowledge factor (PIN / pattern / password)**.
> 
> If the UFS chip is read in a standalone socket, `/userdata` will appear as high-entropy AES-256-XTS ciphertext and cannot be decrypted without the physical Tensor G5 SoC and Titan M2. The repair **must be performed in-place** (or via temporary chip-off rework returned to the original motherboard).

---

## 3. Forensic Rework Procedure

A forensic hardware facility (e.g., iPad Rehab, DriveSavers, or Gillware) with UFS 4.0 ISP (In-System Programming) or BGA-153 rework equipment must perform the following:

### Step 1: Physical Interface
- **Method A (Preferred - ISP Fly-Wire):** Connect via high-speed ISP micro-soldering to the UFS 4.0 test points on the motherboard:
  - `CLK`, `CMD`, `DAT0`, `VCC` (2.5V/3.3V), `VCCQ` (1.2V), `VCCQ2` (1.8V), `GND`.
  - Tools: EasyJTAG Plus with UFS 4.0 socket/ISP adapter, Medusa Pro II, or MIPI Tester.
- **Method B (Alternative - BGA Rework):**
  - Desolder UFS 4.0 BGA chip using controlled IR/hot-air profile (< 230°C peak).
  - Place in UFS 4.0 BGA-153 socket for direct read/write.
  - Reball and resolder back to original motherboard after modification.

### Step 2: Binary Modifications on Plaintext UFS LUNs

#### A. Target 1: `devinfo` Partition (Plaintext LUN / Sector)
- Search for ASCII magic `'DEVI'` (`0x44455649` at partition offset `0x00`).
- **Slot Status & Retry Counter Bytes:**
  - Locate Slot A and Slot B metadata structures at offset `+0x30` / `+0x34` (and `+0x60` / `+0x64`).
  - Set `slot_a.tries_remaining = 7` (Byte value `0x07`).
  - Set `slot_a.successful_boot = 1` (Byte value `0x01`).
  - Set `slot_a.active = 1` (Bitmask flags `0x0c` or `0x01`).
  - Clear `force_dram_training` flag at offset `+0x5d` to `0x00`.

#### B. Target 2: `PInfo` Partition (Plaintext LUN / Sector)
- Search for ASCII magic `'PINF'` (`0x464e4950` at partition offset `0x00`).
- Offset `+0x04`: Major version (`0x0001`, 2 bytes).
- **Offset `+0x06`: Recovery Flag Word (2 bytes):**
  - **Change from `0x0001` (or existing non-zero value) to `0x0000`.**
  - Setting `[PInfo + 0x06] = 0x0000` satisfies `0x09003930: cbnz w10, #0x9003f50` as FALSE (`w10 == 0`), allowing DBL to proceed to normal slot boot.

#### C. Target 3: Full Physical Clone (Safety Backup)
- Before writing, create a complete 1:1 bitstream forensic image (E01 or raw DD) of all UFS LUNs:
  - `LUN 0` (User data / system partitions)
  - `LUN 1` / `LUN 2` (Boot LUNs / DBL)
  - `RPMB` (Replay Protected Memory Block - read counter status)

---

## 4. Boot-Up & Decryption

1. Reassemble motherboard with the modified UFS chip.
2. Connect battery and power on normally (or via Power button).
3. **Execution Path:**
   - APROM (BootROM) loads DBL from UFS.
   - DBL reads `PInfo`: offset `+0x06` is `0x0000`, so `cbnz w10` does NOT branch to Fastboot.
   - DBL reads `devinfo`: `slot_a.tries_remaining = 7`, `slot_a.active = 1`.
   - DBL loads Batch 1, initializes DRAM, loads GSA FW, and boots `abl` (Android Bootloader) into RAM.
   - `abl` boots Linux kernel and Android userland.
4. The Pixel 10 Pro XL boots to the familiar lockscreen.
5. User enters their lockscreen PIN. Titan M2 releases the synthetic encryption key, and Android decrypts `/userdata`.
6. Immediate backup of crypto keys, seed phrases, and personal documents over USB.
