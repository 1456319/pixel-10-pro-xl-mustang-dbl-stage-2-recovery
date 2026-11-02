# Google Pixel 10 Pro XL (`mustang` / Tensor G5) Stage 2 DBL Recovery

Reverse-engineered technical specification and tooling for recovering a Google Pixel 10 Pro XL (`mustang`, Tensor G5 `lga` / `laguna`) trapped in **Stage 2 DBL USB Fastboot mode** (`idVendor=18d1, idProduct=4ee0`, black screen).

---

## 1. Background & Failure Mode

When a Pixel 10 family device exhausts boot retry counters on both Slot A and Slot B (`slot-retry-count:a == 0`, `slot-retry-count:b == 0`) inside the non-volatile `devinfo` partition on UFS storage:

```text
A/B: Both slots (A and B) are invalid
UFS active slot does not match devinfo active slot. Updating devinfo to match UFS
Assuming devinfo a/b slot data is correct
Forcing device into ROM recovery
```

1. The device does **not** fall back to Stage 1 BootROM serial recovery (`18d1:4f00`, "Pixel ROM Recovery").
2. Instead, UFS successfully loads **Stage 2 (`dbl.img`)**.
3. `dbl` initializes the Synopsys DWC3 USB Device Controller (UDC) and exposes a minimal USB Fastboot interface (`18d1:4ee0`):
   - `getvar:boot-stage` -> `OKAYdbl`
   - `getvar:next-boot-stage` -> `OKAYgsa_bl1`
   - `getvar:is-last-boot-stage` -> `OKAYno`
   - `getvar:product` -> `OKAYlga`
   - `getvar:version-dbl` -> `OKAY14451019`
   - `getvar:version` -> `OKAY0.4`

In this mode, `dbl` is waiting for the host to tether-load the next boot stage (`gsa_bl1.img`) over USB into RAM.

---

## 2. Reverse-Engineered Architecture of `dbl.img`

- **Binary Type**: AArch64 64-bit ELF-derived raw binary compiled with Rust/LLVM.
- **Header**: `0x1000` (4096-byte) multiloc container header.
- **Runtime Base Virtual Address**: `0x09000000` ($\text{VA} = \text{File\_Offset} - 0x1000 + 0x09000000$).
- **Function Entry Point**: `0x09015ad4` (`stp x29, x30, [sp, #-0x60]!; sub sp, sp, #0x210`).

### Fastboot Command Dispatcher (`0x09015e60`..`0x09016000`)

DBL implements **only two** Fastboot commands:
1. `getvar:` (`0x09015e84`): Evaluates requested variable against the stack variable table.
2. `download:` (`0x09015ef4`): Expects an 8-character hexadecimal byte length (e.g. `download:00008000` for 32,768 bytes).

Any other fastboot command (`flash`, `erase`, `boot`, `continue`, `stage`, `oem`) triggers `0x09015f90`, which transmits `FAILUnknown command`.

### USB Bulk DMA Engine (`0x090166c8`..`0x09016840`)

When a valid `download:<hex_size>` command is received:
1. `0x09016088`: Compares requested size against available SRAM/DRAM buffer (`bl #0x901cb60; cmp x0, w24, uxtw`).
2. `0x090166d8`: Formats ASCII response `DATA` + 8-hex size and transmits `DATA<hex_size>` over Bulk EP IN (`0x81`).
3. `0x0901676c..0x09016780`: Invokes low-level USB bulk read (`ldp x0, x9, [x8]; ldr x8, [x9, #0x28]; blr x8`) to transfer the entire payload into the buffer via a DMA Transfer Request Block (TRB).
4. `0x09016840`: Upon transfer completion (`b.eq #0x9016840`), records state `2` (`HAS_DATA`), restores stack frames, and executes `ret` (`0x09015c54`) directly returning to the parent image loader loop at `0x090153b8`.

### Caller Progression Loop (`0x090153b8`..`0x09015980`)

1. Immediately upon return from `0x09015ad4`, the caller verifies the downloaded image.
2. The buffer address is passed across the hardware Google Security Anchor (GSA) mailbox (`gsa-mba`) for cryptographic verification against Google's root of trust.
3. Upon authentication success (`Authenticated ` at `0x09031e88`):
   - Flushes and invalidates CPU data caches (`dc cvac` / `dc ivac` at `0x090046c0`).
   - Tears down the USB controller (`USB platform teardown attempt concluded`).
   - Branches execution to `gsa_bl1` in RAM.

---

## 3. Discovered USB Pitfalls

1. **Standard `fastboot stage <file>` Fails**: Standard Android SDK `fastboot` clients fail with `usb_read failed: Protocol error` because the client's framing assumptions conflict with DBL's minimal UDC driver.
2. **Chunked Writes Stall Endpoint**: Slicing the 32 KB payload into multiple 512-byte URBs stalls the DWC3 endpoint because the controller prepares a single DMA TRB for the full buffer size. The payload must be streamed in a **single contiguous transfer** (`ep_out.write(data, timeout=5000)`).
3. **State Machine Lockup**: If a `download:` handshake occurs and the host drops the connection without transferring the full byte count, DBL remains locked in the DATA receive state and rejects subsequent commands with `FAILUndetermined outcome`.

---

## 4. Repository Structure

- `docs/dbl_disassembly.txt`: Complete annotated AArch64 Capstone disassembly of `0x09015ad4`..`0x090169b8` and parent callers.
- `scripts/stage_gsa_bl1.py`: PyUSB staging script implementing single-contiguous-burst delivery of `gsa_bl1.img`.
- `tools/dump_dbl_state_machine.py`: Python disassembler with automatic resolution of Rust `&str` descriptors and relative branch targets.

---

## 5. Research Goal

We are looking to connect with researchers working on Tensor recovery tooling (including [`hack-different/pixel-restore`](https://github.com/hack-different/pixel-restore) and [`JoshuaDoes/tensor-usbdl`](https://github.com/JoshuaDoes/tensor-usbdl)) to establish:
1. Whether standard factory OTA `gsa_bl1.img` / `bl2.img` / `abl.img` binaries can successfully pass GSA authentication in Stage 2 DBL, or if GSA requires signed bootloader recovery packs with specific flags.
2. The exact mailbox handshakes and stage transition expectations between DBL and subsequent stages on Tensor G5 (`lga`).
