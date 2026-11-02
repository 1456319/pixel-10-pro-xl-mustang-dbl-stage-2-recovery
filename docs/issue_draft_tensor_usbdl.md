### Tensor G5 (Pixel 10 family) DBL Fastboot Specification & Signed Recovery BL1 Inquiry

Hi Joshua,

We have reverse-engineered the Stage 2 DBL (`dbl.img`) USB fastboot state machine on Tensor G5 (`lga` / `laguna`, Pixel 10 Pro XL `mustang`), providing the exact specification for how G5 handles tethered boot staging when slot retry counts are exhausted (`18d1:4ee0`).

We published the full annotated disassembly, reverse-engineering findings, and staging tooling here:
👉 **https://github.com/1456319/pixel-10-pro-xl-mustang-dbl-stage-2-recovery**

### Summary of Tensor G5 DBL Protocol:
- **Dispatcher Entry**: `0x09015ad4` (Rust binary at base VA `0x09000000`).
- **Commands**: Implements solely `getvar:` and `download:`. All others return `FAILUnknown command`.
- **Transfer**: Responds with `DATA<hex_size>`, invokes single DMA TRB read (`0x09016780`), sets state `HAS_DATA` (`0x09016840`), and returns to parent loop.
- **Verification**: Hands the loaded image over to GSA hardware mailbox via `0x1a7d0001` / `0x1a7d0005` (`bl #0x901aae8`). On authentication (`0x09031e88`), flushes caches, tears down USB, and boots `gsa_bl1`.

### Question regarding Recovery Packs:
In earlier Tensor generations (GS101 through Zuma), `tensor-usbdl` utilized signed recovery packs (`signed-recovery.zip`) containing BL1s with the USB bootable bit.

For Tensor G5 devices trapped in Stage 2 DBL (`boot-stage: dbl`, `next-boot-stage: gsa_bl1`):
1. Does GSA allow standard OTA-signed boot stages (`gsa_bl1.img` -> `bl2.img` -> `abl.img`) when staged via DBL, or does it require recovery-pack signed stages?
2. If recovery-signed stages are needed, is there any known source or progression for G5 recovery packs?

Would appreciate your insights or getting connected with the researchers tracking Tensor recovery images!

*(Note: Please reply directly to this GitHub issue as I am currently locked out of external accounts/DMs due to 2FA on the down phone. If a physical device would help research, I am also willing to ship/loan the hardware to verified maintainers).*
