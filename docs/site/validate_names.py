#!/usr/bin/env python3
"""
Comprehensive validation script for address_names.json mapping.

Validates naming conventions, coverage, and semantic consistency
for the Trackmania 2020 reverse engineering hex-address-to-name mapping.
"""

import json
import re
import os
import sys
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path

# ─── Configuration ───────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent
MAPPING_FILE = SCRIPT_DIR / "address_names.json"
REPORT_FILE = SCRIPT_DIR / "validation_report.txt"

DOC_DIRS = [
    SCRIPT_DIR.parent / "re",
    SCRIPT_DIR.parent / "plan",
    SCRIPT_DIR.parent / "seminar",
]

# Thresholds
SIMILARITY_THRESHOLD = 0.90  # Flag names with >= 90% similarity
SHORT_NAME_MIN_LEN = 4
TOP_UNMAPPED_COUNT = 20

# Hex pattern that matches 0x followed by 2-16 hex chars (with optional 'xx' wildcard)
HEX_PATTERN = re.compile(r'0x[0-9a-fA-F]{2,16}')

# Pattern for names that look placeholder-ish
PLACEHOLDER_PATTERNS = [
    re.compile(r'\bunknown\b', re.IGNORECASE),
    re.compile(r'\bTODO\b', re.IGNORECASE),
    re.compile(r'\bgeneric\b', re.IGNORECASE),
    re.compile(r'\bplaceholder\b', re.IGNORECASE),
    re.compile(r'\btemp\b', re.IGNORECASE),
    re.compile(r'\bfixme\b', re.IGNORECASE),
    re.compile(r'\bXXX\b'),
    re.compile(r'\bunk_\b', re.IGNORECASE),
    re.compile(r'^FUN_', re.IGNORECASE),  # Ghidra auto-generated function names
    re.compile(r'^DAT_', re.IGNORECASE),  # Ghidra auto-generated data names
    re.compile(r'^undefined', re.IGNORECASE),
]

# ─── Result tracking ─────────────────────────────────────────────────────────

class ValidationResults:
    def __init__(self):
        self.critical = []
        self.warnings = []
        self.info = []
        self.stats = {}

    def add_critical(self, msg):
        self.critical.append(msg)

    def add_warning(self, msg):
        self.warnings.append(msg)

    def add_info(self, msg):
        self.info.append(msg)

    def total_issues(self):
        return len(self.critical) + len(self.warnings)


# ─── 1. Mapping Integrity ────────────────────────────────────────────────────

def validate_integrity(mapping, results):
    """Check structural integrity of the mapping."""
    results.add_info("=" * 70)
    results.add_info("SECTION 1: MAPPING INTEGRITY")
    results.add_info("=" * 70)

    # Check all keys are valid hex
    invalid_keys = []
    # Allow 'xx' wildcard suffix (e.g. 0x030430xx for chunk families)
    hex_key_pattern = re.compile(r'^0x[0-9a-fA-F]+(x{1,2})?$')
    for key in mapping:
        if not hex_key_pattern.match(key):
            invalid_keys.append(key)
    if invalid_keys:
        for k in invalid_keys:
            results.add_critical(f"Invalid hex key: '{k}' -> '{mapping[k]}'")
    else:
        results.add_info(f"All {len(mapping)} keys are valid hex format.")

    # Check all keys are lowercase
    uppercase_keys = [k for k in mapping if k != k.lower()]
    if uppercase_keys:
        for k in uppercase_keys:
            results.add_warning(f"Key not lowercase: '{k}' -> '{mapping[k]}'")
    else:
        results.add_info("All keys are lowercase.")

    # Check all values are non-empty strings
    empty_values = [(k, v) for k, v in mapping.items() if not isinstance(v, str) or not v.strip()]
    if empty_values:
        for k, v in empty_values:
            results.add_critical(f"Empty or non-string value: '{k}' -> {repr(v)}")
    else:
        results.add_info("All values are non-empty strings.")

    # Check for duplicate names (different keys with same name)
    name_to_keys = defaultdict(list)
    for key, name in mapping.items():
        name_to_keys[name].append(key)
    duplicates = {name: keys for name, keys in name_to_keys.items() if len(keys) > 1}
    if duplicates:
        for name, keys in sorted(duplicates.items()):
            results.add_critical(f"Duplicate name '{name}' used by addresses: {', '.join(keys)}")
    else:
        results.add_info("No duplicate names found.")

    # Warn on short/generic names
    short_names = [(k, v) for k, v in mapping.items()
                   if len(v) < SHORT_NAME_MIN_LEN and '_' not in v and '::' not in v]
    if short_names:
        for k, v in short_names:
            results.add_warning(f"Very short name: '{k}' -> '{v}' (length {len(v)})")
    else:
        results.add_info(f"No names shorter than {SHORT_NAME_MIN_LEN} chars (excluding compound names).")

    results.stats['total_entries'] = len(mapping)
    results.stats['invalid_keys'] = len(invalid_keys)
    results.stats['uppercase_keys'] = len(uppercase_keys)
    results.stats['empty_values'] = len(empty_values)
    results.stats['duplicate_names'] = len(duplicates)
    results.stats['short_names'] = len(short_names)


# ─── 2. Naming Convention Consistency ─────────────────────────────────────────

def is_pascal_case(name):
    """Check if name starts with uppercase and has no underscores (except Class::Method)."""
    base = name.split('::')[-1] if '::' in name else name
    return base[0].isupper() and '_' not in base

def is_camel_case(name):
    """Check if name starts with lowercase and has at least one uppercase letter."""
    return name[0].islower() and any(c.isupper() for c in name)

def is_upper_snake(name):
    """Check if name is UPPER_SNAKE_CASE."""
    return re.match(r'^[A-Z][A-Z0-9_]+$', name) is not None

def is_class_method(name):
    """Check if name looks like Class::Method."""
    return '::' in name

def parse_hex_value(key):
    """Parse the hex key to an integer, handling xx wildcards."""
    clean = key.replace('x', '0')  # treat wildcards as 0
    try:
        return int(clean, 16)
    except ValueError:
        return None

def validate_conventions(mapping, results):
    """Check naming convention consistency."""
    results.add_info("")
    results.add_info("=" * 70)
    results.add_info("SECTION 2: NAMING CONVENTION CONSISTENCY")
    results.add_info("=" * 70)

    convention_issues = []
    convention_counts = Counter()

    for key, name in sorted(mapping.items()):
        value = parse_hex_value(key)
        if value is None:
            continue

        # Determine address category
        hex_digits = key[2:]  # strip '0x'
        num_digits = len(hex_digits.replace('x', ''))

        # Function addresses: 0x14XXXXXXX range (9+ hex digits, starting with 14)
        if hex_digits.startswith('14') and len(hex_digits) >= 9:
            convention_counts['function_address'] += 1
            if not (is_pascal_case(name) or is_class_method(name)):
                # Allow some known patterns
                if not name.startswith('str_'):
                    convention_issues.append(
                        f"  FUNCTION {key}: '{name}' -- expected PascalCase or Class::Method")

        # Class IDs: ending in 000
        elif hex_digits.endswith('000') and value >= 0x01000000:
            convention_counts['class_id'] += 1
            if '_CLASS_ID' not in name and '_LEGACY_CLASS_ID' not in name \
               and '_OLD_CLASS_ID' not in name and '_NEW_CLASS_ID' not in name \
               and 'REMAP_' not in name and 'CHUNK_' not in name \
               and '_LEGACY_CHUNK' not in name:
                convention_issues.append(
                    f"  CLASS_ID {key}: '{name}' -- expected _CLASS_ID suffix "
                    f"(or REMAP_/CHUNK_ prefix)")

        # Chunk IDs: class_id + offset (e.g. 0x03043002)
        elif value >= 0x01000000 and not hex_digits.endswith('000') \
                and not hex_digits.endswith('xx') and len(hex_digits) >= 7:
            # These are usually chunk IDs in the class ID space
            base_class = value & 0xFFFFF000
            offset = value & 0xFFF
            if offset > 0 and offset < 0x100:
                convention_counts['chunk_id'] += 1
                if '_CHUNK_' not in name and '_CHUNK' not in name \
                   and 'CHUNK_' not in name.split('_')[0] \
                   and 'LEGACY_CHUNK' not in name \
                   and 'Chunk' not in name:
                    convention_issues.append(
                        f"  CHUNK {key}: '{name}' -- expected _CHUNK_ in name")

        # Chunk families (ending in xx)
        elif hex_digits.endswith('xx'):
            convention_counts['chunk_family'] += 1
            if '_CHUNK_FAMILY' not in name and '_CHUNK_' not in name:
                convention_issues.append(
                    f"  CHUNK_FAMILY {key}: '{name}' -- expected _CHUNK_FAMILY suffix")

        # Struct offsets: small values < 0x10000
        elif value < 0x10000 and len(hex_digits) <= 4:
            convention_counts['struct_offset'] += 1
            if not (is_camel_case(name) or is_upper_snake(name)):
                # Many small values are constants, not struct offsets
                pass  # Don't flag -- too much noise

        # String addresses (in .rdata typically >= 0x141b00000)
        elif hex_digits.startswith('141') and len(hex_digits) >= 9 and value >= 0x141b00000:
            convention_counts['string_address'] += 1
            if not name.startswith('str_'):
                convention_issues.append(
                    f"  STRING {key}: '{name}' -- expected str_ prefix for string literal")

        # Constants (everything else, medium-sized values)
        else:
            convention_counts['constant'] += 1
            # Constants should ideally be UPPER_SNAKE_CASE
            if not is_upper_snake(name) and '_' in name:
                pass  # Many compound names here, don't over-flag

    if convention_issues:
        results.add_info(f"Found {len(convention_issues)} naming convention issues:")
        for issue in convention_issues:
            results.add_warning(issue)
    else:
        results.add_info("All entries follow expected naming conventions.")

    results.add_info("")
    results.add_info("Address category breakdown:")
    for cat, count in sorted(convention_counts.items()):
        results.add_info(f"  {cat}: {count}")

    results.stats['convention_issues'] = len(convention_issues)
    results.stats['convention_counts'] = dict(convention_counts)


# ─── 3. Coverage Analysis ────────────────────────────────────────────────────

def extract_hex_from_markdown(filepath):
    """Extract hex addresses from markdown, excluding fenced code blocks."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Remove fenced code blocks (``` ... ```)
    # We keep hex refs found in inline code (`0x...`) but exclude fenced blocks
    lines = content.split('\n')
    in_fence = False
    text_lines = []
    for line in lines:
        if line.strip().startswith('```'):
            in_fence = not in_fence
            continue
        if not in_fence:
            text_lines.append(line)

    text = '\n'.join(text_lines)
    return HEX_PATTERN.findall(text)


def validate_coverage(mapping, results):
    """Scan markdown docs and check coverage of hex addresses."""
    results.add_info("")
    results.add_info("=" * 70)
    results.add_info("SECTION 3: COVERAGE ANALYSIS")
    results.add_info("=" * 70)

    # Normalize all mapping keys to lowercase
    mapping_keys = {k.lower() for k in mapping}

    # Also build a set of normalized values (strip leading zeros after 0x for matching)
    def normalize_hex(h):
        """Normalize hex string: lowercase, strip leading zeros but keep at least one digit."""
        h = h.lower()
        prefix = '0x'
        digits = h[2:].lstrip('0') or '0'
        return prefix + digits

    mapping_normalized = {normalize_hex(k) for k in mapping}

    # Scan all markdown files
    doc_hex_refs = Counter()
    file_count = 0
    files_scanned = []

    for doc_dir in DOC_DIRS:
        if not doc_dir.exists():
            results.add_warning(f"Documentation directory not found: {doc_dir}")
            continue
        for md_file in sorted(doc_dir.glob('*.md')):
            file_count += 1
            files_scanned.append(str(md_file.relative_to(SCRIPT_DIR.parent)))
            refs = extract_hex_from_markdown(md_file)
            for ref in refs:
                doc_hex_refs[ref.lower()] += 1

    results.add_info(f"Scanned {file_count} markdown files across {len(DOC_DIRS)} directories.")
    results.add_info(f"Files scanned:")
    for f in files_scanned:
        results.add_info(f"  {f}")

    total_unique_refs = len(doc_hex_refs)
    results.add_info(f"\nTotal unique hex references in docs (outside code blocks): {total_unique_refs}")
    results.add_info(f"Total hex reference occurrences: {sum(doc_hex_refs.values())}")

    # Check which doc refs have mappings
    mapped = set()
    unmapped = set()
    for ref in doc_hex_refs:
        ref_norm = normalize_hex(ref)
        if ref in mapping_keys or ref_norm in mapping_normalized:
            mapped.add(ref)
        else:
            unmapped.add(ref)

    coverage_pct = (len(mapped) / total_unique_refs * 100) if total_unique_refs > 0 else 0

    results.add_info(f"\nMapped addresses:   {len(mapped):>5} ({coverage_pct:.1f}%)")
    results.add_info(f"Unmapped addresses: {len(unmapped):>5} ({100 - coverage_pct:.1f}%)")

    # Top unmapped addresses by reference count
    unmapped_counts = [(ref, doc_hex_refs[ref]) for ref in unmapped]
    unmapped_counts.sort(key=lambda x: -x[1])

    results.add_info(f"\nTop {TOP_UNMAPPED_COUNT} most-referenced unmapped addresses:")
    for ref, count in unmapped_counts[:TOP_UNMAPPED_COUNT]:
        results.add_info(f"  {ref}: referenced {count} time(s)")

    # Also report mapping entries that are never referenced in docs
    referenced_mapping_keys = set()
    for ref in doc_hex_refs:
        if ref in mapping_keys:
            referenced_mapping_keys.add(ref)
        else:
            ref_norm = normalize_hex(ref)
            for mk in mapping_keys:
                if normalize_hex(mk) == ref_norm:
                    referenced_mapping_keys.add(mk)
                    break

    unreferenced_count = len(mapping_keys) - len(referenced_mapping_keys)
    results.add_info(f"\nMapping entries never referenced in prose docs: {unreferenced_count}")
    results.add_info(f"  (This is normal -- many entries are for code blocks or internal use)")

    results.stats['files_scanned'] = file_count
    results.stats['total_unique_doc_refs'] = total_unique_refs
    results.stats['mapped_refs'] = len(mapped)
    results.stats['unmapped_refs'] = len(unmapped)
    results.stats['coverage_pct'] = round(coverage_pct, 1)


# ─── 4. Semantic Sanity Checks ───────────────────────────────────────────────

def validate_semantics(mapping, results):
    """Check for placeholder names, suspicious similarities, and format collisions."""
    results.add_info("")
    results.add_info("=" * 70)
    results.add_info("SECTION 4: SEMANTIC SANITY CHECKS")
    results.add_info("=" * 70)

    # 4a. Placeholder/auto-generated names
    results.add_info("\n--- 4a. Placeholder/auto-generated names ---")
    placeholder_hits = []
    for key, name in sorted(mapping.items()):
        for pat in PLACEHOLDER_PATTERNS:
            if pat.search(name):
                placeholder_hits.append((key, name, pat.pattern))
                break

    if placeholder_hits:
        results.add_info(f"Found {len(placeholder_hits)} potentially placeholder names:")
        for key, name, pattern in placeholder_hits:
            results.add_warning(f"  {key}: '{name}' (matched pattern: {pattern})")
    else:
        results.add_info("No placeholder or auto-generated names detected.")

    # 4b. Suspiciously similar names (potential copy-paste errors)
    results.add_info("\n--- 4b. Suspiciously similar names ---")
    names_list = sorted(mapping.values())
    similar_pairs = []

    # Optimization: only compare names with similar length and prefix
    # Group by first 5 chars for faster comparison
    prefix_groups = defaultdict(list)
    for name in names_list:
        prefix = name[:5].lower()
        prefix_groups[prefix].append(name)

    for prefix, group in prefix_groups.items():
        if len(group) < 2:
            continue
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                n1, n2 = group[i], group[j]
                if n1 == n2:
                    continue
                # Skip pairs that are clearly related (same class, different chunks)
                # e.g., CGameCtnChallenge_CHUNK_MapInfo vs CGameCtnChallenge_CHUNK_Version
                if '::' in n1 and '::' in n2:
                    c1, m1 = n1.split('::', 1)
                    c2, m2 = n2.split('::', 1)
                    if c1 == c2:
                        continue  # Same class, different methods -- intentional
                if '_CHUNK_' in n1 and '_CHUNK_' in n2:
                    base1 = n1.split('_CHUNK_')[0]
                    base2 = n2.split('_CHUNK_')[0]
                    if base1 == base2:
                        continue  # Same class, different chunks -- intentional

                ratio = SequenceMatcher(None, n1, n2).ratio()
                if ratio >= SIMILARITY_THRESHOLD:
                    similar_pairs.append((n1, n2, ratio))

    # Also check globally for very high similarity (>= 0.95)
    # Use a second pass with longer prefix groups
    long_prefix_groups = defaultdict(list)
    for name in names_list:
        prefix = name[:10].lower()
        long_prefix_groups[prefix].append(name)

    for prefix, group in long_prefix_groups.items():
        if len(group) < 2:
            continue
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                n1, n2 = group[i], group[j]
                if n1 == n2:
                    continue
                if (n1, n2) in {(a, b) for a, b, _ in similar_pairs}:
                    continue
                # Skip known-OK patterns
                if '_CHUNK_' in n1 and '_CHUNK_' in n2:
                    base1 = n1.split('_CHUNK_')[0]
                    base2 = n2.split('_CHUNK_')[0]
                    if base1 == base2:
                        continue
                if '::' in n1 and '::' in n2:
                    c1 = n1.split('::')[0]
                    c2 = n2.split('::')[0]
                    if c1 == c2:
                        continue
                ratio = SequenceMatcher(None, n1, n2).ratio()
                if ratio >= 0.95:
                    similar_pairs.append((n1, n2, ratio))

    # Deduplicate
    seen = set()
    unique_pairs = []
    for n1, n2, ratio in similar_pairs:
        pair_key = tuple(sorted([n1, n2]))
        if pair_key not in seen:
            seen.add(pair_key)
            unique_pairs.append((n1, n2, ratio))

    unique_pairs.sort(key=lambda x: -x[2])

    if unique_pairs:
        results.add_info(f"Found {len(unique_pairs)} suspiciously similar name pairs:")
        for n1, n2, ratio in unique_pairs[:30]:  # Cap output
            results.add_warning(f"  {ratio:.0%} similar: '{n1}' vs '{n2}'")
        if len(unique_pairs) > 30:
            results.add_info(f"  ... and {len(unique_pairs) - 30} more pairs")
    else:
        results.add_info("No suspiciously similar names found.")

    # 4c. Same value in different formats
    results.add_info("\n--- 4c. Potential duplicate addresses (different format, same value) ---")
    value_to_keys = defaultdict(list)
    for key in mapping:
        val = parse_hex_value(key)
        if val is not None:
            value_to_keys[val].append(key)

    format_dupes = {v: keys for v, keys in value_to_keys.items() if len(keys) > 1}
    if format_dupes:
        results.add_info(f"Found {len(format_dupes)} values with multiple key formats:")
        for val, keys in sorted(format_dupes.items()):
            names = [f"{k} -> '{mapping[k]}'" for k in keys]
            results.add_warning(f"  Value 0x{val:x} appears as: {'; '.join(names)}")
    else:
        results.add_info("No duplicate address values found in different formats.")

    # 4d. Names with trailing/leading whitespace
    results.add_info("\n--- 4d. Whitespace issues ---")
    ws_issues = [(k, v) for k, v in mapping.items() if v != v.strip()]
    if ws_issues:
        for k, v in ws_issues:
            results.add_critical(f"  {k}: name has leading/trailing whitespace: {repr(v)}")
    else:
        results.add_info("No whitespace issues found.")

    # 4e. Names with unusual characters
    results.add_info("\n--- 4e. Unusual characters in names ---")
    valid_name_pattern = re.compile(r'^[A-Za-z0-9_:]+$')
    unusual_chars = [(k, v) for k, v in mapping.items() if not valid_name_pattern.match(v)]
    if unusual_chars:
        results.add_info(f"Found {len(unusual_chars)} names with unusual characters:")
        for k, v in unusual_chars:
            results.add_warning(f"  {k}: '{v}'")
    else:
        results.add_info("All names use only alphanumeric characters, underscores, and colons.")

    results.stats['placeholder_names'] = len(placeholder_hits)
    results.stats['similar_pairs'] = len(unique_pairs)
    results.stats['format_dupes'] = len(format_dupes)
    results.stats['whitespace_issues'] = len(ws_issues)
    results.stats['unusual_chars'] = len(unusual_chars)


# ─── Report Generation ───────────────────────────────────────────────────────

def generate_report(results):
    """Generate the final validation report."""
    lines = []
    lines.append("=" * 70)
    lines.append("ADDRESS_NAMES.JSON VALIDATION REPORT")
    lines.append("=" * 70)
    lines.append("")

    # Summary
    lines.append("SUMMARY")
    lines.append("-" * 70)
    lines.append(f"Total entries validated:     {results.stats.get('total_entries', 0)}")
    lines.append(f"Critical issues:            {len(results.critical)}")
    lines.append(f"Warnings:                   {len(results.warnings)}")
    lines.append(f"Coverage percentage:         {results.stats.get('coverage_pct', 'N/A')}%")
    lines.append(f"Files scanned:              {results.stats.get('files_scanned', 0)}")
    lines.append("")

    # Issue breakdown
    lines.append("ISSUE BREAKDOWN")
    lines.append("-" * 70)
    lines.append(f"  Integrity:")
    lines.append(f"    Invalid keys:           {results.stats.get('invalid_keys', 0)}")
    lines.append(f"    Uppercase keys:         {results.stats.get('uppercase_keys', 0)}")
    lines.append(f"    Empty values:           {results.stats.get('empty_values', 0)}")
    lines.append(f"    Duplicate names:        {results.stats.get('duplicate_names', 0)}")
    lines.append(f"    Short names:            {results.stats.get('short_names', 0)}")
    lines.append(f"  Conventions:")
    lines.append(f"    Convention issues:       {results.stats.get('convention_issues', 0)}")
    lines.append(f"  Coverage:")
    lines.append(f"    Unique doc hex refs:    {results.stats.get('total_unique_doc_refs', 0)}")
    lines.append(f"    Mapped:                 {results.stats.get('mapped_refs', 0)}")
    lines.append(f"    Unmapped:               {results.stats.get('unmapped_refs', 0)}")
    lines.append(f"  Semantics:")
    lines.append(f"    Placeholder names:      {results.stats.get('placeholder_names', 0)}")
    lines.append(f"    Similar name pairs:     {results.stats.get('similar_pairs', 0)}")
    lines.append(f"    Format duplicate addrs: {results.stats.get('format_dupes', 0)}")
    lines.append(f"    Whitespace issues:      {results.stats.get('whitespace_issues', 0)}")
    lines.append(f"    Unusual characters:     {results.stats.get('unusual_chars', 0)}")
    lines.append("")

    # Detailed results
    lines.append("DETAILED RESULTS")
    lines.append("-" * 70)

    for msg in results.info:
        lines.append(msg)

    if results.critical:
        lines.append("")
        lines.append("=" * 70)
        lines.append(f"CRITICAL ISSUES ({len(results.critical)})")
        lines.append("=" * 70)
        for msg in results.critical:
            lines.append(f"[CRITICAL] {msg}")

    if results.warnings:
        lines.append("")
        lines.append("=" * 70)
        lines.append(f"WARNINGS ({len(results.warnings)})")
        lines.append("=" * 70)
        for msg in results.warnings:
            lines.append(f"[WARNING]  {msg}")

    return '\n'.join(lines)


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    print(f"Loading mapping from {MAPPING_FILE}...")
    with open(MAPPING_FILE, 'r', encoding='utf-8') as f:
        mapping = json.load(f)

    print(f"Loaded {len(mapping)} entries.")

    results = ValidationResults()

    print("Validating integrity...")
    validate_integrity(mapping, results)

    print("Checking naming conventions...")
    validate_conventions(mapping, results)

    print("Analyzing coverage...")
    validate_coverage(mapping, results)

    print("Running semantic checks...")
    validate_semantics(mapping, results)

    # Generate report
    report = generate_report(results)

    print(f"\nWriting report to {REPORT_FILE}...")
    with open(REPORT_FILE, 'w', encoding='utf-8') as f:
        f.write(report)

    # Print summary to console
    print("\n" + "=" * 50)
    print("VALIDATION COMPLETE")
    print("=" * 50)
    print(f"Total entries:    {results.stats['total_entries']}")
    print(f"Critical issues:  {len(results.critical)}")
    print(f"Warnings:         {len(results.warnings)}")
    print(f"Coverage:         {results.stats.get('coverage_pct', 'N/A')}%")
    print(f"Report written to: {REPORT_FILE}")

    # Exit with error code if critical issues found
    if results.critical:
        print(f"\n!! {len(results.critical)} CRITICAL issues require attention !!")
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
