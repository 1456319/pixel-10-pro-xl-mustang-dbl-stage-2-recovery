### Tensor G5 (Pixel 10 / mustang) Stage 2 DBL Fastboot Protocol Specification & GSA Recovery Inquiry

Hi team,

Following up on the Pixel 10 family note in `README.md` (`| Pixel 10 family | frankel, blazer, mustang, rango | laguna (G5) | no USB-bootable BL1 published; ROM protocol unknown |`):

We have reverse-engineered the Stage 2 DBL (`dbl.img`) USB recovery state machine on Tensor G5 (`lga` / `laguna`, tested on Pixel 10 Pro XL `mustang`). When A/B slot retry counters exhaust in `devinfo`, the device halts normal UFS boot and drops into Stage 2 tethered Fastboot (`18d1:4ee0`, black screen).

We have fully mapped the state machine and published the complete annotated disassembly, analysis, and Python staging tools here:
👉 **https://github.com/1456319/pixel-10-pro-xl-mustang-dbl-stage-2-recovery**

### Key Findings on Tensor G5 DBL (`dbl.img`):

1. **Protocol Implementation**:
   - Dispatcher entry point: `0x09015ad4` (called from image loading loop at `0x090153b8`).
   - Implements **only** `getvar:` (`0x09015e84`) and `download:` (`0x09015ef4`). Any other command (`boot`, `continue`, `flash`, `stage`) returns `FAILUnknown command`.
   - Variable table exposes: `version` (0.4), `boot-stage` (`dbl`), `next-boot-stage` (`gsa_bl1`), `is-last-boot-stage` (`no`), `product` (`lga`), `version-dbl` (`14451019`), `test`, `imei1`, `imei2`.

2. **DMA Bulk Transfer Engine (`0x090166c8`..`0x09016840`)**:
   - `download:<hex_size>` validates buffer bounds (`bl #0x901cb60; cmp x0, w24, uxtw`).
   - Responds with `DATA<hex_size>`.
   - Reads the full payload via a single DMA Transfer Request Block (TRB) (`blr x8` at `0x09016780`).
   - Sets state = 2 (`HAS_DATA`) at `0x09016840` and returns immediately via `ret` (`0x09015c54`) back to the parent stage launcher.

3. **GSA Hardware Mailbox Verification (`gsa-mba`)**:
   - The stage buffer is dispatched to the GSA mailbox via opcodes `0x1a7d0001` through `0x1a7d0005` (`bl #0x901aae8`).
   - On verification success (`Authenticated ` at `0x09031e88`), DBL flushes data cache (`dc cvac`/`dc ivac` at `0x090046c0`), concludes USB teardown, and branches execution to `gsa_bl1`.

### Where We Need Guidance:

We are currently attempting to rescue a Pixel 10 Pro XL (`mustang`) that entered this mode without wiping `/userdata`.

When staging `gsa_bl1.img` from the official factory OTA (`mustang-ota-bp4a.260205.001`), we want to verify:
1. Does Stage 2 DBL accept retail OTA Google-signed boot stages (`gsa_bl1.img`), or does the GSA mailbox enforce a "USB bootable" flag similar to Stage 1 BootROM?
2. Are researchers who source the signed recovery bootloaders (`signed-recovery.zip`) aware of any specific requirements for G5 DBL tethered staging?

All disassembly, Ghidra/Capstone maps, and PyUSB scripts are available in the repository linked above. We would love to collaborate on adding full Tensor G5 Stage 2 support to `pixel-restore`.
