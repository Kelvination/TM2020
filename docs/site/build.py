#!/usr/bin/env python3
"""
Build script for Trackmania 2020 Engine Reference documentation site.
Converts markdown source files to a professional HTML documentation site.
"""

import re
import os
import json
import html as html_module

SITE_DIR = os.path.dirname(os.path.abspath(__file__))
RE_DIR = os.path.join(os.path.dirname(SITE_DIR), 're')
PLAN_DIR = os.path.join(os.path.dirname(SITE_DIR), 'plan')
SEMINAR_DIR = os.path.join(os.path.dirname(SITE_DIR), 'seminar')

# Load address-to-name mapping for named hex addresses
ADDR_NAMES_FILE = os.path.join(SITE_DIR, 'address_names.json')
ADDRESS_NAMES = {}
if os.path.exists(ADDR_NAMES_FILE):
    with open(ADDR_NAMES_FILE, 'r', encoding='utf-8') as f:
        ADDRESS_NAMES = json.load(f)

# Page definitions: (output_file, title, source_files, nav_icon)
# Entries with None as output_file are section separators shown in the sidebar.
# Entries with 'sub:' prefix in output_file are subsection labels within a section.
PAGES = [
    # --- Reverse Engineering ---
    (None, 'Reverse Engineering', [], None),
    # Core Systems
    ('sub:', 'Core Systems', [], None),
    ('index.html', 'Overview', ['00-master-overview.md'], 'home'),
    ('architecture.html', 'Architecture', ['08-game-architecture.md', '12-architecture-deep-dive.md'], 'diagram'),
    ('class-hierarchy.html', 'Class System', ['02-class-hierarchy.md', '13-subsystem-class-map.md'], 'sitemap'),
    ('binary.html', 'Binary Analysis', ['01-binary-overview.md'], 'cpu'),
    # Physics & Driving
    ('sub:', 'Physics & Driving', [], None),
    ('physics.html', 'Physics & Vehicle', ['04-physics-vehicle.md', '10-physics-deep-dive.md'], 'gauge'),
    ('competitive.html', 'Competitive Mechanics', ['21-competitive-mechanics.md'], 'timer'),
    # Rendering
    ('sub:', 'Rendering', [], None),
    ('rendering.html', 'Rendering & Graphics', ['05-rendering-graphics.md', '11-rendering-deep-dive.md'], 'display'),
    ('shaders.html', 'Shader Catalog', ['32-shader-catalog.md'], 'palette'),
    # File Formats & Data
    ('sub:', 'File Formats & Data', [], None),
    ('file-formats.html', 'File Formats', ['06-file-formats.md', '16-fileformat-deep-dive.md'], 'file'),
    ('game-files.html', 'Game Files', ['09-game-files-analysis.md'], 'folder'),
    ('map-structure.html', 'Map Structure', ['28-map-structure-encyclopedia.md'], 'grid'),
    ('ghost-replay.html', 'Ghost & Replay Format', ['30-ghost-replay-format.md'], 'film'),
    ('real-files.html', 'Real File Analysis', ['26-real-file-analysis.md'], 'inspect'),
    # Networking & Audio
    ('sub:', 'Networking & Audio', [], None),
    ('networking.html', 'Networking', ['07-networking.md', '17-networking-deep-dive.md'], 'network'),
    ('audio.html', 'Audio System', ['24-audio-deep-dive.md'], 'speaker'),
    # Scripting & UI
    ('sub:', 'Scripting & UI', [], None),
    ('maniascript.html', 'ManiaScript Reference', ['31-maniascript-reference.md'], 'code'),
    ('ui-manialink.html', 'UI & ManiaLink', ['34-ui-manialink-reference.md'], 'layout'),
    # External Intelligence
    ('sub:', 'External Intelligence', [], None),
    ('openplanet.html', 'Openplanet Intelligence', ['19-openplanet-intelligence.md'], 'puzzle'),
    ('openplanet-mining.html', 'Openplanet Deep Mining', ['25-openplanet-deep-mining.md'], 'gem'),
    ('dll-intelligence.html', 'DLL Intelligence', ['27-dll-intelligence.md'], 'library'),
    ('community.html', 'Community Knowledge', ['29-community-knowledge.md'], 'users'),
    ('tmnf-crossref.html', 'TMNF Comparison', ['14-tmnf-crossref.md'], 'compare'),
    # Research & Validation
    ('sub:', 'Research & Validation', [], None),
    ('ghidra-findings.html', 'Ghidra Research', ['15-ghidra-research-findings.md'], 'search'),
    ('ghidra-gaps.html', 'Ghidra Gap Research', ['22-ghidra-gap-findings.md'], 'microscope'),
    ('validation.html', 'Errata & Corrections', ['18-validation-review.md'], 'check'),
    ('visual-reference.html', 'Visual Reference & Glossary', ['23-visual-reference.md'], 'map'),
    ('recreation.html', 'Browser Recreation Guide', ['20-browser-recreation-guide.md'], 'rocket'),
    # --- Planning ---
    (None, 'Planning', [], None),
    ('plan-overview.html', 'Executive Summary', ['plan:00-executive-summary.md'], 'star'),
    ('plan-architecture.html', 'System Architecture', ['plan:01-system-architecture.md'], 'blueprint'),
    ('plan-physics.html', 'Physics Engine Design', ['plan:02-physics-engine.md'], 'cog'),
    ('plan-renderer.html', 'Renderer Design', ['plan:03-renderer-design.md'], 'palette'),
    ('plan-assets.html', 'Asset Pipeline', ['plan:04-asset-pipeline.md'], 'package'),
    ('plan-blockmesh.html', 'Block Mesh Research', ['plan:05-block-mesh-research.md'], 'cube'),
    ('plan-determinism.html', 'Determinism Analysis', ['plan:06-determinism-analysis.md'], 'check'),
    ('plan-constants.html', 'Physics Constants', ['plan:07-physics-constants.md'], 'hash'),
    ('plan-mvp.html', 'MVP Task Breakdown', ['plan:08-mvp-tasks.md'], 'list'),
    ('plan-tuning.html', 'Tuning Data Extraction', ['plan:09-tuning-data-extraction.md'], 'sliders'),
    ('plan-tuning-loading.html', 'Tuning Loading Analysis', ['plan:10-tuning-loading-analysis.md'], 'download'),
    # --- Seminar ---
    (None, 'Seminar', [], None),
    ('seminar-alex.html', 'Alex: Physics Notes', ['seminar:alex-physics-notes.md'], 'notebook'),
    ('seminar-maya.html', 'Maya: Rendering Notes', ['seminar:maya-rendering-notes.md'], 'brush'),
    ('seminar-jordan.html', 'Jordan: Systems Notes', ['seminar:jordan-systems-notes.md'], 'diagram'),
    ('seminar-chen.html', 'Prof. Chen: Physics Lectures', ['seminar:prof-chen-physics-lectures.md'], 'school'),
    ('seminar-kovac.html', 'Prof. Kovac: Graphics Lectures', ['seminar:prof-kovac-graphics-lectures.md'], 'school'),
]

def read_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def escape_html(text):
    return html_module.escape(text)

def slugify(text):
    text = re.sub(r'<[^>]+>', '', text)
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s]+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text.strip('-')

def convert_inline(text):
    """Convert inline markdown to HTML."""
    # Escape HTML first but preserve already-processed tags
    # We need to be careful here - process in specific order

    # Bold+italic
    text = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong><em>\1</em></strong>', text)
    # Bold
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    # Italic
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)

    # Inline code
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)

    # Links - internal .md links to .html
    def convert_link(m):
        link_text = m.group(1)
        url = m.group(2)
        # Convert internal markdown links
        if url.startswith('#'):
            return f'<a href="{url}">{link_text}</a>'
        # Map md files to html pages
        url = map_md_to_html(url)
        return f'<a href="{url}">{link_text}</a>'

    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', convert_link, text)

    # Confidence badges
    text = re.sub(r'\bVERIFIED\b', '<span class="badge badge-verified">VERIFIED</span>', text)
    text = re.sub(r'\bPLAUSIBLE\b', '<span class="badge badge-plausible">PLAUSIBLE</span>', text)
    text = re.sub(r'\bSPECULATIVE\b', '<span class="badge badge-speculative">SPECULATIVE</span>', text)
    text = re.sub(r'\[UNKNOWN[^\]]*\]', lambda m: f'<span class="badge badge-unknown">{m.group(0)}</span>', text)
    text = re.sub(r'\bUNKNOWN\b(?![^<]*>)', '<span class="badge badge-unknown">UNKNOWN</span>', text)

    # --- Ghidra FUN_/DAT_ references (process BEFORE 0x addresses) ---

    # Pattern: (FUN_XXXXXXXX @ 0xXXXXXXXXX) - hide entire parenthetical
    text = re.sub(
        r'\s*\(FUN_[0-9a-fA-F]{6,16}\s*@\s*0x[0-9a-fA-F]{6,16}\)',
        lambda m: f'<span class="ghidra-ref">{escape_html(m.group(0))}</span>',
        text
    )

    # Pattern: (FUN_XXXXXXXX) - hide parenthetical
    text = re.sub(
        r'\s*\(FUN_[0-9a-fA-F]{6,16}\)',
        lambda m: f'<span class="ghidra-ref">{escape_html(m.group(0))}</span>',
        text
    )

    # FUN_XXXXXXXX in <code> tags - replace with named version
    def fun_code_replace(m):
        hex_part = m.group(1).lower()
        addr = '0x' + hex_part
        name = ADDRESS_NAMES.get(addr)
        if name:
            return (f'<span class="named-addr">'
                    f'<span class="addr-name">{escape_html(name)}</span>'
                    f'<code class="ghidra-ref">FUN_{m.group(1)}</code>'
                    f'</span>')
        return m.group(0)

    text = re.sub(r'<code>FUN_([0-9a-fA-F]{6,16})</code>', fun_code_replace, text)

    # Bare FUN_XXXXXXXX in prose (not inside tags or already-processed spans)
    def fun_bare_replace(m):
        full = m.group(0)
        start = m.start()
        prefix = text[:start]
        # Skip if inside an HTML tag
        last_lt = prefix.rfind('<')
        last_gt = prefix.rfind('>')
        if last_lt > last_gt:
            return full
        # Skip if inside a ghidra-ref or named-addr span
        last_ghidra = prefix.rfind('ghidra-ref')
        last_named = prefix.rfind('named-addr')
        last_span_close = prefix.rfind('</span>')
        if max(last_ghidra, last_named) > last_span_close:
            return full
        hex_part = m.group(1).lower()
        addr = '0x' + hex_part
        name = ADDRESS_NAMES.get(addr)
        if name:
            return (f'<span class="named-addr">'
                    f'<span class="addr-name">{escape_html(name)}</span>'
                    f'<span class="ghidra-ref">{full}</span>'
                    f'</span>')
        return full

    text = re.sub(r'FUN_([0-9a-fA-F]{6,16})', fun_bare_replace, text)

    # DAT_XXXXXXXX in <code> tags
    def dat_code_replace(m):
        hex_part = m.group(1).lower()
        addr = '0x' + hex_part
        name = ADDRESS_NAMES.get(addr)
        if name:
            return (f'<span class="named-addr">'
                    f'<span class="addr-name">{escape_html(name)}</span>'
                    f'<code class="ghidra-ref">DAT_{m.group(1)}</code>'
                    f'</span>')
        return m.group(0)

    text = re.sub(r'<code>DAT_([0-9a-fA-F]{6,16})</code>', dat_code_replace, text)

    # Bare DAT_XXXXXXXX in prose (not inside tags or already-processed spans)
    def dat_bare_replace(m):
        full = m.group(0)
        start = m.start()
        prefix = text[:start]
        last_lt = prefix.rfind('<')
        last_gt = prefix.rfind('>')
        if last_lt > last_gt:
            return full
        last_ghidra = prefix.rfind('ghidra-ref')
        last_named = prefix.rfind('named-addr')
        last_span_close = prefix.rfind('</span>')
        if max(last_ghidra, last_named) > last_span_close:
            return full
        hex_part = m.group(1).lower()
        addr = '0x' + hex_part
        name = ADDRESS_NAMES.get(addr)
        if name:
            return (f'<span class="named-addr">'
                    f'<span class="addr-name">{escape_html(name)}</span>'
                    f'<span class="ghidra-ref">{full}</span>'
                    f'</span>')
        return full

    text = re.sub(r'DAT_([0-9a-fA-F]{6,16})', dat_bare_replace, text)

    # --- 0x hex addresses ---

    # Named addresses - replace hex with symbolic names when mapping exists
    def named_addr_code(m):
        addr = m.group(1)
        addr_lower = addr.lower()
        # Look up in mapping (try both original case and lowercase)
        name = ADDRESS_NAMES.get(addr_lower) or ADDRESS_NAMES.get(addr)
        if name:
            return (f'<span class="named-addr">'
                    f'<span class="addr-name">{escape_html(name)}</span>'
                    f'<code class="addr">{addr}</code>'
                    f'</span>')
        # Not in mapping - apply addr class for long addresses (8+ hex digits)
        if len(addr) - 2 >= 8:
            return f'<code class="addr">{addr}</code>'
        return f'<code>{addr}</code>'

    text = re.sub(r'<code>(0x[0-9a-fA-F]{2,16})</code>', named_addr_code, text)

    # Also catch bare hex addresses (8-16 hex digits) not already in code tags
    def bare_addr_replace(m):
        addr = m.group(0)
        start = m.start()
        prefix = text[:start]
        # Skip if inside a tag attribute or already in a code/span element
        if prefix.endswith('"') or prefix.endswith("'"):
            return addr
        last_code_open = prefix.rfind('<code')
        last_code_close = prefix.rfind('</code>')
        if last_code_open > last_code_close:
            return addr
        # Skip if inside a ghidra-ref or named-addr span
        last_ghidra = prefix.rfind('ghidra-ref')
        last_named = prefix.rfind('named-addr')
        last_span_close = prefix.rfind('</span>')
        if max(last_ghidra, last_named) > last_span_close:
            return addr
        # Check naming mapping
        addr_lower = addr.lower()
        name = ADDRESS_NAMES.get(addr_lower) or ADDRESS_NAMES.get(addr)
        if name:
            return (f'<span class="named-addr">'
                    f'<span class="addr-name">{escape_html(name)}</span>'
                    f'<code class="addr">{addr}</code>'
                    f'</span>')
        return f'<code class="addr">{addr}</code>'

    text = re.sub(r'(?<![\w"\'/>])0x[0-9a-fA-F]{8,16}(?![\w"\'<])', bare_addr_replace, text)

    return text

MD_TO_HTML_MAP = {
    '00-master-overview.md': 'index.html',
    '01-binary-overview.md': 'binary.html',
    '02-class-hierarchy.md': 'class-hierarchy.html',
    '04-physics-vehicle.md': 'physics.html',
    '05-rendering-graphics.md': 'rendering.html',
    '06-file-formats.md': 'file-formats.html',
    '07-networking.md': 'networking.html',
    '08-game-architecture.md': 'architecture.html',
    '09-game-files-analysis.md': 'game-files.html',
    '10-physics-deep-dive.md': 'physics.html',
    '11-rendering-deep-dive.md': 'rendering.html',
    '12-architecture-deep-dive.md': 'architecture.html',
    '13-subsystem-class-map.md': 'class-hierarchy.html',
    '14-tmnf-crossref.md': 'tmnf-crossref.html',
    '16-fileformat-deep-dive.md': 'file-formats.html',
    '17-networking-deep-dive.md': 'networking.html',
}

def map_md_to_html(url):
    # Handle anchor links
    parts = url.split('#')
    filename = parts[0]
    anchor = '#' + parts[1] if len(parts) > 1 else ''

    if filename in MD_TO_HTML_MAP:
        return MD_TO_HTML_MAP[filename] + anchor
    return url

def parse_table(lines):
    """Parse markdown table lines into HTML table."""
    if len(lines) < 2:
        return '<p>' + '<br>'.join(lines) + '</p>'

    # First line is header
    header = [cell.strip() for cell in lines[0].strip('|').split('|')]
    # Second line is separator - check alignment
    sep = [cell.strip() for cell in lines[1].strip('|').split('|')]
    alignments = []
    for s in sep:
        if s.startswith(':') and s.endswith(':'):
            alignments.append('center')
        elif s.endswith(':'):
            alignments.append('right')
        else:
            alignments.append('left')

    while len(alignments) < len(header):
        alignments.append('left')

    html = '<div class="table-wrapper"><table>\n<thead>\n<tr>\n'
    for i, h in enumerate(header):
        align = alignments[i] if i < len(alignments) else 'left'
        html += f'  <th style="text-align:{align}">{convert_inline(h)}</th>\n'
    html += '</tr>\n</thead>\n<tbody>\n'

    for line in lines[2:]:
        cells = [cell.strip() for cell in line.strip('|').split('|')]
        html += '<tr>\n'
        for i, cell in enumerate(cells):
            align = alignments[i] if i < len(alignments) else 'left'
            html += f'  <td style="text-align:{align}">{convert_inline(cell)}</td>\n'
        html += '</tr>\n'

    html += '</tbody>\n</table></div>\n'
    return html

def markdown_to_html(md_text):
    """Convert markdown text to HTML."""
    lines = md_text.split('\n')
    html_parts = []
    toc = []  # (level, id, text)
    i = 0
    in_code_block = False
    code_lang = ''
    code_lines = []
    in_list = False
    list_items = []
    list_type = 'ul'
    in_table = False
    table_lines = []

    def flush_list():
        nonlocal in_list, list_items, list_type
        if in_list and list_items:
            tag = list_type
            html_parts.append(f'<{tag}>\n')
            for item in list_items:
                html_parts.append(f'  <li>{convert_inline(item)}</li>\n')
            html_parts.append(f'</{tag}>\n')
            list_items = []
            in_list = False

    def flush_table():
        nonlocal in_table, table_lines
        if in_table and table_lines:
            html_parts.append(parse_table(table_lines))
            table_lines = []
            in_table = False

    while i < len(lines):
        line = lines[i]

        # Code blocks
        if line.strip().startswith('```'):
            if in_code_block:
                # End code block
                code_content = '\n'.join(code_lines)
                lang_class = f' class="language-{code_lang}"' if code_lang else ''
                escaped = escape_html(code_content)
                html_parts.append(f'<div class="code-block"><button class="copy-btn" title="Copy to clipboard">Copy</button><pre><code{lang_class}>{escaped}</code></pre></div>\n')
                in_code_block = False
                code_lines = []
                code_lang = ''
            else:
                flush_list()
                flush_table()
                in_code_block = True
                code_lang = line.strip().lstrip('`').strip()
                if not code_lang or ' ' in code_lang:
                    code_lang = ''
            i += 1
            continue

        if in_code_block:
            code_lines.append(line)
            i += 1
            continue

        # HTML passthrough - pass through raw HTML block tags (details, summary, div, etc.)
        if re.match(r'^\s*<(details|/details|summary|/summary|div|/div)\b', line.strip()):
            flush_list()
            flush_table()
            html_parts.append(line + '\n')
            i += 1
            continue

        # Horizontal rules
        if re.match(r'^---+\s*$', line):
            flush_list()
            flush_table()
            html_parts.append('<hr>\n')
            i += 1
            continue

        # Headings
        heading_match = re.match(r'^(#{1,6})\s+(.+)$', line)
        if heading_match:
            flush_list()
            flush_table()
            level = len(heading_match.group(1))
            text = heading_match.group(2).strip()
            slug = slugify(text)
            # Ensure unique slugs
            base_slug = slug
            counter = 1
            existing_slugs = [t[1] for t in toc]
            while slug in existing_slugs:
                slug = f'{base_slug}-{counter}'
                counter += 1

            if level in (2, 3):
                toc.append((level, slug, text))

            converted_text = convert_inline(text)
            html_parts.append(f'<h{level} id="{slug}"><a class="anchor" href="#{slug}">#</a>{converted_text}</h{level}>\n')
            i += 1
            continue

        # Tables
        if '|' in line and re.match(r'^\s*\|', line):
            flush_list()
            if not in_table:
                in_table = True
                table_lines = []
            table_lines.append(line)
            i += 1
            continue
        else:
            flush_table()

        # Unordered lists
        list_match = re.match(r'^(\s*)[-*+]\s+(.+)$', line)
        if list_match:
            flush_table()
            if not in_list:
                in_list = True
                list_type = 'ul'
                list_items = []
            list_items.append(list_match.group(2))
            i += 1
            continue

        # Ordered lists
        ol_match = re.match(r'^(\s*)\d+\.\s+(.+)$', line)
        if ol_match:
            flush_table()
            if not in_list:
                in_list = True
                list_type = 'ol'
                list_items = []
            list_items.append(ol_match.group(2))
            i += 1
            continue

        # Checkbox lists
        cb_match = re.match(r'^[-*]\s+\[([xX ])\]\s+(.+)$', line)
        if cb_match:
            flush_table()
            if not in_list:
                in_list = True
                list_type = 'ul'
                list_items = []
            checked = 'checked' if cb_match.group(1).lower() == 'x' else ''
            list_items.append(f'<input type="checkbox" {checked} disabled> {cb_match.group(2)}')
            i += 1
            continue

        # Not a list item - flush any pending list
        flush_list()

        # Empty lines
        if not line.strip():
            i += 1
            continue

        # Paragraph
        para_lines = []
        while i < len(lines) and lines[i].strip() and not lines[i].startswith('#') and not lines[i].startswith('```') and not re.match(r'^\s*[-*+]\s+', lines[i]) and not re.match(r'^\s*\d+\.\s+', lines[i]) and not re.match(r'^\s*\|', lines[i]) and not re.match(r'^---+', lines[i]):
            para_lines.append(lines[i])
            i += 1

        if para_lines:
            text = ' '.join(para_lines)
            html_parts.append(f'<p>{convert_inline(text)}</p>\n')
            continue

        i += 1

    flush_list()
    flush_table()

    return ''.join(html_parts), toc

def add_collapsible_sections(html):
    """Wrap technical/binary sections in collapsible <details> elements.

    Scans for <h2> and <h3> headings whose text matches binary/technical patterns,
    then wraps the heading + its content (up to the next same-level heading) in
    <details> elements that are collapsed by default.
    """
    import re as _re

    # Patterns that indicate a section should be auto-collapsed
    collapse_patterns = [
        r'\bhex\b', r'\bdump\b', r'\bbyte[s]?\b', r'offset\s*table',
        r'\baddress', r'\bdata\s+at\b', r'\bxxd\b',
        r'struct\s+offset', r'struct\s+layout', r'memory\s+layout',
        r'key\s+function\s+reference', r'critical\s+address',
        r'decompiled\s+code\s+index',
        r'\bpe\s+header', r'\bsection\s+(layout|info|table)',
        r'\bimport\s+(analysis|table)', r'\bexport\s+(analysis|table)',
        r'\bvalidation\b',
        r'0x[0-9a-fA-F]',
        r'\bfunction\s+statistics', r'\bstring\s+statistics',
        r'\bentry\s+point',
    ]

    # Patterns that should ALWAYS stay open (checked first)
    keep_open_patterns = [
        r'\bQ\d*:', r'\bquestion\b', r'\bhow\s', r'\bwhat\s',
        r'\bwalk', r'\btutorial\b', r'\bguide\b',
        r'\bimplementation\b', r'\bbrowser\b', r'\bwebgpu\b', r'\btypescript\b',
        r'\boverview\b', r'\bexecutive\b',
        r'^summary\b', r'\barchitecture\b',
    ]

    def should_collapse(heading_text):
        """Determine if a heading's section should be collapsed by default."""
        # Strip HTML tags to get plain text
        plain = _re.sub(r'<[^>]+>', '', heading_text).strip()
        # Remove leading '#' from anchor links
        plain = plain.lstrip('#').strip()
        text_lower = plain.lower()

        # Check keep-open patterns first
        for pat in keep_open_patterns:
            if _re.search(pat, text_lower):
                return False

        # Check collapse patterns
        for pat in collapse_patterns:
            if _re.search(pat, text_lower):
                return True

        return False

    # Find all h2 and h3 headings with their positions
    heading_re = _re.compile(r'(<h([23])\s+id="([^"]*)"[^>]*>)(.*?)(</h\2>)', _re.DOTALL)

    matches = list(heading_re.finditer(html))
    if not matches:
        return html

    # Process from last to first so positions don't shift
    for idx in range(len(matches) - 1, -1, -1):
        m = matches[idx]
        heading_level = int(m.group(2))
        heading_id = m.group(3)
        heading_inner = m.group(4)  # Content between <hN> and </hN>
        full_heading = m.group(0)

        if not should_collapse(heading_inner):
            continue

        # Find the end of this section: next heading of same or higher level
        section_start = m.start()
        section_content_start = m.end()

        # Look for the next heading at same or higher (lower number) level
        next_heading_re = _re.compile(r'<h([1-' + str(heading_level) + r'])\s', _re.IGNORECASE)
        next_match = next_heading_re.search(html, section_content_start)

        if next_match:
            section_end = next_match.start()
        else:
            section_end = len(html)

        # Extract the content after the heading
        section_content = html[section_content_start:section_end]

        # Build the <details> wrapper
        # The heading becomes the <summary>, content goes inside
        details_html = (
            f'<details class="collapsible collapsed-by-default">\n'
            f'<summary>{full_heading}</summary>\n'
            f'<div class="collapsible-content">{section_content}</div>\n'
            f'</details>\n'
        )

        # Replace the section in the HTML
        html = html[:section_start] + details_html + html[section_end:]

    return html

def build_toc_html(toc):
    """Build table of contents from heading list."""
    if not toc:
        return ''
    html = '<nav class="page-toc" id="page-toc">\n<h3>On This Page</h3>\n<ul>\n'
    for level, slug, text in toc:
        indent = '  ' * (level - 2)
        cls = 'toc-h3' if level == 3 else ''
        html += f'{indent}<li class="{cls}"><a href="#{slug}">{escape_html(text)}</a></li>\n'
    html += '</ul>\n</nav>\n'
    return html

def build_sidebar(current_page):
    """Build navigation sidebar."""
    nav_items = []
    for filename, title, _, icon in PAGES:
        if filename is None:
            # Section separator
            nav_items.append(f'<div class="nav-section">{escape_html(title)}</div>')
            continue
        if filename == 'sub:':
            # Subsection label within a section
            nav_items.append(f'<div class="nav-subsection">{escape_html(title)}</div>')
            continue
        active = ' active' if filename == current_page else ''
        nav_items.append(f'<a class="nav-item{active}" href="{filename}"><span class="nav-text">{escape_html(title)}</span></a>')

    return '\n'.join(nav_items)

def build_prev_next(current_page):
    """Build previous/next navigation."""
    # Filter out section separators and subsection labels for prev/next navigation
    real_pages = [p for p in PAGES if p[0] is not None and p[0] != 'sub:']
    filenames = [p[0] for p in real_pages]
    idx = filenames.index(current_page) if current_page in filenames else -1

    prev_html = ''
    next_html = ''

    if idx > 0:
        prev_file = real_pages[idx - 1][0]
        prev_title = real_pages[idx - 1][1]
        prev_html = f'<a class="prev" href="{prev_file}">&larr; {escape_html(prev_title)}</a>'

    if idx < len(real_pages) - 1 and idx >= 0:
        next_file = real_pages[idx + 1][0]
        next_title = real_pages[idx + 1][1]
        next_html = f'<a class="next" href="{next_file}">{escape_html(next_title)} &rarr;</a>'

    return f'<nav class="prev-next">{prev_html}{next_html}</nav>'

def build_page(page_def):
    """Build a complete HTML page."""
    filename, title, sources, icon = page_def

    # Read and combine source files
    combined_md = ''
    for src in sources:
        # Sources prefixed with 'plan:' resolve from PLAN_DIR
        if src.startswith('plan:'):
            src_path = os.path.join(PLAN_DIR, src[5:])
        elif src.startswith('seminar:'):
            src_path = os.path.join(SEMINAR_DIR, src[8:])
        else:
            src_path = os.path.join(RE_DIR, src)
        if os.path.exists(src_path):
            if combined_md:
                combined_md += '\n\n---\n\n'
            combined_md += read_file(src_path)
        else:
            print(f"WARNING: Source file not found: {src_path}")

    content_html, toc = markdown_to_html(combined_md)
    content_html = add_collapsible_sections(content_html)
    toc_html = build_toc_html(toc)
    sidebar_html = build_sidebar(filename)
    prev_next_html = build_prev_next(filename)

    is_plan_page = filename.startswith('plan-')
    if is_plan_page:
        disclaimer_html = ''
        page_title = f'{title} - Trackmania 2020 Planning'
    else:
        disclaimer_html = (
            '<div class="disclaimer">'
            'This documentation is produced through reverse engineering for educational purposes. '
            'All findings are based on static analysis of embedded debug strings, not official documentation.'
            '</div>'
        )
        page_title = f'{title} - Trackmania 2020 Engine Reference'

    html = f'''<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{escape_html(page_title)}</title>
    <link rel="stylesheet" href="style.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/atom-one-dark.min.css" id="hljs-theme">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/languages/c.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/languages/cpp.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/languages/x86asm.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/languages/json.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/languages/xml.min.js"></script>
</head>
<body>
    <div class="layout">
        <!-- Sidebar -->
        <aside class="sidebar" id="sidebar">
            <div class="sidebar-header">
                <h1 class="site-title"><a href="index.html">TM2020 Engine Reference</a></h1>
                <p class="site-subtitle">Reverse Engineering Documentation</p>
            </div>
            <div class="sidebar-search">
                <input type="text" id="search-input" placeholder="Search documentation..." autocomplete="off">
                <div id="search-results" class="search-results"></div>
            </div>
            <div class="sidebar-toggle">
                <button id="tech-toggle" class="tech-toggle" title="Toggle visibility of technical/binary detail sections">
                    <span class="toggle-icon">&#9660;</span>
                    Hide Technical Details
                </button>
            </div>
            <div class="sidebar-toggle">
                <button id="addr-toggle" class="tech-toggle collapsed" title="Toggle hex address display alongside symbol names">
                    <span class="toggle-icon">&#9654;</span>
                     Show Hex Addresses
                </button>
            </div>
            <nav class="sidebar-nav" id="sidebar-nav">
                {sidebar_html}
            </nav>
            <div class="sidebar-footer">
                <button id="theme-toggle" class="theme-toggle" title="Toggle dark/light theme">
                    <span class="theme-icon-dark">&#9790;</span>
                    <span class="theme-icon-light">&#9728;</span>
                </button>
            </div>
        </aside>

        <!-- Mobile header -->
        <header class="mobile-header">
            <button class="menu-toggle" id="menu-toggle" aria-label="Toggle navigation">
                <span></span><span></span><span></span>
            </button>
            <span class="mobile-title">TM2020 Engine Reference</span>
            <button id="theme-toggle-mobile" class="theme-toggle" title="Toggle theme">
                <span class="theme-icon-dark">&#9790;</span>
                <span class="theme-icon-light">&#9728;</span>
            </button>
        </header>

        <!-- Main content -->
        <main class="content" id="content">
            <div class="content-wrapper">
                <!-- Breadcrumb -->
                <nav class="breadcrumb">
                    <a href="index.html">Home</a>
                    <span class="sep">/</span>
                    <span>{escape_html(title)}</span>
                </nav>

                <div class="content-body">
                    <div class="content-main">
                        {disclaimer_html}
                        {content_html}
                        {prev_next_html}
                    </div>
                    {toc_html}
                </div>
            </div>
        </main>
    </div>

    <button class="scroll-top" id="scroll-top" title="Scroll to top">&uarr;</button>
    <div class="overlay" id="overlay"></div>

    <script src="address_map.js"></script>
    <script src="script.js"></script>
</body>
</html>'''

    return html

def build_css():
    """Build the stylesheet."""
    return '''/* ========================================
   Trackmania 2020 Engine Reference - Styles
   ======================================== */

/* CSS Variables */
:root {
    --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, sans-serif;
    --font-mono: "JetBrains Mono", "Fira Code", "SF Mono", Consolas, "Liberation Mono", monospace;
    --sidebar-width: 280px;
    --toc-width: 220px;
    --max-content: 900px;
    --transition: 0.2s ease;
}

[data-theme="dark"] {
    --bg-primary: #1a1b26;
    --bg-secondary: #16161e;
    --bg-tertiary: #24283b;
    --bg-hover: #292e42;
    --bg-code: #1e2030;
    --text-primary: #c0caf5;
    --text-secondary: #a9b1d6;
    --text-muted: #565f89;
    --text-heading: #c0caf5;
    --accent: #7aa2f7;
    --accent-hover: #89b4fa;
    --border: #292e42;
    --border-light: #3b4261;
    --badge-verified: #9ece6a;
    --badge-verified-bg: rgba(158, 206, 106, 0.15);
    --badge-plausible: #e0af68;
    --badge-plausible-bg: rgba(224, 175, 104, 0.15);
    --badge-speculative: #f7768e;
    --badge-speculative-bg: rgba(247, 118, 142, 0.15);
    --badge-unknown: #565f89;
    --badge-unknown-bg: rgba(86, 95, 137, 0.15);
    --table-stripe: rgba(41, 46, 66, 0.5);
    --shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
    --code-addr: #bb9af7;
    --scrollbar-bg: #16161e;
    --scrollbar-thumb: #3b4261;
    --disclaimer-bg: rgba(122, 162, 247, 0.08);
    --disclaimer-border: rgba(122, 162, 247, 0.3);
}

[data-theme="light"] {
    --bg-primary: #ffffff;
    --bg-secondary: #f8f9fa;
    --bg-tertiary: #e9ecef;
    --bg-hover: #dee2e6;
    --bg-code: #f1f3f5;
    --text-primary: #212529;
    --text-secondary: #495057;
    --text-muted: #868e96;
    --text-heading: #1a1b26;
    --accent: #2563eb;
    --accent-hover: #1d4ed8;
    --border: #dee2e6;
    --border-light: #e9ecef;
    --badge-verified: #16a34a;
    --badge-verified-bg: rgba(22, 163, 74, 0.1);
    --badge-plausible: #ca8a04;
    --badge-plausible-bg: rgba(202, 138, 4, 0.1);
    --badge-speculative: #dc2626;
    --badge-speculative-bg: rgba(220, 38, 38, 0.1);
    --badge-unknown: #6b7280;
    --badge-unknown-bg: rgba(107, 114, 128, 0.1);
    --table-stripe: rgba(0, 0, 0, 0.02);
    --shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
    --code-addr: #7c3aed;
    --scrollbar-bg: #f8f9fa;
    --scrollbar-thumb: #ced4da;
    --disclaimer-bg: rgba(37, 99, 235, 0.05);
    --disclaimer-border: rgba(37, 99, 235, 0.2);
}

/* Reset */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

html {
    scroll-behavior: smooth;
    scroll-padding-top: 80px;
}

body {
    font-family: var(--font-sans);
    font-size: 15px;
    line-height: 1.7;
    color: var(--text-primary);
    background: var(--bg-primary);
    -webkit-font-smoothing: antialiased;
    overflow-x: hidden;
}

/* Scrollbar */
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: var(--scrollbar-bg); }
::-webkit-scrollbar-thumb { background: var(--scrollbar-thumb); border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }

/* Layout */
.layout {
    display: flex;
    min-height: 100vh;
}

/* Sidebar */
.sidebar {
    width: var(--sidebar-width);
    background: var(--bg-secondary);
    border-right: 1px solid var(--border);
    position: fixed;
    top: 0;
    left: 0;
    bottom: 0;
    display: flex;
    flex-direction: column;
    z-index: 100;
    overflow: hidden;
}

.sidebar-header {
    padding: 20px 16px 12px;
    border-bottom: 1px solid var(--border);
}

.site-title {
    font-size: 16px;
    font-weight: 700;
    letter-spacing: -0.02em;
    line-height: 1.3;
}

.site-title a {
    color: var(--accent);
    text-decoration: none;
}

.site-subtitle {
    font-size: 11px;
    color: var(--text-muted);
    margin-top: 2px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.sidebar-search {
    padding: 12px 16px;
    position: relative;
}

.sidebar-search input {
    width: 100%;
    padding: 8px 12px;
    background: var(--bg-tertiary);
    border: 1px solid var(--border);
    border-radius: 6px;
    color: var(--text-primary);
    font-size: 13px;
    font-family: var(--font-sans);
    outline: none;
    transition: border-color var(--transition);
}

.sidebar-search input:focus {
    border-color: var(--accent);
}

.sidebar-search input::placeholder {
    color: var(--text-muted);
}

.search-results {
    display: none;
    position: absolute;
    top: 100%;
    left: 16px;
    right: 16px;
    background: var(--bg-tertiary);
    border: 1px solid var(--border);
    border-radius: 6px;
    max-height: 300px;
    overflow-y: auto;
    z-index: 200;
    box-shadow: var(--shadow);
}

.search-results.active { display: block; }

.search-result-item {
    display: block;
    padding: 8px 12px;
    color: var(--text-primary);
    text-decoration: none;
    font-size: 13px;
    border-bottom: 1px solid var(--border);
    transition: background var(--transition);
}

.search-result-item:hover { background: var(--bg-hover); }
.search-result-item:last-child { border-bottom: none; }

.search-result-item .result-page {
    font-size: 11px;
    color: var(--text-muted);
}

.sidebar-nav {
    flex: 1;
    overflow-y: auto;
    padding: 8px 0;
}

.nav-section {
    padding: 12px 16px 4px;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-muted);
    border-top: 1px solid var(--border);
    margin-top: 8px;
}

.nav-section:first-child {
    border-top: none;
    margin-top: 0;
}

.nav-subsection {
    padding: 6px 16px 2px 24px;
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-muted);
    opacity: 0.7;
    margin-top: 4px;
}

.nav-subsection + .nav-item {
    /* No extra margin needed */
}

.nav-item {
    display: flex;
    align-items: center;
    padding: 8px 16px;
    color: var(--text-secondary);
    text-decoration: none;
    font-size: 14px;
    transition: all var(--transition);
    border-left: 3px solid transparent;
}

.nav-item:hover {
    background: var(--bg-hover);
    color: var(--text-primary);
}

.nav-item.active {
    background: var(--bg-hover);
    color: var(--accent);
    border-left-color: var(--accent);
    font-weight: 600;
}

.sidebar-footer {
    padding: 12px 16px;
    border-top: 1px solid var(--border);
    display: flex;
    justify-content: center;
}

/* Theme Toggle */
.theme-toggle {
    background: var(--bg-tertiary);
    border: 1px solid var(--border);
    color: var(--text-secondary);
    padding: 6px 12px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 16px;
    transition: all var(--transition);
}

.theme-toggle:hover {
    background: var(--bg-hover);
    color: var(--text-primary);
}

[data-theme="dark"] .theme-icon-light { display: none; }
[data-theme="light"] .theme-icon-dark { display: none; }

/* Mobile Header */
.mobile-header {
    display: none;
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    height: 50px;
    background: var(--bg-secondary);
    border-bottom: 1px solid var(--border);
    z-index: 90;
    align-items: center;
    padding: 0 12px;
    gap: 12px;
}

.menu-toggle {
    background: none;
    border: none;
    cursor: pointer;
    padding: 4px;
    display: flex;
    flex-direction: column;
    gap: 4px;
}

.menu-toggle span {
    display: block;
    width: 20px;
    height: 2px;
    background: var(--text-secondary);
    border-radius: 1px;
    transition: var(--transition);
}

.mobile-title {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
    flex: 1;
}

/* Main Content */
.content {
    flex: 1;
    margin-left: var(--sidebar-width);
    min-width: 0;
}

.content-wrapper {
    max-width: calc(var(--max-content) + var(--toc-width) + 60px);
    margin: 0 auto;
    padding: 24px 32px;
}

.content-body {
    display: flex;
    gap: 32px;
}

.content-main {
    flex: 1;
    min-width: 0;
    max-width: var(--max-content);
}

/* Breadcrumb */
.breadcrumb {
    font-size: 13px;
    color: var(--text-muted);
    margin-bottom: 20px;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--border);
}

.breadcrumb a {
    color: var(--accent);
    text-decoration: none;
}

.breadcrumb a:hover { text-decoration: underline; }

.breadcrumb .sep {
    margin: 0 6px;
    color: var(--text-muted);
}

/* Disclaimer */
.disclaimer {
    background: var(--disclaimer-bg);
    border: 1px solid var(--disclaimer-border);
    border-radius: 6px;
    padding: 12px 16px;
    font-size: 13px;
    color: var(--text-secondary);
    margin-bottom: 24px;
    line-height: 1.5;
}

/* Typography */
h1, h2, h3, h4, h5, h6 {
    color: var(--text-heading);
    font-weight: 700;
    line-height: 1.3;
    margin-top: 2em;
    margin-bottom: 0.5em;
    position: relative;
}

h1 { font-size: 28px; margin-top: 0; padding-bottom: 8px; border-bottom: 2px solid var(--border); }
h2 { font-size: 22px; padding-bottom: 6px; border-bottom: 1px solid var(--border); }
h3 { font-size: 18px; }
h4 { font-size: 16px; }
h5 { font-size: 15px; }
h6 { font-size: 14px; }

.anchor {
    color: var(--text-muted);
    text-decoration: none;
    font-weight: 400;
    margin-right: 6px;
    opacity: 0;
    transition: opacity var(--transition);
    font-size: 0.85em;
}

h1:hover .anchor, h2:hover .anchor, h3:hover .anchor,
h4:hover .anchor, h5:hover .anchor, h6:hover .anchor {
    opacity: 1;
}

.anchor:hover { color: var(--accent); }

p { margin-bottom: 1em; }

a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }

strong { font-weight: 600; }
em { font-style: italic; }

/* Inline code */
code {
    font-family: var(--font-mono);
    font-size: 0.88em;
    background: var(--bg-code);
    padding: 2px 6px;
    border-radius: 4px;
    color: var(--text-primary);
    word-break: break-word;
}

code.addr {
    color: var(--code-addr);
    font-weight: 500;
}

/* Named addresses: show symbol name, hide hex by default */
.named-addr .addr {
    display: none;
    margin-left: 3px;
    font-size: 0.85em;
    opacity: 0.6;
}

.named-addr .addr::before {
    content: "(";
}

.named-addr .addr::after {
    content: ")";
}

body.show-addresses .named-addr .addr {
    display: inline;
}

/* Ghidra references (FUN_/DAT_ patterns) - hidden by default */
.ghidra-ref {
    display: none;
    margin-left: 3px;
    font-size: 0.85em;
    opacity: 0.6;
    font-family: var(--font-mono);
}

body.show-addresses .ghidra-ref {
    display: inline;
}

/* Named addresses inside code blocks */
pre code .addr-name {
    background: none;
    padding: 0;
    border-radius: 0;
}

pre code .ghidra-ref {
    font-size: inherit;
}

.addr-name {
    font-family: var(--font-mono);
    font-size: 0.88em;
    background: var(--bg-code);
    padding: 2px 6px;
    border-radius: 4px;
    color: var(--code-addr);
    font-weight: 500;
    word-break: break-word;
}

/* Code blocks */
.code-block {
    position: relative;
    margin: 1em 0;
}

.code-block pre {
    background: var(--bg-code);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px;
    overflow-x: auto;
    line-height: 1.5;
}

.code-block pre code {
    background: none;
    padding: 0;
    font-size: 13px;
    color: var(--text-primary);
}

.copy-btn {
    position: absolute;
    top: 8px;
    right: 8px;
    background: var(--bg-tertiary);
    border: 1px solid var(--border);
    color: var(--text-muted);
    padding: 4px 10px;
    border-radius: 4px;
    font-size: 12px;
    cursor: pointer;
    opacity: 0;
    transition: all var(--transition);
    font-family: var(--font-sans);
}

.code-block:hover .copy-btn { opacity: 1; }
.copy-btn:hover { background: var(--bg-hover); color: var(--text-primary); }
.copy-btn.copied { color: var(--badge-verified); }

/* Tables */
.table-wrapper {
    overflow-x: auto;
    margin: 1em 0;
    border-radius: 8px;
    border: 1px solid var(--border);
}

table {
    width: 100%;
    border-collapse: collapse;
    font-size: 14px;
}

th {
    background: var(--bg-tertiary);
    font-weight: 600;
    text-align: left;
    padding: 10px 14px;
    border-bottom: 2px solid var(--border);
    white-space: nowrap;
}

td {
    padding: 8px 14px;
    border-bottom: 1px solid var(--border);
    vertical-align: top;
}

tbody tr:nth-child(even) { background: var(--table-stripe); }
tbody tr:hover { background: var(--bg-hover); }

/* Lists */
ul, ol {
    margin: 0.5em 0 1em;
    padding-left: 1.5em;
}

li {
    margin-bottom: 0.3em;
}

li input[type="checkbox"] {
    margin-right: 6px;
}

/* Badges */
.badge {
    display: inline-block;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    padding: 2px 8px;
    border-radius: 4px;
    font-family: var(--font-mono);
    white-space: nowrap;
    vertical-align: middle;
}

.badge-verified { color: var(--badge-verified); background: var(--badge-verified-bg); }
.badge-plausible { color: var(--badge-plausible); background: var(--badge-plausible-bg); }
.badge-speculative { color: var(--badge-speculative); background: var(--badge-speculative-bg); }
.badge-unknown { color: var(--badge-unknown); background: var(--badge-unknown-bg); }

/* Horizontal Rule */
hr {
    border: none;
    border-top: 1px solid var(--border);
    margin: 2em 0;
}

/* Page ToC */
.page-toc {
    width: var(--toc-width);
    flex-shrink: 0;
    position: sticky;
    top: 24px;
    align-self: flex-start;
    max-height: calc(100vh - 48px);
    overflow-y: auto;
}

.page-toc h3 {
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-muted);
    margin: 0 0 8px;
    border: none;
    padding: 0;
}

.page-toc ul {
    list-style: none;
    padding: 0;
    margin: 0;
}

.page-toc li {
    margin: 0;
}

.page-toc li a {
    display: block;
    padding: 3px 0 3px 12px;
    font-size: 12px;
    color: var(--text-muted);
    text-decoration: none;
    border-left: 2px solid var(--border);
    transition: all var(--transition);
    line-height: 1.4;
}

.page-toc li a:hover {
    color: var(--accent);
    border-left-color: var(--accent);
}

.page-toc li a.active {
    color: var(--accent);
    border-left-color: var(--accent);
    font-weight: 600;
}

.page-toc .toc-h3 a {
    padding-left: 24px;
    font-size: 11px;
}

/* Prev/Next Navigation */
.prev-next {
    display: flex;
    justify-content: space-between;
    margin-top: 3em;
    padding-top: 1.5em;
    border-top: 1px solid var(--border);
    gap: 16px;
}

.prev-next a {
    display: block;
    padding: 12px 16px;
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--text-secondary);
    text-decoration: none;
    font-size: 14px;
    transition: all var(--transition);
    max-width: 48%;
}

.prev-next a:hover {
    background: var(--bg-hover);
    color: var(--accent);
    border-color: var(--accent);
}

.prev-next .next { margin-left: auto; text-align: right; }

/* Scroll to Top */
.scroll-top {
    position: fixed;
    bottom: 24px;
    right: 24px;
    width: 40px;
    height: 40px;
    background: var(--bg-tertiary);
    border: 1px solid var(--border);
    color: var(--text-secondary);
    border-radius: 8px;
    font-size: 18px;
    cursor: pointer;
    display: none;
    align-items: center;
    justify-content: center;
    z-index: 80;
    transition: all var(--transition);
    box-shadow: var(--shadow);
}

.scroll-top.visible { display: flex; }
.scroll-top:hover { background: var(--bg-hover); color: var(--accent); }

/* Overlay for mobile sidebar */
.overlay {
    display: none;
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.5);
    z-index: 95;
}

.overlay.active { display: block; }

/* Responsive */
@media (max-width: 1200px) {
    .page-toc { display: none; }
    .content-body { display: block; }
}

@media (max-width: 768px) {
    .sidebar {
        transform: translateX(-100%);
        transition: transform 0.3s ease;
        width: 280px;
    }

    .sidebar.open { transform: translateX(0); }

    .mobile-header { display: flex; }

    .content {
        margin-left: 0;
        padding-top: 50px;
    }

    .content-wrapper {
        padding: 12px;
    }

    h1 { font-size: 20px; }
    h2 { font-size: 17px; }
    h3 { font-size: 15px; }
    h4 { font-size: 14px; }

    body { font-size: 14px; }

    .prev-next { flex-direction: column; }
    .prev-next a { max-width: 100%; }

    /* Named addresses on mobile */
    .addr-name {
        font-size: 0.82em;
        padding: 1px 4px;
        word-break: break-all;
    }

    .named-addr .addr {
        font-size: 0.78em;
    }

    /* Tables on mobile */
    .table-wrapper {
        -webkit-overflow-scrolling: touch;
        position: relative;
    }

    table {
        font-size: 12px;
    }

    th, td {
        padding: 6px 8px;
    }

    th {
        white-space: normal;
    }

    /* Code blocks on mobile */
    .code-block pre {
        padding: 12px;
        font-size: 12px;
    }

    .code-block pre code {
        font-size: 12px;
    }

    /* Inline code on mobile */
    code {
        font-size: 0.82em;
        padding: 1px 4px;
    }

    /* Touch-friendly targets */
    .sidebar-toggle button {
        min-height: 44px;
    }

    .nav-item {
        min-height: 44px;
        padding: 10px 16px;
    }

    /* Disclaimer compact */
    .disclaimer {
        font-size: 12px;
        padding: 10px 12px;
    }

    /* Collapsible sections on mobile */
    details.collapsible summary {
        padding: 8px 8px 8px 12px;
    }

    details.collapsible .collapsible-content {
        padding: 0 0 0.5em 8px;
    }

    /* Scroll top button - larger touch target */
    .scroll-top {
        width: 44px;
        height: 44px;
        bottom: 16px;
        right: 16px;
    }
}

/* Extra small screens */
@media (max-width: 400px) {
    .content-wrapper {
        padding: 8px;
    }

    h1 { font-size: 18px; }
    h2 { font-size: 16px; }

    table { font-size: 11px; }
    th, td { padding: 4px 6px; }

    .addr-name {
        font-size: 0.78em;
    }
}

/* Collapsible sections */
details.collapsible {
    margin: 0.5em 0;
    border-left: 3px solid var(--text-muted);
    border-radius: 2px;
    transition: border-color var(--transition);
}

details.collapsible[open] {
    border-left-color: var(--accent);
}

details.collapsible summary {
    cursor: pointer;
    list-style: none;
    padding: 4px 8px 4px 12px;
    margin-left: -3px;
    border-radius: 4px;
    transition: background var(--transition), color var(--transition);
    display: flex;
    align-items: center;
    gap: 8px;
    user-select: none;
}

details.collapsible summary::-webkit-details-marker {
    display: none;
}

details.collapsible summary::before {
    content: "\\25B6";
    font-size: 0.7em;
    color: var(--text-muted);
    transition: transform 0.2s ease, color 0.2s ease;
    flex-shrink: 0;
    display: inline-block;
    width: 1em;
    text-align: center;
}

details.collapsible[open] > summary::before {
    transform: rotate(90deg);
    color: var(--accent);
}

details.collapsible summary:hover {
    background: var(--bg-hover);
}

details.collapsible summary h2,
details.collapsible summary h3 {
    margin: 0;
    padding: 0;
    border: none;
    display: inline;
    font-size: inherit;
}

details.collapsible summary h2 {
    font-size: 22px;
}

details.collapsible summary h3 {
    font-size: 18px;
}

details.collapsible .collapsible-content {
    padding: 0 0 0.5em 12px;
    animation: collapsible-fade-in 0.25s ease;
}

@keyframes collapsible-fade-in {
    from { opacity: 0; transform: translateY(-4px); }
    to { opacity: 1; transform: translateY(0); }
}

/* Sidebar tech toggle button */
.sidebar-toggle {
    padding: 4px 16px 8px;
}

.tech-toggle {
    width: 100%;
    padding: 7px 12px;
    background: var(--bg-tertiary);
    border: 1px solid var(--border);
    border-radius: 6px;
    color: var(--text-secondary);
    font-size: 12px;
    font-family: var(--font-sans);
    cursor: pointer;
    transition: all var(--transition);
    display: flex;
    align-items: center;
    gap: 6px;
}

.tech-toggle:hover {
    background: var(--bg-hover);
    color: var(--text-primary);
    border-color: var(--accent);
}

.tech-toggle .toggle-icon {
    font-size: 10px;
    transition: transform 0.2s ease;
}

.tech-toggle.collapsed .toggle-icon {
    transform: rotate(-90deg);
}

/* Print styles */
@media print {
    .sidebar, .mobile-header, .scroll-top, .copy-btn, .page-toc, .prev-next, .sidebar-toggle { display: none !important; }
    .content { margin-left: 0 !important; }
    body { color: #000; background: #fff; }
    details.collapsible { border-left: none; }
    details.collapsible[open] { border-left: none; }
    details.collapsible > summary { display: none; }
    details.collapsible .collapsible-content { padding-left: 0; }
}
'''

def build_js():
    """Build the JavaScript file."""
    return '''// ========================================
// Trackmania 2020 Engine Reference - Script
// ========================================

(function() {
    "use strict";

    // Theme management
    const THEME_KEY = "tm2020-docs-theme";

    function getPreferredTheme() {
        const stored = localStorage.getItem(THEME_KEY);
        if (stored) return stored;
        return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
    }

    function setTheme(theme) {
        document.documentElement.setAttribute("data-theme", theme);
        localStorage.setItem(THEME_KEY, theme);
        // Swap highlight.js theme
        const link = document.getElementById("hljs-theme");
        if (link) {
            link.href = theme === "light"
                ? "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/atom-one-light.min.css"
                : "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/atom-one-dark.min.css";
        }
    }

    function toggleTheme() {
        const current = document.documentElement.getAttribute("data-theme");
        setTheme(current === "dark" ? "light" : "dark");
    }

    // Initialize theme
    setTheme(getPreferredTheme());

    document.addEventListener("DOMContentLoaded", function() {
        // Theme toggle buttons
        var btns = document.querySelectorAll("#theme-toggle, #theme-toggle-mobile");
        btns.forEach(function(btn) {
            btn.addEventListener("click", toggleTheme);
        });

        // Mobile sidebar
        var menuToggle = document.getElementById("menu-toggle");
        var sidebar = document.getElementById("sidebar");
        var overlay = document.getElementById("overlay");

        if (menuToggle) {
            menuToggle.addEventListener("click", function() {
                sidebar.classList.toggle("open");
                overlay.classList.toggle("active");
            });
        }

        if (overlay) {
            overlay.addEventListener("click", function() {
                sidebar.classList.remove("open");
                overlay.classList.remove("active");
            });
        }

        // Code copy buttons
        document.querySelectorAll(".copy-btn").forEach(function(btn) {
            btn.addEventListener("click", function() {
                var code = btn.parentElement.querySelector("code");
                if (code) {
                    navigator.clipboard.writeText(code.textContent).then(function() {
                        btn.textContent = "Copied!";
                        btn.classList.add("copied");
                        setTimeout(function() {
                            btn.textContent = "Copy";
                            btn.classList.remove("copied");
                        }, 2000);
                    });
                }
            });
        });

        // Syntax highlighting
        if (typeof hljs !== "undefined") {
            document.querySelectorAll("pre code").forEach(function(block) {
                hljs.highlightElement(block);
            });
        }

        // Post-process code blocks: replace FUN_/DAT_ with named addresses
        var addrMap = window.TM_ADDRESS_MAP || {};
        function lookupAddr(hex) {
            var addr = "0x" + hex.toLowerCase();
            return addrMap[addr] || null;
        }

        document.querySelectorAll("pre code").forEach(function(block) {
            var html = block.innerHTML;
            var changed = false;

            // Pass 1: (FUN_XXX @ 0xXXX) - hide entire parenthetical
            var r1 = html.replace(/\\s*\\([^)]*?FUN_[0-9a-fA-F]{6,16}[^)]*?@[^)]*?0x[0-9a-fA-F]{6,16}[^)]*?\\)/g,
                function(match) { return '<span class="ghidra-ref">' + match + '</span>'; }
            );
            if (r1 !== html) { html = r1; changed = true; }

            // Pass 2: (FUN_XXX) without @ - hide parenthetical
            var r2 = html.replace(/\\s*\\([^)]*?FUN_[0-9a-fA-F]{6,16}[^)]*?\\)/g,
                function(match) {
                    if (match.indexOf('ghidra-ref') !== -1) return match;
                    return '<span class="ghidra-ref">' + match + '</span>';
                }
            );
            if (r2 !== html) { html = r2; changed = true; }

            // Pass 3: bare FUN_XXX
            var r3 = html.replace(/FUN_([0-9a-fA-F]{6,16})/g,
                function(match, hex, offset) {
                    var before = html.substring(Math.max(0, offset - 200), offset);
                    if (before.lastIndexOf('ghidra-ref') > before.lastIndexOf('</span>')) return match;
                    var name = lookupAddr(hex);
                    if (name) {
                        return '<span class="named-addr"><span class="addr-name">' +
                               name + '</span><span class="ghidra-ref">' +
                               match + '</span></span>';
                    }
                    return match;
                }
            );
            if (r3 !== html) { html = r3; changed = true; }

            // Pass 4: DAT_XXX
            var r4 = html.replace(/DAT_([0-9a-fA-F]{6,16})/g,
                function(match, hex, offset) {
                    var before = html.substring(Math.max(0, offset - 200), offset);
                    if (before.lastIndexOf('ghidra-ref') > before.lastIndexOf('</span>')) return match;
                    var name = lookupAddr(hex);
                    if (name) {
                        return '<span class="named-addr"><span class="addr-name">' +
                               name + '</span><span class="ghidra-ref">' +
                               match + '</span></span>';
                    }
                    return match;
                }
            );
            if (r4 !== html) { html = r4; changed = true; }

            if (changed) block.innerHTML = html;
        });

        // Technical details toggle
        var TECH_TOGGLE_KEY = "tm2020-docs-tech-hidden";
        var techToggleBtn = document.getElementById("tech-toggle");
        var collapsibleSections = document.querySelectorAll("details.collapsed-by-default");

        function setTechSectionsState(hidden) {
            collapsibleSections.forEach(function(el) {
                if (hidden) {
                    el.removeAttribute("open");
                } else {
                    el.setAttribute("open", "");
                }
            });
            if (techToggleBtn) {
                var icon = techToggleBtn.querySelector(".toggle-icon");
                if (hidden) {
                    techToggleBtn.classList.add("collapsed");
                    icon.innerHTML = "&#9654;";
                    techToggleBtn.childNodes[techToggleBtn.childNodes.length - 1].textContent = " Show Technical Details";
                } else {
                    techToggleBtn.classList.remove("collapsed");
                    icon.innerHTML = "&#9660;";
                    techToggleBtn.childNodes[techToggleBtn.childNodes.length - 1].textContent = " Hide Technical Details";
                }
            }
            localStorage.setItem(TECH_TOGGLE_KEY, hidden ? "1" : "0");
        }

        // Initialize: default is hidden (collapsed), respect stored preference
        var techHidden = localStorage.getItem(TECH_TOGGLE_KEY);
        if (techHidden === null) {
            // Default: collapsed (hidden)
            setTechSectionsState(true);
        } else {
            setTechSectionsState(techHidden === "1");
        }

        if (techToggleBtn) {
            techToggleBtn.addEventListener("click", function() {
                var isCurrentlyHidden = techToggleBtn.classList.contains("collapsed");
                setTechSectionsState(!isCurrentlyHidden);
            });
        }

        // Address toggle (show/hide hex addresses alongside symbol names)
        var ADDR_TOGGLE_KEY = "tm2020-docs-addr-visible";
        var addrToggleBtn = document.getElementById("addr-toggle");

        function setAddrState(visible) {
            if (visible) {
                document.body.classList.add("show-addresses");
            } else {
                document.body.classList.remove("show-addresses");
            }
            if (addrToggleBtn) {
                var icon = addrToggleBtn.querySelector(".toggle-icon");
                if (visible) {
                    addrToggleBtn.classList.remove("collapsed");
                    icon.innerHTML = "&#9660;";
                    addrToggleBtn.childNodes[addrToggleBtn.childNodes.length - 1].textContent = " Hide Hex Addresses";
                } else {
                    addrToggleBtn.classList.add("collapsed");
                    icon.innerHTML = "&#9654;";
                    addrToggleBtn.childNodes[addrToggleBtn.childNodes.length - 1].textContent = " Show Hex Addresses";
                }
            }
            localStorage.setItem(ADDR_TOGGLE_KEY, visible ? "1" : "0");
        }

        // Initialize: default is hidden (only names shown)
        var addrVisible = localStorage.getItem(ADDR_TOGGLE_KEY);
        if (addrVisible === null) {
            setAddrState(false);
        } else {
            setAddrState(addrVisible === "1");
        }

        if (addrToggleBtn) {
            addrToggleBtn.addEventListener("click", function() {
                var isCurrentlyVisible = document.body.classList.contains("show-addresses");
                setAddrState(!isCurrentlyVisible);
            });
        }

        // Scroll to top button
        var scrollTopBtn = document.getElementById("scroll-top");
        var content = document.getElementById("content");

        function checkScroll() {
            if (window.scrollY > 400) {
                scrollTopBtn.classList.add("visible");
            } else {
                scrollTopBtn.classList.remove("visible");
            }
        }

        window.addEventListener("scroll", checkScroll);
        checkScroll();

        if (scrollTopBtn) {
            scrollTopBtn.addEventListener("click", function() {
                window.scrollTo({ top: 0, behavior: "smooth" });
            });
        }

        // ToC active highlighting + auto-open collapsed sections on click
        var tocLinks = document.querySelectorAll(".page-toc a");
        var headings = [];

        tocLinks.forEach(function(link) {
            var id = link.getAttribute("href");
            if (id && id.startsWith("#")) {
                var el = document.getElementById(id.slice(1));
                if (el) headings.push({ el: el, link: link });
            }

            // When clicking a ToC link, open any collapsed parent <details>
            link.addEventListener("click", function() {
                var targetId = link.getAttribute("href");
                if (targetId && targetId.startsWith("#")) {
                    var target = document.getElementById(targetId.slice(1));
                    if (target) {
                        var parent = target.closest("details.collapsible");
                        if (parent && !parent.hasAttribute("open")) {
                            parent.setAttribute("open", "");
                        }
                        // Also check if the heading is inside a summary
                        var summaryParent = target.closest("summary");
                        if (summaryParent) {
                            var detailsEl = summaryParent.closest("details.collapsible");
                            if (detailsEl && !detailsEl.hasAttribute("open")) {
                                detailsEl.setAttribute("open", "");
                            }
                        }
                    }
                }
            });
        });

        function updateActiveToc() {
            var scrollPos = window.scrollY + 100;
            var active = null;

            for (var i = headings.length - 1; i >= 0; i--) {
                if (headings[i].el.offsetTop <= scrollPos) {
                    active = headings[i];
                    break;
                }
            }

            tocLinks.forEach(function(link) { link.classList.remove("active"); });
            if (active) active.link.classList.add("active");
        }

        if (headings.length > 0) {
            window.addEventListener("scroll", updateActiveToc);
            updateActiveToc();
        }

        // Search functionality
        var searchInput = document.getElementById("search-input");
        var searchResults = document.getElementById("search-results");

        // Build search index from page content
        var searchIndex = [];

        // Index all headings on the current page
        document.querySelectorAll("h1, h2, h3, h4").forEach(function(h) {
            searchIndex.push({
                text: h.textContent.replace(/^#\\s*/, ""),
                id: h.id,
                page: "",
                type: "heading"
            });
        });

        // Static cross-page search data
        var pages = [
            { file: "index.html", title: "Overview", keywords: "master overview executive summary binary protection engine architecture class system subsystem map critical addresses open questions" },
            { file: "binary.html", title: "Binary Analysis", keywords: "PE header sections imports exports entry point TLS callbacks packer protector DLL function statistics string statistics" },
            { file: "class-hierarchy.html", title: "Class System", keywords: "CMwNod class hierarchy RTTI MwClassId CGame CPlug CWebServices CNet CScene CHms CControl CSystem namespace vtable" },
            { file: "physics.html", title: "Physics & Vehicle", keywords: "NSceneDyna NSceneVehiclePhy NHmsCollision physics simulation vehicle wheel suspension turbo boost gravity collision friction surface" },
            { file: "rendering.html", title: "Rendering & Graphics", keywords: "D3D11 deferred shading G-buffer HBAO bloom shadows particles volumetric fog SSR PBR lightmap shader HLSL Tech3" },
            { file: "architecture.html", title: "Architecture", keywords: "entry point WinMain CGbxApp game loop state machine CGameCtnApp fiber coroutine ManiaScript profiling initialization" },
            { file: "file-formats.html", title: "File Formats", keywords: "GBX GameBox header chunk serialization CClassicArchive class ID map loading pack Fid CSystemArchiveNod FACADE01" },
            { file: "networking.html", title: "Networking", keywords: "Winsock libcurl OpenSSL HTTP QUIC TCP UDP Ubisoft Connect Nadeo Services authentication API XMPP Vivox XML-RPC" },
            { file: "game-files.html", title: "Game Files", keywords: "DLL materials packs game files analysis Stadium items vehicles textures sounds" },
            { file: "tmnf-crossref.html", title: "TMNF Comparison", keywords: "TrackMania Nations Forever TMNF cross-reference comparison evolution changes" },
        ];

        if (searchInput) {
            searchInput.addEventListener("input", function() {
                var query = searchInput.value.toLowerCase().trim();
                searchResults.innerHTML = "";

                if (query.length < 2) {
                    searchResults.classList.remove("active");
                    return;
                }

                var results = [];

                // Search current page headings
                searchIndex.forEach(function(item) {
                    if (item.text.toLowerCase().includes(query)) {
                        results.push({
                            text: item.text,
                            url: "#" + item.id,
                            page: "(this page)"
                        });
                    }
                });

                // Search cross-page
                pages.forEach(function(page) {
                    if (page.title.toLowerCase().includes(query) ||
                        page.keywords.toLowerCase().includes(query)) {
                        results.push({
                            text: page.title,
                            url: page.file,
                            page: page.file
                        });
                    }
                });

                if (results.length === 0) {
                    searchResults.classList.remove("active");
                    return;
                }

                // Limit results
                results = results.slice(0, 15);

                results.forEach(function(r) {
                    var a = document.createElement("a");
                    a.className = "search-result-item";
                    a.href = r.url;
                    a.innerHTML = r.text + \' <span class="result-page">\' + r.page + "</span>";
                    searchResults.appendChild(a);
                });

                searchResults.classList.add("active");
            });

            // Close search on click outside
            document.addEventListener("click", function(e) {
                if (!searchInput.contains(e.target) && !searchResults.contains(e.target)) {
                    searchResults.classList.remove("active");
                }
            });

            // Close search on Escape
            searchInput.addEventListener("keydown", function(e) {
                if (e.key === "Escape") {
                    searchResults.classList.remove("active");
                    searchInput.blur();
                }
            });
        }
    });
})();
'''

def main():
    os.makedirs(SITE_DIR, exist_ok=True)

    # Build each page (skip section separators)
    for page_def in PAGES:
        filename = page_def[0]
        if filename is None or filename == 'sub:':
            continue
        print(f"Building {filename}...")
        html = build_page(page_def)
        output_path = os.path.join(SITE_DIR, filename)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)

    # Build CSS
    print("Building style.css...")
    css = build_css()
    with open(os.path.join(SITE_DIR, 'style.css'), 'w', encoding='utf-8') as f:
        f.write(css)

    # Build address map JS (for client-side code block processing)
    print("Building address_map.js...")
    with open(os.path.join(SITE_DIR, 'address_map.js'), 'w', encoding='utf-8') as f:
        f.write('// Auto-generated address name mapping for client-side code block processing\n')
        f.write('window.TM_ADDRESS_MAP = ')
        json.dump(ADDRESS_NAMES, f)
        f.write(';\n')

    # Build JS
    print("Building script.js...")
    js = build_js()
    with open(os.path.join(SITE_DIR, 'script.js'), 'w', encoding='utf-8') as f:
        f.write(js)

    print("\nDone! Site built in:", SITE_DIR)

    # Print file sizes
    for entry in sorted(os.listdir(SITE_DIR)):
        if entry == 'build.py':
            continue
        path = os.path.join(SITE_DIR, entry)
        if os.path.isfile(path):
            size = os.path.getsize(path)
            if size > 1024 * 1024:
                print(f"  {entry}: {size / (1024*1024):.1f} MB")
            elif size > 1024:
                print(f"  {entry}: {size / 1024:.1f} KB")
            else:
                print(f"  {entry}: {size} B")

if __name__ == '__main__':
    main()
