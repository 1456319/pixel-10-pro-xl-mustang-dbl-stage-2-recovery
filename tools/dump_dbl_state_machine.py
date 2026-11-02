import struct
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM

with open("/home/deck/Downloads/extracted_ota/dbl.img", "rb") as f:
    data = f.read()

BASE_VA = 0x09000000
HDR_SIZE = 0x1000
md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
md.detail = True

def resolve_va(va):
    foff = (va - BASE_VA) + HDR_SIZE
    if not (0 <= foff < len(data)):
        return None
    if foff + 16 <= len(data):
        ptr, length = struct.unpack_from("<QQ", data, foff)
        s_off = (ptr - BASE_VA) + HDR_SIZE
        if BASE_VA <= ptr < BASE_VA + len(data) and 1 <= length <= 160 and 0 <= s_off <= len(data) - length:
            s = data[s_off:s_off+length]
            if all(0x20 <= b <= 0x7e or b in (0x09, 0x0a, 0x0d) for b in s):
                return f"Desc -> {repr(s.decode('ascii'))}"
    end = foff
    while end < min(len(data), foff + 80) and (0x20 <= data[end] <= 0x7e or data[end] in (0x09, 0x0a, 0x0d)):
        end += 1
    if end - foff >= 2:
        return f"Str -> {repr(data[foff:end].decode('ascii'))}"
    return None

def dump_range(title, start_va, end_va):
    print(f"=== {title} (0x{start_va:08x}..0x{end_va:08x}) ===")
    start_off = (start_va - BASE_VA) + HDR_SIZE
    end_off   = (end_va - BASE_VA) + HDR_SIZE
    last_adrp = {}
    for insn in md.disasm(data[start_off:end_off], start_va):
        note = ""
        if insn.mnemonic == "adr":
            res = resolve_va(insn.operands[1].imm)
            if res: note = f"  ; {res}"
        elif insn.mnemonic == "adrp":
            last_adrp[insn.reg_name(insn.operands[0].reg)] = insn.operands[1].imm
        elif insn.mnemonic == "add" and len(insn.operands) >= 3:
            r_src = insn.reg_name(insn.operands[1].reg)
            if r_src in last_adrp and insn.operands[2].type == 2:
                target = last_adrp[r_src] + insn.operands[2].imm
                res = resolve_va(target)
                if res: note = f"  ; [0x{target:08x}] {res}"
        print(f"0x{insn.address:08x}: {insn.mnemonic:8s} {insn.op_str}{note}")

dump_range("1. DOWNLOAD HANDLER & EXIT PATH", 0x09016500, 0x090169b8)

# Find all callers of 0x09015ad4 (the fastboot stage handler)
print("\n=== 2. ENTRY PROLOGUE & CALLERS OF FASTBOOT STATE MACHINE ===")
dump_range("FASTBOOT PROLOGUE", 0x09015ad0, 0x09015c60)

code = data[HDR_SIZE:]
for i in range(0, len(code) - 4, 4):
    word = struct.unpack_from("<I", code, i)[0]
    if (word & 0xfc000000) == 0x94000000: # BL instruction
        imm26 = word & 0x03ffffff
        if imm26 & 0x02000000:
            imm26 -= 0x04000000
        va = BASE_VA + i
        target = va + (imm26 << 2)
        if 0x09015ad0 <= target <= 0x09015c60:
            print(f"\nFound BL to 0x{target:08x} at 0x{va:08x}:")
            dump_range(f"CALLER AROUND 0x{va:08x}", max(BASE_VA, va - 0x80), min(BASE_VA + len(code), va + 0xa0))
