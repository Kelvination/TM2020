"""
Quick PE analysis of Trackmania.exe without Ghidra.
Extracts headers, sections, imports, exports, and string samples.
"""

import struct
import sys
import os

BINARY = "/Users/kelvinnewton/Projects/tm/TM2020/Trackmania.exe"


def read_pe(path):
    with open(path, "rb") as f:
        data = f.read()
    return data


def parse_dos_header(data):
    magic = data[0:2]
    assert magic == b'MZ', f"Not a PE file: {magic}"
    e_lfanew = struct.unpack_from('<I', data, 0x3C)[0]
    return e_lfanew


def parse_pe_header(data, offset):
    sig = data[offset:offset+4]
    assert sig == b'PE\x00\x00', f"Bad PE sig: {sig}"

    # COFF header
    machine = struct.unpack_from('<H', data, offset+4)[0]
    num_sections = struct.unpack_from('<H', data, offset+6)[0]
    timestamp = struct.unpack_from('<I', data, offset+8)[0]
    characteristics = struct.unpack_from('<H', data, offset+22)[0]

    # Optional header
    opt_offset = offset + 24
    opt_magic = struct.unpack_from('<H', data, opt_offset)[0]

    machines = {0x8664: "x86-64", 0x14c: "x86", 0xAA64: "ARM64"}

    info = {
        "machine": machines.get(machine, f"0x{machine:04x}"),
        "num_sections": num_sections,
        "timestamp": timestamp,
        "characteristics": f"0x{characteristics:04x}",
        "pe_type": "PE32+" if opt_magic == 0x20b else "PE32",
    }

    if opt_magic == 0x20b:  # PE32+
        info["image_base"] = struct.unpack_from('<Q', data, opt_offset + 24)[0]
        info["section_alignment"] = struct.unpack_from('<I', data, opt_offset + 32)[0]
        info["file_alignment"] = struct.unpack_from('<I', data, opt_offset + 36)[0]
        info["size_of_image"] = struct.unpack_from('<I', data, opt_offset + 56)[0]
        info["size_of_headers"] = struct.unpack_from('<I', data, opt_offset + 60)[0]
        info["subsystem"] = struct.unpack_from('<H', data, opt_offset + 68)[0]
        info["num_data_dirs"] = struct.unpack_from('<I', data, opt_offset + 108)[0]
        info["opt_header_size"] = 112 + info["num_data_dirs"] * 8

        # Data directories
        dd_offset = opt_offset + 112
        dd_names = ["Export", "Import", "Resource", "Exception", "Security",
                    "BaseReloc", "Debug", "Architecture", "GlobalPtr", "TLS",
                    "LoadConfig", "BoundImport", "IAT", "DelayImport",
                    "CLRHeader", "Reserved"]
        info["data_dirs"] = []
        for i in range(min(info["num_data_dirs"], 16)):
            rva = struct.unpack_from('<I', data, dd_offset + i*8)[0]
            size = struct.unpack_from('<I', data, dd_offset + i*8 + 4)[0]
            if rva or size:
                name = dd_names[i] if i < len(dd_names) else f"Dir{i}"
                info["data_dirs"].append((name, rva, size))

    return info, opt_offset


def parse_sections(data, pe_offset, num_sections, opt_header_size):
    sections = []
    sec_offset = pe_offset + 24 + opt_header_size
    for i in range(num_sections):
        off = sec_offset + i * 40
        name = data[off:off+8].rstrip(b'\x00').decode('ascii', errors='replace')
        vsize = struct.unpack_from('<I', data, off+8)[0]
        vaddr = struct.unpack_from('<I', data, off+12)[0]
        raw_size = struct.unpack_from('<I', data, off+16)[0]
        raw_ptr = struct.unpack_from('<I', data, off+20)[0]
        chars = struct.unpack_from('<I', data, off+36)[0]

        perms = ""
        if chars & 0x20000000: perms += "R"
        if chars & 0x40000000: perms += "W"  # Note: this is wrong, let me fix
        if chars & 0x80000000: perms += "W"
        if chars & 0x20000000: perms = "R"
        if chars & 0x40000000: perms += "X"
        if chars & 0x80000000: perms += "W"

        # Redo properly
        perms = ""
        if chars & 0x40000000: perms += "R"
        if chars & 0x80000000: perms += "W"
        if chars & 0x20000000: perms += "X"

        contains_code = bool(chars & 0x20)
        contains_init = bool(chars & 0x40)
        contains_uninit = bool(chars & 0x80)

        sections.append({
            "name": name,
            "virtual_size": vsize,
            "virtual_addr": vaddr,
            "raw_size": raw_size,
            "raw_ptr": raw_ptr,
            "characteristics": f"0x{chars:08x}",
            "perms": perms,
            "code": contains_code,
            "init_data": contains_init,
            "uninit_data": contains_uninit,
        })
    return sections


def rva_to_offset(sections, rva):
    for sec in sections:
        if sec["virtual_addr"] <= rva < sec["virtual_addr"] + sec["virtual_size"]:
            return sec["raw_ptr"] + (rva - sec["virtual_addr"])
    return None


def parse_imports(data, sections, import_rva, import_size):
    if not import_rva:
        return []

    offset = rva_to_offset(sections, import_rva)
    if offset is None:
        return []

    imports = []
    i = 0
    while True:
        ilt_rva = struct.unpack_from('<I', data, offset + i*20)[0]
        name_rva = struct.unpack_from('<I', data, offset + i*20 + 12)[0]
        if not ilt_rva and not name_rva:
            break

        name_off = rva_to_offset(sections, name_rva)
        if name_off:
            dll_name = b""
            for j in range(256):
                b = data[name_off + j:name_off + j + 1]
                if b == b'\x00' or not b:
                    break
                dll_name += b
            imports.append(dll_name.decode('ascii', errors='replace'))
        i += 1
    return imports


def extract_strings(data, min_len=6):
    """Extract printable ASCII strings."""
    strings = []
    current = b""
    offset = 0
    for i, b in enumerate(data):
        if 32 <= b < 127:
            if not current:
                offset = i
            current += bytes([b])
        else:
            if len(current) >= min_len:
                strings.append((offset, current.decode('ascii')))
            current = b""
    return strings


def main():
    data = read_pe(BINARY)
    print(f"File size: {len(data):,} bytes ({len(data)/1024/1024:.1f} MB)")

    e_lfanew = parse_dos_header(data)
    pe_info, opt_offset = parse_pe_header(data, e_lfanew)

    print(f"\n=== PE Header ===")
    print(f"Type: {pe_info['pe_type']}")
    print(f"Machine: {pe_info['machine']}")
    print(f"Image base: 0x{pe_info.get('image_base', 0):X}")
    print(f"Size of image: {pe_info.get('size_of_image', 0):,} bytes")
    print(f"Sections: {pe_info['num_sections']}")
    subsys = {2: "GUI", 3: "Console"}.get(pe_info.get('subsystem', 0), str(pe_info.get('subsystem', '?')))
    print(f"Subsystem: {subsys}")

    print(f"\n=== Data Directories ===")
    for name, rva, size in pe_info.get('data_dirs', []):
        print(f"  {name}: RVA=0x{rva:08X}, Size={size:,}")

    sections = parse_sections(data, e_lfanew, pe_info['num_sections'], pe_info.get('opt_header_size', 240))

    print(f"\n=== Sections ===")
    print(f"{'Name':<12} {'VAddr':>10} {'VSize':>12} {'RawSize':>12} {'Perms':<6} {'Flags'}")
    for sec in sections:
        flags = []
        if sec['code']: flags.append("CODE")
        if sec['init_data']: flags.append("IDATA")
        if sec['uninit_data']: flags.append("UDATA")
        print(f"{sec['name']:<12} 0x{sec['virtual_addr']:08X} {sec['virtual_size']:>12,} {sec['raw_size']:>12,} {sec['perms']:<6} {', '.join(flags)}")

    # Imports
    import_dir = None
    for name, rva, size in pe_info.get('data_dirs', []):
        if name == "Import":
            import_dir = (rva, size)

    if import_dir:
        dlls = parse_imports(data, sections, import_dir[0], import_dir[1])
        print(f"\n=== Imported DLLs ({len(dlls)}) ===")
        for dll in sorted(dlls):
            print(f"  {dll}")

    # String analysis - sample interesting strings
    print(f"\n=== String Analysis ===")
    all_strings = extract_strings(data, min_len=8)
    print(f"Total strings (>= 8 chars): {len(all_strings):,}")

    # Categorize interesting strings
    categories = {
        "Class names (C prefix)": [],
        "DirectX/Graphics": [],
        "Network/HTTP": [],
        "File formats": [],
        "Physics/Vehicle": [],
        "Debug/Error": [],
        "GBX/ManiaPlanet": [],
    }

    for offset, s in all_strings:
        sl = s.lower()
        if s.startswith("CGame") or s.startswith("CPlug") or s.startswith("CMw") or s.startswith("CFast") or s.startswith("CHms") or s.startswith("CScene"):
            categories["Class names (C prefix)"].append(s)
        elif any(k in sl for k in ["d3d", "dx1", "vulkan", "shader", "render", "texture", "vertex", "pixel", "directx"]):
            categories["DirectX/Graphics"].append(s)
        elif any(k in sl for k in ["http", "socket", "tcp", "udp", "network", "nadeo", "ubisoft", "maniaplanet"]):
            categories["Network/HTTP"].append(s)
        elif any(k in sl for k in [".gbx", ".dds", ".pak", ".zip", ".json", ".xml", ".mux"]):
            categories["File formats"].append(s)
        elif any(k in sl for k in ["physics", "vehicle", "wheel", "engine", "speed", "accel", "gravity", "friction", "collision", "surface"]):
            categories["Physics/Vehicle"].append(s)
        elif any(k in sl for k in ["error", "assert", "fail", "debug", "warn", "exception"]):
            categories["Debug/Error"].append(s)
        elif any(k in sl for k in ["gbx", "mania", "nadeo", "trackmania", "chunk"]):
            categories["GBX/ManiaPlanet"].append(s)

    for cat, strings in categories.items():
        unique = sorted(set(strings))
        print(f"\n  {cat}: {len(unique)} unique strings")
        for s in unique[:30]:
            print(f"    {s}")
        if len(unique) > 30:
            print(f"    ... and {len(unique) - 30} more")


if __name__ == "__main__":
    main()
