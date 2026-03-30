"""
Extract class names, RTTI info, and method names from Trackmania.exe strings.
ManiaPlanet/Nadeo uses consistent naming conventions we can exploit:
  - Classes: CGameXxx, CPlugXxx, CMwXxx, CHmsXxx, etc.
  - Methods: ClassName::MethodName patterns in error/debug strings
  - MSVC RTTI: .?AV prefix for class type info
"""

import re
import struct
import json
import sys

BINARY = "/Users/kelvinnewton/Projects/tm/TM2020/Trackmania.exe"


def extract_strings(data, min_len=4):
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


def extract_rtti_classes(strings):
    """Extract MSVC RTTI class names (.?AV pattern)."""
    rtti_classes = set()
    for offset, s in strings:
        # MSVC RTTI type_info name format: .?AVClassName@@
        matches = re.findall(r'\.?\?AV(\w+?)@@', s)
        for m in matches:
            rtti_classes.add(m)
        # Also catch .?AU (struct)
        matches = re.findall(r'\.?\?AU(\w+?)@@', s)
        for m in matches:
            rtti_classes.add(m)
    return sorted(rtti_classes)


def extract_nadeo_classes(strings):
    """Extract Nadeo class names (C-prefix convention)."""
    classes = set()
    methods = {}  # class -> [methods]

    # Patterns for Nadeo class names
    class_pattern = re.compile(
        r'\b(C(?:Game|Plug|Mw|Hms|Fast|Scene|Vision|Net|System|Input|Audio|Gbx|'
        r'Script|Control|Menu|Xml|Nod|Fid|Buffer|Media|Action|Motion|'
        r'Shader|Texture|Surface|Vehicle|Block|Item|Map|Challenge|'
        r'Ghost|Replay|Record|Campaign|Title|Profile|User|Client|Server|'
        r'Http|Uplay|WebServices|Packman|Notification|Collection|'
        r'Mobil|Solid|Crystal|Material|Light|Prefab|Dyna|Anim)[A-Z]\w+)\b'
    )

    method_pattern = re.compile(
        r'\b(C\w{3,})::([\w~]+)'
    )

    for offset, s in strings:
        # Extract class::method patterns
        for m in method_pattern.finditer(s):
            cls = m.group(1)
            method = m.group(2)
            classes.add(cls)
            if cls not in methods:
                methods[cls] = set()
            methods[cls].add(method)

        # Extract standalone class names
        for m in class_pattern.finditer(s):
            classes.add(m.group(1))

    return sorted(classes), {k: sorted(v) for k, v in sorted(methods.items())}


def extract_enums_and_constants(strings):
    """Extract enum-like patterns and named constants."""
    enums = {}  # prefix -> values
    for offset, s in strings:
        # Pattern: ESomething::Value or EFoo_Bar
        m = re.match(r'^(E[A-Z]\w+)::([\w]+)$', s.strip())
        if m:
            enum = m.group(1)
            val = m.group(2)
            if enum not in enums:
                enums[enum] = []
            enums[enum].append(val)
    return {k: sorted(set(v)) for k, v in sorted(enums.items())}


def categorize_classes(classes):
    """Group classes by their prefix/subsystem."""
    categories = {}
    for cls in classes:
        # Find the subsystem prefix
        m = re.match(r'^C(Game|Plug|Mw|Hms|Fast|Scene|Vision|Net|System|Input|Audio|Gbx|'
                     r'Script|Control|Menu|Xml|Nod|Fid|Buffer|Media|Action|Motion|'
                     r'Shader|Texture|Surface|Vehicle|Block|Item|Map|Challenge|'
                     r'Ghost|Replay|Record|Campaign|Title|Profile|User|Client|Server|'
                     r'Http|Uplay|WebServices|Packman|Notification|Collection|'
                     r'Mobil|Solid|Crystal|Material|Light|Prefab|Dyna|Anim)', cls)
        if m:
            prefix = m.group(1)
        else:
            # Try general C prefix
            m2 = re.match(r'^C([A-Z][a-z]+)', cls)
            prefix = m2.group(1) if m2 else "Other"
        if prefix not in categories:
            categories[prefix] = []
        categories[prefix].append(cls)
    return {k: sorted(v) for k, v in sorted(categories.items())}


def main():
    with open(BINARY, "rb") as f:
        data = f.read()

    print("Extracting strings...", file=sys.stderr)
    all_strings = extract_strings(data, min_len=4)
    print(f"Found {len(all_strings)} strings", file=sys.stderr)

    # RTTI
    print("Extracting RTTI classes...", file=sys.stderr)
    rtti = extract_rtti_classes(all_strings)
    print(f"RTTI classes: {len(rtti)}")
    for cls in rtti[:50]:
        print(f"  {cls}")
    if len(rtti) > 50:
        print(f"  ... and {len(rtti) - 50} more")

    # Nadeo classes
    print("\nExtracting Nadeo classes and methods...", file=sys.stderr)
    nadeo_classes, methods = extract_nadeo_classes(all_strings)
    print(f"\nNadeo classes with methods: {len(methods)}")
    for cls, meths in list(methods.items())[:80]:
        print(f"\n  {cls}:")
        for meth in meths[:15]:
            print(f"    ::{meth}")
        if len(meths) > 15:
            print(f"    ... and {len(meths) - 15} more methods")

    # Categorize
    print(f"\n\n=== Class Categories ===")
    cats = categorize_classes(nadeo_classes)
    for prefix, classes in cats.items():
        print(f"\n  {prefix} ({len(classes)} classes):")
        for cls in classes[:10]:
            print(f"    {cls}")
        if len(classes) > 10:
            print(f"    ... and {len(classes) - 10} more")

    # Enums
    print("\nExtracting enums...", file=sys.stderr)
    enums = extract_enums_and_constants(all_strings)
    if enums:
        print(f"\n=== Enums ({len(enums)}) ===")
        for enum, vals in list(enums.items())[:30]:
            print(f"\n  {enum}: {', '.join(vals[:10])}")
            if len(vals) > 10:
                print(f"    ... and {len(vals) - 10} more")

    # Save full data
    output = {
        "rtti_classes": rtti,
        "nadeo_classes": nadeo_classes,
        "methods": methods,
        "categories": cats,
        "enums": enums,
    }

    with open("/Users/kelvinnewton/Projects/tm/TM2020/docs/re/class_hierarchy.json", "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nFull data saved to docs/re/class_hierarchy.json", file=sys.stderr)


if __name__ == "__main__":
    main()
