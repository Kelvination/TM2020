"""
Query the TM2020 binary via PyGhidra (headless, no GUI needed).

Usage:
  python3 bridge_query.py <command> [args...]

Commands:
  search_funcs <pattern>       - Search functions by name
  search_strings <pattern>     - Search strings in binary
  namespaces [pattern]         - List namespaces/classes
  class_funcs <class_name>     - List functions in a class
  decompile <name_or_addr>     - Decompile a function
  xrefs_to <addr>              - Cross-references to an address
  calls_from <func_name>       - Functions called by a function
  calling <func_name>          - Functions that call a function
  func_info <name_or_addr>     - Get function signature and basic info
  data_at <addr> [count]       - Read data at address
  float_scan <section>         - Scan a section for notable float constants
  list_programs                - List all programs in the project
  section_info                 - List PE sections with sizes
  imports [pattern]            - List imported functions
  exports [pattern]            - List exported functions
  entry_point                  - Show entry point info
  func_count                   - Count total functions
  string_count                 - Count total defined strings
  large_funcs [min_bytes]      - List largest functions
  vtable_scan [pattern]        - Scan for vtable-like structures
"""

import os
import sys

GHIDRA_INSTALL = "/Users/kelvinnewton/Projects/ghidra/ghidra_12.0.4_PUBLIC"
PROJECT_DIR = "/Users/kelvinnewton/Projects/tm/TM2020/TM2020"
PROJECT_NAME = "TM2020"
PROGRAM_PATH = "/Trackmania.exe"

os.environ["GHIDRA_INSTALL_DIR"] = GHIDRA_INSTALL

import pyghidra

_launcher = None
_project = None
_program = None
_consumer = None


def init():
    global _launcher, _project, _program, _consumer
    if not pyghidra.started():
        print("# Starting PyGhidra...", file=sys.stderr)
        _launcher = pyghidra.start(install_dir=GHIDRA_INSTALL)
    _project = pyghidra.open_project(PROJECT_DIR, PROJECT_NAME)
    _program, _consumer = pyghidra.consume_program(_project, PROGRAM_PATH)
    print(f"# Program: {_program.getName()}", file=sys.stderr)
    print(f"# Language: {_program.getLanguage().getLanguageID()}", file=sys.stderr)
    print(f"# Base: {_program.getImageBase()}", file=sys.stderr)
    return _program


def cleanup():
    global _program, _consumer, _project
    if _program and _consumer:
        _program.release(_consumer)
    if _project:
        _project.close()


def cmd_list_programs():
    def print_file(df):
        print(f"{df.getPathname()}\t{df.getContentType()}")
    pyghidra.walk_project(_project, print_file)


def cmd_search_funcs(pattern):
    fm = _program.getFunctionManager()
    pattern_lower = pattern.lower()
    count = 0
    for func in fm.getFunctions(True):
        name = func.getName()
        if pattern_lower in name.lower():
            ns = func.getParentNamespace()
            ns_name = ns.getName(True) if ns and not ns.isGlobal() else ""
            full = f"{ns_name}::{name}" if ns_name else name
            print(f"{func.getEntryPoint()}\t{full}")
            count += 1
    print(f"\n# {count} matches")


def _iter_strings():
    listing = _program.getListing()
    mem = _program.getMemory()
    for block in mem.getBlocks():
        if not block.isInitialized():
            continue
        data_iter = listing.getDefinedData(block.getStart(), True)
        for data in data_iter:
            if data.getAddress().compareTo(block.getEnd()) > 0:
                break
            dt = data.getBaseDataType()
            if dt is not None and "string" in dt.getName().lower():
                yield data


def cmd_search_strings(pattern):
    pattern_lower = pattern.lower()
    count = 0
    for data in _iter_strings():
        val = data.getDefaultValueRepresentation()
        if pattern_lower in val.lower():
            print(f"{data.getAddress()}\t{val}")
            count += 1
    print(f"\n# {count} matches")


def cmd_namespaces(pattern=None):
    st = _program.getSymbolTable()
    namespaces = set()
    for sym in st.getAllSymbols(True):
        ns = sym.getParentNamespace()
        if ns and not ns.isGlobal():
            namespaces.add(ns.getName(True))
    namespaces = sorted(namespaces)
    if pattern:
        pattern_lower = pattern.lower()
        namespaces = [n for n in namespaces if pattern_lower in n.lower()]
    for ns in namespaces:
        print(ns)
    print(f"\n# {len(namespaces)} namespaces")


def cmd_class_funcs(class_name):
    fm = _program.getFunctionManager()
    count = 0
    for func in fm.getFunctions(True):
        ns = func.getParentNamespace()
        if ns and class_name.lower() in ns.getName(True).lower():
            print(f"{func.getEntryPoint()}\t{ns.getName(True)}::{func.getName()}")
            count += 1
    print(f"\n# {count} functions")


def cmd_decompile(name_or_addr):
    from ghidra.app.decompiler import DecompInterface

    fm = _program.getFunctionManager()
    func = None
    try:
        addr = _program.getAddressFactory().getAddress(name_or_addr)
        func = fm.getFunctionAt(addr)
    except Exception:
        pass
    if func is None:
        for f in fm.getFunctions(True):
            if f.getName() == name_or_addr:
                func = f
                break
    if func is None:
        for f in fm.getFunctions(True):
            if name_or_addr.lower() in f.getName().lower():
                func = f
                ns = f.getParentNamespace()
                ns_str = f"{ns.getName(True)}::" if ns and not ns.isGlobal() else ""
                print(f"# Matched: {ns_str}{f.getName()} at {f.getEntryPoint()}")
                break
    if func is None:
        print(f"# Function not found: {name_or_addr}")
        return

    decomp = DecompInterface()
    decomp.openProgram(_program)
    result = decomp.decompileFunction(func, 60, None)
    if result.decompileCompleted():
        print(result.getDecompiledFunction().getC())
    else:
        print(f"# Decompilation failed: {result.getErrorMessage()}")
    decomp.dispose()


def cmd_xrefs_to(addr_str):
    addr = _program.getAddressFactory().getAddress(addr_str)
    ref_mgr = _program.getReferenceManager()
    refs = ref_mgr.getReferencesTo(addr)
    fm = _program.getFunctionManager()
    count = 0
    for ref in refs:
        from_addr = ref.getFromAddress()
        func = fm.getFunctionContaining(from_addr)
        func_name = func.getName() if func else "<none>"
        print(f"{from_addr}\t{func_name}\t{ref.getReferenceType()}")
        count += 1
    print(f"\n# {count} references")


def cmd_calls_from(func_name):
    fm = _program.getFunctionManager()
    func = None
    for f in fm.getFunctions(True):
        if f.getName() == func_name:
            func = f
            break
    if func is None:
        for f in fm.getFunctions(True):
            if func_name.lower() in f.getName().lower():
                func = f
                print(f"# Matched: {f.getName()}")
                break
    if func is None:
        print(f"# Function not found: {func_name}")
        return
    called = func.getCalledFunctions(None)
    count = 0
    for callee in called:
        ns = callee.getParentNamespace()
        ns_str = f"{ns.getName(True)}::" if ns and not ns.isGlobal() else ""
        print(f"{callee.getEntryPoint()}\t{ns_str}{callee.getName()}")
        count += 1
    print(f"\n# {count} calls from {func.getName()}")


def cmd_calling(func_name):
    fm = _program.getFunctionManager()
    func = None
    for f in fm.getFunctions(True):
        if f.getName() == func_name:
            func = f
            break
    if func is None:
        for f in fm.getFunctions(True):
            if func_name.lower() in f.getName().lower():
                func = f
                print(f"# Matched: {f.getName()}")
                break
    if func is None:
        print(f"# Function not found: {func_name}")
        return
    callers = func.getCallingFunctions(None)
    count = 0
    for caller in callers:
        ns = caller.getParentNamespace()
        ns_str = f"{ns.getName(True)}::" if ns and not ns.isGlobal() else ""
        print(f"{caller.getEntryPoint()}\t{ns_str}{caller.getName()}")
        count += 1
    print(f"\n# {count} callers of {func.getName()}")


def cmd_func_info(name_or_addr):
    fm = _program.getFunctionManager()
    func = None
    try:
        addr = _program.getAddressFactory().getAddress(name_or_addr)
        func = fm.getFunctionAt(addr)
    except Exception:
        pass
    if func is None:
        for f in fm.getFunctions(True):
            if f.getName() == name_or_addr:
                func = f
                break
    if func is None:
        for f in fm.getFunctions(True):
            if name_or_addr.lower() in f.getName().lower():
                func = f
                break
    if func is None:
        print(f"# Function not found: {name_or_addr}")
        return
    ns = func.getParentNamespace()
    ns_str = ns.getName(True) if ns and not ns.isGlobal() else ""
    print(f"Name: {func.getName()}")
    print(f"Address: {func.getEntryPoint()}")
    print(f"Signature: {func.getSignature()}")
    if ns_str:
        print(f"Namespace: {ns_str}")
    print(f"Body size: {func.getBody().getNumAddresses()} bytes")
    print(f"Stack frame: {func.getStackFrame().getFrameSize()} bytes")
    params = func.getParameters()
    if params:
        print(f"Parameters ({len(params)}):")
        for p in params:
            print(f"  {p.getDataType()} {p.getName()}")
    called = list(func.getCalledFunctions(None))
    print(f"Calls: {len(called)} functions")
    calling = list(func.getCallingFunctions(None))
    print(f"Called by: {len(calling)} functions")


def cmd_data_at(addr_str, count="64"):
    addr = _program.getAddressFactory().getAddress(addr_str)
    mem = _program.getMemory()
    count = int(count)
    import jpype
    jbuf = jpype.JArray(jpype.JByte)(count)
    mem.getBytes(addr, jbuf)
    buf = bytes([b & 0xFF for b in jbuf])
    for i in range(0, len(buf), 16):
        hex_part = " ".join(f"{b:02x}" for b in buf[i:i+16])
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in buf[i:i+16])
        offset_addr = addr.add(i)
        print(f"{offset_addr}  {hex_part:<48}  {ascii_part}")


def cmd_float_scan(section=".rdata"):
    mem = _program.getMemory()
    notable = {
        9.81: "gravity (m/s^2)",
        9.8: "gravity approx",
        -9.81: "gravity negative",
        -9.8: "gravity negative approx",
        3.14159: "pi",
        6.28318: "2*pi",
        1.5708: "pi/2",
        0.0174533: "deg2rad",
        57.2958: "rad2deg",
    }
    blocks = mem.getBlocks()
    count = 0
    for block in blocks:
        if not block.isInitialized():
            continue
        if section != "*" and block.getName() != section:
            continue
        start = block.getStart()
        end = block.getEnd()
        size = block.getSize()
        print(f"# Scanning {block.getName()} ({size} bytes)...")
        addr = start
        while addr is not None and addr.compareTo(end) < 0:
            try:
                val = mem.getFloat(addr)
                for target, desc in notable.items():
                    if abs(val - target) < 0.01:
                        print(f"{addr}\t{val:.6f}\t{desc}")
                        count += 1
            except Exception:
                pass
            try:
                addr = addr.add(4)
            except Exception:
                break
    print(f"\n# {count} notable floats found")


def cmd_section_info():
    mem = _program.getMemory()
    for block in mem.getBlocks():
        start = block.getStart()
        end = block.getEnd()
        size = block.getSize()
        perms = ""
        if block.isRead(): perms += "R"
        if block.isWrite(): perms += "W"
        if block.isExecute(): perms += "X"
        init = "init" if block.isInitialized() else "uninit"
        print(f"{block.getName()}\t{start}-{end}\t{size}\t{perms}\t{init}")


def cmd_imports(pattern=None):
    st = _program.getSymbolTable()
    ext_mgr = _program.getExternalManager()
    count = 0
    for sym in st.getExternalSymbols():
        name = sym.getName()
        source = sym.getSource()
        ns = sym.getParentNamespace()
        ns_name = ns.getName() if ns else ""
        full = f"{ns_name}::{name}" if ns_name else name
        if pattern and pattern.lower() not in full.lower():
            continue
        print(f"{sym.getAddress()}\t{full}\t{source}")
        count += 1
    print(f"\n# {count} imports")


def cmd_exports(pattern=None):
    st = _program.getSymbolTable()
    count = 0
    for sym in st.getAllSymbols(True):
        if sym.isExternalEntryPoint():
            name = sym.getName()
            if pattern and pattern.lower() not in name.lower():
                continue
            print(f"{sym.getAddress()}\t{name}")
            count += 1
    print(f"\n# {count} exports")


def cmd_entry_point():
    fm = _program.getFunctionManager()
    entry = _program.getSymbolTable().getExternalEntryPointIterator()
    count = 0
    for addr in entry:
        func = fm.getFunctionAt(addr)
        if func:
            print(f"{addr}\t{func.getName()}\t(function)")
        else:
            print(f"{addr}\t<no function>")
        count += 1
        if count > 20:
            print("# ... (truncated)")
            break
    print(f"\n# {count} entry points shown")


def cmd_func_count():
    fm = _program.getFunctionManager()
    count = fm.getFunctionCount()
    print(f"Total functions: {count}")


def cmd_string_count():
    count = sum(1 for _ in _iter_strings())
    print(f"Total defined strings: {count}")


def cmd_large_funcs(min_bytes="1000"):
    min_bytes = int(min_bytes)
    fm = _program.getFunctionManager()
    funcs = []
    for func in fm.getFunctions(True):
        size = func.getBody().getNumAddresses()
        if size >= min_bytes:
            ns = func.getParentNamespace()
            ns_name = ns.getName(True) if ns and not ns.isGlobal() else ""
            full = f"{ns_name}::{func.getName()}" if ns_name else func.getName()
            funcs.append((size, func.getEntryPoint(), full))
    funcs.sort(reverse=True)
    for size, addr, name in funcs[:100]:
        print(f"{addr}\t{size}\t{name}")
    print(f"\n# {len(funcs)} functions >= {min_bytes} bytes (showing top 100)")


def cmd_vtable_scan(pattern=None):
    st = _program.getSymbolTable()
    count = 0
    for sym in st.getAllSymbols(True):
        name = sym.getName()
        if "vtable" in name.lower() or "vftable" in name.lower() or name.startswith("__vt"):
            if pattern and pattern.lower() not in name.lower():
                continue
            ns = sym.getParentNamespace()
            ns_name = ns.getName(True) if ns and not ns.isGlobal() else ""
            full = f"{ns_name}::{name}" if ns_name else name
            print(f"{sym.getAddress()}\t{full}")
            count += 1
    print(f"\n# {count} vtable symbols")


COMMANDS = {
    "search_funcs": (cmd_search_funcs, 1, 1),
    "search_strings": (cmd_search_strings, 1, 1),
    "namespaces": (cmd_namespaces, 0, 1),
    "class_funcs": (cmd_class_funcs, 1, 1),
    "decompile": (cmd_decompile, 1, 1),
    "xrefs_to": (cmd_xrefs_to, 1, 1),
    "calls_from": (cmd_calls_from, 1, 1),
    "calling": (cmd_calling, 1, 1),
    "func_info": (cmd_func_info, 1, 1),
    "data_at": (cmd_data_at, 1, 2),
    "float_scan": (cmd_float_scan, 0, 1),
    "list_programs": (cmd_list_programs, 0, 0),
    "section_info": (cmd_section_info, 0, 0),
    "imports": (cmd_imports, 0, 1),
    "exports": (cmd_exports, 0, 1),
    "entry_point": (cmd_entry_point, 0, 0),
    "func_count": (cmd_func_count, 0, 0),
    "string_count": (cmd_string_count, 0, 0),
    "large_funcs": (cmd_large_funcs, 0, 1),
    "vtable_scan": (cmd_vtable_scan, 0, 1),
}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd_name = sys.argv[1]
    args = sys.argv[2:]

    if cmd_name not in COMMANDS:
        print(f"Unknown command: {cmd_name}")
        print(f"Available: {', '.join(sorted(COMMANDS.keys()))}")
        sys.exit(1)

    func, min_args, max_args = COMMANDS[cmd_name]
    if len(args) < min_args or len(args) > max_args:
        print(f"Usage: {cmd_name} requires {min_args}-{max_args} arguments, got {len(args)}")
        sys.exit(1)

    try:
        program = init()
        func(*args)
    except Exception as e:
        print(f"# ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
    finally:
        cleanup()
