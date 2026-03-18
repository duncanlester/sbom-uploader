#!/usr/bin/env python3
"""
SBOM Component Report generator.

Usage:
    generate_sbom_report.py <report_title>

Data sources (checked in order):
    boms/  — directory of CycloneDX JSON files, one per project (multi-project mode)
    bom.json — single CycloneDX JSON file (single-project mode)

Output:
    sbom-component-report.pdf
"""
import json
import sys
import os
from math import ceil
from fpdf import FPDF
from datetime import datetime


def sanitize_text(text):
    if not text:
        return ""
    replacements = {
        '\u202f': ' ', '\u2019': "'", '\u2018': "'",
        '\u201c': '"', '\u201d': '"', '\u2013': '-',
        '\u2014': '-', '\u2022': '*', '\u00a0': ' ',
    }
    for u, a in replacements.items():
        text = text.replace(u, a)
    return text.encode('latin-1', errors='ignore').decode('latin-1')


def extract_licenses(component):
    licenses = []
    for lic in component.get('licenses', []):
        if 'license' in lic:
            name = lic['license'].get('name') or lic['license'].get('id', '')
            if name:
                licenses.append(name)
        elif 'expression' in lic:
            licenses.append(lic['expression'])
    return ', '.join(licenses) if licenses else ''


def load_boms():
    """Return list of (label, components_list) tuples."""
    projects = []
    boms_dir = 'boms'
    if os.path.isdir(boms_dir):
        for fname in sorted(os.listdir(boms_dir)):
            if not fname.endswith('.json'):
                continue
            with open(os.path.join(boms_dir, fname)) as f:
                bom = json.load(f)
            meta  = bom.get('metadata', {}).get('component', {})
            name  = sanitize_text(meta.get('name') or fname[:-5])
            ver   = sanitize_text(meta.get('version', ''))
            label = f"{name} {ver}".strip()
            projects.append((label, bom.get('components', [])))
    # Fall back to single bom.json whether or not boms/ existed (may have been empty)
    if not projects and os.path.isfile('bom.json'):
        with open('bom.json') as f:
            bom = json.load(f)
        meta  = bom.get('metadata', {}).get('component', {})
        name  = sanitize_text(meta.get('name', 'Unknown'))
        ver   = sanitize_text(meta.get('version', ''))
        label = f"{name} {ver}".strip()
        projects.append((label, bom.get('components', [])))
    return projects


def main(report_title):
    projects = load_boms()
    if not projects:
        print("No BOM files found (expected boms/ directory or bom.json)")
        sys.exit(1)

    multi = len(projects) > 1
    col_names = ['Component', 'Version', 'Type', 'PURL', 'Licenses']

    # Build row values per project
    for proj_label, comps in projects:
        for comp in comps:
            comp['_row'] = [
                sanitize_text(comp.get('name', 'N/A')),
                sanitize_text(str(comp.get('version') or '')),
                sanitize_text(comp.get('type', '').capitalize()),
                sanitize_text(comp.get('purl', '')),
                sanitize_text(extract_licenses(comp)),
            ]

    total_components = sum(len(comps) for _, comps in projects)
    type_counts = {}
    for _, comps in projects:
        for comp in comps:
            t = comp.get('type', 'unknown').capitalize()
            type_counts[t] = type_counts.get(t, 0) + 1

    HDR_COLOR = (15, 82, 112)

    class SBOMReport(FPDF):
        def header(self):
            self.set_fill_color(15, 82, 112)
            self.rect(0, 0, self.w, 45, 'F')
            self.set_text_color(255, 255, 255)
            self.set_font("Helvetica", "B", 28)
            self.set_y(12)
            self.cell(0, 12, "SBOM Component Report", align="C", ln=True)
            self.set_font("Helvetica", "", 11)
            self.set_text_color(178, 216, 230)
            self.cell(0, 8, sanitize_text(report_title), align="C")
            self.set_y(50)

        def footer(self):
            self.set_y(-15)
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(148, 163, 184)
            self.set_draw_color(226, 232, 240)
            self.line(10, self.get_y() - 3, self.w - 10, self.get_y() - 3)
            self.cell(0, 10,
                      f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} | Page {self.page_no()}",
                      align="C")

    pdf = SBOMReport(orientation='L', format='A4')
    pdf.set_top_margin(50)
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=25)

    # ── Summary section ──────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(0, 10, "Summary", ln=True)
    pdf.ln(3)

    box_w = 55
    box_h = 26
    top_types = [("Total Components", total_components, HDR_COLOR)] + [
        (t, c, (30, 120, 160))
        for t, c in sorted(type_counts.items(), key=lambda x: -x[1])[:5]
    ]
    base_y = pdf.get_y()
    for idx, (label, count, color) in enumerate(top_types):
        x = 12 + idx * (box_w + 2)
        pdf.set_fill_color(248, 250, 252)
        pdf.rect(x, base_y, box_w, box_h, 'F')
        pdf.set_fill_color(*color)
        pdf.rect(x, base_y, 3, box_h, 'F')
        pdf.set_xy(x + 5, base_y + 3)
        pdf.set_font("Helvetica", "B", 20)
        pdf.set_text_color(*color)
        pdf.cell(box_w - 8, 10, str(count), align="C")
        pdf.set_xy(x + 5, base_y + 14)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(71, 85, 105)
        pdf.cell(box_w - 8, 6, label, align="C")

    pdf.set_y(base_y + box_h + 8)

    if multi:
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(30, 41, 59)
        pdf.cell(0, 7, f"Projects included: {len(projects)}", ln=True)
        for proj_label, comps in projects:
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(71, 85, 105)
            pdf.cell(0, 5, f"  {proj_label}  ({len(comps)} components)", ln=True)
        pdf.ln(5)

    # ── Compute column widths from actual content ─────────────────────────────
    USABLE_W = 277.0
    MIN_COL  = 14.0
    CAP_COL  = 72.0
    PADDING  = 4.0

    pdf.set_font("Helvetica", "B", 7)
    col_raw = [pdf.get_string_width(name) + PADDING for name in col_names]

    pdf.set_font("Helvetica", "", 7)
    for _, comps in projects:
        for comp in comps:
            for i, val in enumerate(comp.get('_row', [])):
                w = min(pdf.get_string_width(val) + PADDING, CAP_COL)
                if w > col_raw[i]:
                    col_raw[i] = w

    col_raw = [max(MIN_COL, w) for w in col_raw]
    total_raw = sum(col_raw)
    col_widths = [round(w * USABLE_W / total_raw, 2) for w in col_raw]
    col_widths[-1] = round(USABLE_W - sum(col_widths[:-1]), 2)
    cols = list(zip(col_names, col_widths))

    # ── Row rendering helpers ─────────────────────────────────────────────────
    def draw_table_header():
        pdf.set_fill_color(*HDR_COLOR)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 7)
        for col_name, col_w in cols:
            pdf.cell(col_w, 7, col_name, 1, 0, "C", True)
        pdf.ln()

    def render_data_row(row_vals, fill_color):
        pdf.set_font("Helvetica", "", 7)
        y_start = pdf.get_y()
        line_h  = 5

        max_lines = 1
        for (_, col_w), val in zip(cols, row_vals):
            if val:
                lines = max(1, ceil(pdf.get_string_width(val) / max(1, col_w - 2)))
                max_lines = max(max_lines, lines)
        row_h = max_lines * line_h

        if pdf.will_page_break(row_h):
            pdf.add_page()
            pdf.set_font("Helvetica", "", 7)
            y_start = pdf.get_y()

        # Fill background then draw cell borders
        pdf.set_fill_color(*fill_color)
        pdf.set_draw_color(180, 195, 210)
        x_cursor = pdf.l_margin
        for (_, col_w), _ in zip(cols, row_vals):
            pdf.rect(x_cursor, y_start, col_w, row_h, 'FD')
            x_cursor += col_w

        # Render text
        pdf.set_text_color(51, 65, 85)
        x_cursor = pdf.l_margin
        for (_, col_w), val in zip(cols, row_vals):
            pdf.set_xy(x_cursor + 1, y_start + 0.5)
            pdf.multi_cell(col_w - 2, line_h, val, border=0, align="L")
            x_cursor += col_w

        pdf.set_y(y_start + row_h)

    ROW_COLORS = [(245, 249, 252), (255, 255, 255)]

    # ── Component tables — one section per project ────────────────────────────
    for proj_label, comps in projects:
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(*HDR_COLOR)
        pdf.cell(0, 9, f"{proj_label}  ({len(comps)} components)", ln=True)
        pdf.ln(1)

        if not comps:
            pdf.set_font("Helvetica", "I", 9)
            pdf.set_text_color(100, 116, 139)
            pdf.cell(0, 7, "No components found in this BOM.", ln=True)
            pdf.ln(4)
            continue

        draw_table_header()
        for i, comp in enumerate(comps):
            render_data_row(comp.get('_row', []), ROW_COLORS[i % 2])

        pdf.ln(8)

    pdf.output("sbom-component-report.pdf")
    print("SBOM component report generated successfully")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: generate_sbom_report.py <report_title>")
        sys.exit(1)
    main(sys.argv[1])
