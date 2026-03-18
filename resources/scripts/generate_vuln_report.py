#!/usr/bin/env python3
import json
import sys
import os
import urllib.request
import urllib.parse
from math import ceil
from fpdf import FPDF
from datetime import datetime

def sanitize_text(text):
    """Remove non-Latin-1 characters from text to avoid fpdf encoding errors"""
    if not text:
        return ""
    # Replace common Unicode characters with ASCII equivalents
    replacements = {
        '\u202f': ' ',  # Narrow no-break space -> regular space
        '\u2019': "'",  # Right single quotation mark -> apostrophe
        '\u2018': "'",  # Left single quotation mark -> apostrophe
        '\u201c': '"',  # Left double quotation mark
        '\u201d': '"',  # Right double quotation mark
        '\u2013': '-',  # En dash -> hyphen
        '\u2014': '-',  # Em dash -> hyphen
        '\u2022': '*',  # Bullet -> asterisk
        '\u00a0': ' ',  # Non-breaking space -> regular space
    }
    for unicode_char, ascii_char in replacements.items():
        text = text.replace(unicode_char, ascii_char)

    # Remove any remaining non-Latin-1 characters
    return text.encode('latin-1', errors='ignore').decode('latin-1')

def fetch_analysis(api_url, api_key, project_uuid, component_uuid, vuln_uuid):
    """Fetch full analysis record from Dependency-Track for a single finding."""
    if not all([api_url, api_key, project_uuid, component_uuid, vuln_uuid]):
        return {}
    try:
        params = urllib.parse.urlencode({
            'project':       project_uuid,
            'component':     component_uuid,
            'vulnerability': vuln_uuid,
        })
        req = urllib.request.Request(
            f"{api_url}/api/v1/analysis?{params}",
            headers={'X-Api-Key': api_key, 'accept': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return {}

def main(project_name, project_version):
    api_url = os.environ.get('DT_API_URL', '')
    api_key = os.environ.get('DT_API_KEY', '')

    with open("metrics.json") as f:
        metrics = json.load(f)
    with open("findings.json") as f:
        findings = json.load(f)

    # Enrich each finding with its full analysis record
    for finding in findings:
        finding['_analysis'] = fetch_analysis(
            api_url, api_key,
            finding.get('projectUuid', ''),
            finding.get('component', {}).get('uuid', ''),
            finding.get('vulnerability', {}).get('uuid', ''),
        )

    has_source_col = any(f.get("sourceName") for f in findings)

    PAGE_W = 297  # A4 landscape width in mm

    class VulnPDF(FPDF):
        def header(self):
            self.set_fill_color(30, 58, 138)
            self.rect(0, 0, self.w, 45, 'F')
            self.set_text_color(255, 255, 255)
            self.set_font("Helvetica", "B", 32)
            self.set_y(15)
            self.cell(0, 12, "Security Analysis Report", align="C", ln=True)
            self.set_font("Helvetica", "", 11)
            self.set_text_color(203, 213, 225)
            self.cell(0, 8, f"{project_name} {project_version}", align="C")
            self.set_y(50)

        def footer(self):
            self.set_y(-15)
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(148, 163, 184)
            self.set_draw_color(226, 232, 240)
            self.line(10, self.get_y() - 3, self.w - 10, self.get_y() - 3)
            self.cell(0, 10, f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} | Page {self.page_no()}", align="C")

    # Create PDF — landscape A4
    pdf = VulnPDF(orientation='L', format='A4')
    pdf.set_top_margin(50)
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=25)

    critical = metrics.get("critical", 0)
    high = metrics.get("high", 0)
    medium = metrics.get("medium", 0)
    low = metrics.get("low", 0)

    # Risk assessment box
    risk_level = "CRITICAL" if critical > 0 else "HIGH" if high > 5 else "MODERATE" if high > 0 or medium > 10 else "LOW"
    risk_colors = {
        "CRITICAL": (220, 38, 38),
        "HIGH": (234, 88, 12),
        "MODERATE": (250, 204, 21),
        "LOW": (34, 197, 94)
    }
    risk_color = risk_colors[risk_level]

    # Vulnerabilities heading
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(0, 10, "Vulnerabilities", ln=True)
    pdf.ln(5)

    # Metrics grid — 4 boxes in a row
    box_width = 60
    box_height = 28
    start_x = 12

    severity_metrics = [
        ("CRITICAL", critical, (220, 38, 38)),
        ("HIGH", high, (234, 88, 12)),
        ("MEDIUM", medium, (250, 204, 21)),
        ("LOW", low, (34, 197, 94))
    ]

    base_y = pdf.get_y()

    for idx, (label, count, color) in enumerate(severity_metrics):
        x_pos = start_x + (idx * (box_width + 2))
        pdf.set_fill_color(248, 250, 252)
        pdf.rect(x_pos, base_y, box_width, box_height, 'F')
        pdf.set_fill_color(*color)
        pdf.rect(x_pos, base_y, 3, box_height, 'F')
        pdf.set_xy(x_pos + 5, base_y + 5)
        pdf.set_font("Helvetica", "B", 24)
        pdf.set_text_color(*color)
        pdf.cell(box_width - 10, 10, str(count), align="C")
        pdf.set_xy(x_pos + 5, base_y + 14)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(71, 85, 105)
        pdf.cell(box_width - 10, 6, label, align="C")

    pdf.set_y(base_y + box_height + 10)

    # Group and sort findings by severity then CVSS
    vulns_by_severity = {"CRITICAL": [], "HIGH": [], "MEDIUM": [], "LOW": []}
    for vuln in findings:
        sev = vuln.get("vulnerability", {}).get("severity", "")
        if sev in vulns_by_severity:
            vulns_by_severity[sev].append(vuln)

    for sev in vulns_by_severity:
        vulns_by_severity[sev].sort(
            key=lambda x: (
                x.get("vulnerability", {}).get("cvssV3BaseScore") or
                x.get("vulnerability", {}).get("cvssV2BaseScore") or 0
            ),
            reverse=True
        )

    severity_configs = [
        ("CRITICAL", (220, 38, 38)),
        ("HIGH",     (234, 88, 12)),
        ("MEDIUM",   (250, 204, 21)),
        ("LOW",      (34, 197, 94)),
    ]

    # Pre-build all row values so we can measure content widths before drawing
    for finding in findings:
        v = finding.get("vulnerability", {})
        c = finding.get("component", {})
        a = finding.get("_analysis", {})

        vuln_id      = sanitize_text(v.get("vulnId", "N/A"))
        comp_name    = sanitize_text(c.get("name", ""))
        version      = sanitize_text(str(c.get("version") or ""))
        comp_version = f"{comp_name} {version}".strip() if version else comp_name or "N/A"
        score        = str(v.get("cvssV3BaseScore") or v.get("cvssV2BaseScore") or "N/A")
        suppressed   = a.get("isSuppressed", False)
        state_raw    = (a.get("analysisState") or "").replace("_", " ")
        state        = sanitize_text(f"[SUPPRESSED] {state_raw}".strip() if suppressed and state_raw else
                                     "[SUPPRESSED]" if suppressed else state_raw)
        justif       = sanitize_text((a.get("analysisJustification") or "").replace("_", " "))
        response     = sanitize_text((a.get("analysisResponse")      or "").replace("_", " "))

        last_comment = (a.get("analysisComments") or [{}])[-1]
        comment_text = sanitize_text(last_comment.get("comment", ""))
        raw_ts       = last_comment.get("timestamp")
        if isinstance(raw_ts, (int, float)):
            comment_time = datetime.fromtimestamp(raw_ts / 1000).strftime('%Y-%m-%d %H:%M')
        elif isinstance(raw_ts, str) and raw_ts:
            comment_time = raw_ts[:16].replace("T", " ")
        else:
            comment_time = ""
        commenter = sanitize_text(last_comment.get("commenter", ""))

        if has_source_col:
            finding['_row_vals'] = [
                vuln_id, sanitize_text(finding.get("sourceName", "")),
                comp_version, score,
                state, justif, response,
                comment_text, comment_time, commenter,
            ]
        else:
            finding['_row_vals'] = [
                vuln_id, comp_version, score,
                state, justif, response,
                comment_text, comment_time, commenter,
            ]

    # Column header names
    if has_source_col:
        col_names = ["Vulnerability ID", "Project", "Component Version", "CVSS Score",
                     "Analysis State", "Analysis Justification", "Analysis Response",
                     "Analysis Comments", "Time of Comment", "Commenter"]
    else:
        col_names = ["Vulnerability ID", "Component Version", "CVSS Score",
                     "Analysis State", "Analysis Justification", "Analysis Response",
                     "Analysis Comments", "Time of Comment", "Commenter"]

    # Measure widest content per column across headers + all data rows
    # Cap each cell's contribution so one very long value can't monopolise a column
    USABLE_W = 277.0
    MIN_COL  = 14.0
    CAP_COL  = 65.0
    PADDING  = 4.0

    pdf.set_font("Helvetica", "B", 7)
    col_raw = [pdf.get_string_width(name) + PADDING for name in col_names]

    pdf.set_font("Helvetica", "", 7)
    for finding in findings:
        for i, val in enumerate(finding.get('_row_vals', [])):
            w = min(pdf.get_string_width(val) + PADDING, CAP_COL)
            if w > col_raw[i]:
                col_raw[i] = w

    col_raw = [max(MIN_COL, w) for w in col_raw]

    # Scale proportionally to fill USABLE_W exactly
    total = sum(col_raw)
    col_widths = [round(w * USABLE_W / total, 2) for w in col_raw]
    col_widths[-1] = round(USABLE_W - sum(col_widths[:-1]), 2)

    cols = list(zip(col_names, col_widths))

    def render_data_row(row_vals):
        """Render a table data row with wrapping text and uniform cell height."""
        pdf.set_font("Helvetica", "", 7)
        y_start = pdf.get_y()
        x_start = pdf.l_margin
        line_h = 5

        # Measure how many lines each cell needs, take the max for a uniform row height
        max_lines = 1
        for (_, col_w), val in zip(cols, row_vals):
            if val:
                lines = max(1, ceil(pdf.get_string_width(val) / max(1, col_w - 2)))
                max_lines = max(max_lines, lines)
        row_h = max_lines * line_h

        # Start a new page if the row won't fit, then re-set font (header resets it)
        if pdf.will_page_break(row_h):
            pdf.add_page()
            pdf.set_font("Helvetica", "", 7)
            y_start = pdf.get_y()

        # Draw all cell borders at the full uniform row height
        pdf.set_draw_color(180, 195, 210)
        x_cursor = x_start
        for (_, col_w), _ in zip(cols, row_vals):
            pdf.rect(x_cursor, y_start, col_w, row_h)
            x_cursor += col_w

        # Render text in each cell without border (borders already drawn above)
        pdf.set_text_color(51, 65, 85)
        x_cursor = x_start
        for (_, col_w), val in zip(cols, row_vals):
            pdf.set_xy(x_cursor + 1, y_start + 0.5)
            pdf.multi_cell(col_w - 2, line_h, val, border=0, align="L")
            x_cursor += col_w

        pdf.set_y(y_start + row_h)

    for sev_label, sev_color in severity_configs:
        sev_vulns = vulns_by_severity[sev_label]
        if not sev_vulns:
            continue

        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(*sev_color)
        pdf.cell(0, 8, f"{sev_label} ({len(sev_vulns)})", ln=True)
        pdf.ln(2)

        # Table header
        pdf.set_fill_color(*sev_color)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 7)
        for i, (col_name, col_w) in enumerate(cols):
            pdf.cell(col_w, 7, col_name, 1, 1 if i == len(cols) - 1 else 0, "C", True)

        # Table rows
        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(51, 65, 85)
        for vuln in sev_vulns:
            render_data_row(vuln.get('_row_vals', []))

        pdf.ln(8)

    # Detail section: descriptions and external references
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(0, 12, "Vulnerability Details", ln=True)
    pdf.ln(5)

    all_vulns = (vulns_by_severity["CRITICAL"] + vulns_by_severity["HIGH"] +
                 vulns_by_severity["MEDIUM"]   + vulns_by_severity["LOW"])

    if all_vulns:
        for vuln in all_vulns:
            v = vuln.get("vulnerability", {})
            c = vuln.get("component", {})

            vuln_id     = v.get("vulnId", "N/A")
            severity    = v.get("severity", "N/A")
            score       = v.get("cvssV3BaseScore") or v.get("cvssV2BaseScore") or "N/A"
            description = sanitize_text((v.get("description") or "No description available")[:500])
            cwes        = v.get("cwes", [])
            published   = v.get("published", "")

            sev_color = (220, 38, 38) if severity == "CRITICAL" else \
                        (234, 88, 12) if severity == "HIGH" else \
                        (250, 204, 21) if severity == "MEDIUM" else (34, 197, 94)

            pdf.set_font("Helvetica", "B", 12)
            pdf.set_text_color(*sev_color)
            pdf.cell(0, 8, sanitize_text(vuln_id), ln=True)

            component_info = (f"{sanitize_text(c.get('name',''))} v{sanitize_text(str(c.get('version','')))} "
                              f"| CVSS: {score} | {severity}")
            if vuln.get('sourceName'):
                component_info += f" | Project: {sanitize_text(vuln['sourceName'])}"
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(100, 116, 139)
            pdf.cell(0, 5, sanitize_text(component_info), ln=True)
            pdf.ln(2)

            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(51, 65, 85)
            suffix = "..." if len(v.get("description", "")) > 500 else ""
            pdf.multi_cell(0, 4, description + suffix)
            pdf.ln(2)

            if cwes or published:
                info_parts = []
                if published:
                    info_parts.append(f"Published: {published[:10]}")
                if cwes:
                    info_parts.append(", ".join(f"CWE-{cwe.get('cweId')}" for cwe in cwes[:3]))
                pdf.set_font("Helvetica", "", 8)
                pdf.set_text_color(100, 116, 139)
                pdf.cell(0, 4, " | ".join(info_parts), ln=True)

            if vuln_id.startswith("CVE-"):
                link_url = f"https://nvd.nist.gov/vuln/detail/{vuln_id}"
                pdf.set_font("Helvetica", "", 8)
                pdf.set_text_color(59, 130, 246)
                pdf.cell(0, 4, f"-> {link_url}", ln=True, link=link_url)
            elif vuln_id.startswith("GHSA-"):
                link_url = f"https://github.com/advisories/{vuln_id}"
                pdf.set_font("Helvetica", "", 8)
                pdf.set_text_color(59, 130, 246)
                pdf.cell(0, 4, f"-> {link_url}", ln=True, link=link_url)

            pdf.ln(4)
            pdf.set_draw_color(226, 232, 240)
            pdf.line(10, pdf.get_y(), pdf.w - 10, pdf.get_y())
            pdf.ln(6)
    else:
        pdf.set_font("Helvetica", "", 12)
        pdf.set_fill_color(240, 253, 244)
        pdf.set_text_color(22, 163, 74)
        pdf.cell(0, 12, "   [OK] No vulnerabilities found", ln=True, fill=True)

    pdf.output("vulnerability-report.pdf")
    print("PDF generated successfully")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: generate_vuln_report.py <project_name> <project_version>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
