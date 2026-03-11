#!/usr/bin/env python3
import json
import sys
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

def main(project_name, project_version):
    # Load data
    with open("metrics.json") as f:
        metrics = json.load(f)
    with open("findings.json") as f:
        findings = json.load(f)

    class VulnPDF(FPDF):
        def header(self):
            # Gradient-like header with dark blue
            self.set_fill_color(30, 58, 138)  # Dark blue
            self.rect(0, 0, 210, 45, 'F')

            # Title
            self.set_text_color(255, 255, 255)
            self.set_font("Helvetica", "B", 32)
            self.set_y(15)
            self.cell(0, 12, "Security Analysis Report", align="C", ln=True)

            # Subtitle
            self.set_font("Helvetica", "", 11)
            self.set_text_color(203, 213, 225)
            self.cell(0, 8, f"{project_name} {project_version}", align="C")

            # Position cursor below header
            self.set_y(50)

        def footer(self):
            self.set_y(-15)
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(148, 163, 184)
            self.set_draw_color(226, 232, 240)
            self.line(10, self.get_y() - 3, 200, self.get_y() - 3)
            self.cell(0, 10, f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} | Page {self.page_no()}", align="C")

    # Create PDF
    pdf = VulnPDF()
    pdf.set_top_margin(50)
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=25)

    # Metrics cards
    total = metrics.get("vulnerabilities", 0)
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

    # Metrics grid - 4 boxes in a row
    box_width = 45
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

        # Box background
        pdf.set_fill_color(248, 250, 252)
        pdf.rect(x_pos, base_y, box_width, box_height, 'F')

        # Color bar on left
        pdf.set_fill_color(*color)
        pdf.rect(x_pos, base_y, 3, box_height, 'F')

        # Count (large)
        pdf.set_xy(x_pos + 5, base_y + 5)
        pdf.set_font("Helvetica", "B", 24)
        pdf.set_text_color(*color)
        pdf.cell(box_width - 10, 10, str(count), align="C")

        # Label (small)
        pdf.set_xy(x_pos + 5, base_y + 14)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(71, 85, 105)
        pdf.cell(box_width - 10, 6, label, align="C")

    pdf.set_y(base_y + box_height + 10)

    # Group vulnerabilities by severity
    vulns_by_severity = {"CRITICAL": [], "HIGH": [], "MEDIUM": [], "LOW": []}
    for vuln in findings:
        severity = vuln.get("vulnerability", {}).get("severity", "")
        if severity in vulns_by_severity:
            vulns_by_severity[severity].append(vuln)

    # Sort each group by CVSS score
    for severity in vulns_by_severity:
        vulns_by_severity[severity] = sorted(
            vulns_by_severity[severity],
            key=lambda x: x.get("vulnerability", {}).get("cvssV3BaseScore", 0) or x.get("vulnerability", {}).get("cvssV2BaseScore", 0) or 0,
            reverse=True
        )

    # Vulnerability summary tables by severity
    severity_configs = [
        ("CRITICAL", (220, 38, 38)),
        ("HIGH", (234, 88, 12)),
        ("MEDIUM", (250, 204, 21)),
        ("LOW", (34, 197, 94))
    ]

    # Collect all vulnerabilities to show in detailed section (up to 50)
    detailed_vulns = vulns_by_severity["CRITICAL"] + vulns_by_severity["HIGH"] + vulns_by_severity["MEDIUM"] + vulns_by_severity["LOW"]
    detailed_vulns = detailed_vulns[:50]

    # Create set of vuln IDs that will have detail pages
    detailed_vuln_ids = set()
    for vuln in detailed_vulns:
        vuln_id = vuln.get("vulnerability", {}).get("vulnId", "N/A")
        detailed_vuln_ids.add(vuln_id)

    # Create link map for all detailed vulns
    vuln_links = {}
    for vuln in detailed_vulns:
        vuln_id = vuln.get("vulnerability", {}).get("vulnId", "N/A")
        vuln_links[vuln_id] = pdf.add_link()

    # Render tables - one per row
    for sev_label, sev_color in severity_configs:
        # Only show vulnerabilities that have detail pages
        sev_vulns = [v for v in vulns_by_severity[sev_label] if v.get("vulnerability", {}).get("vulnId", "N/A") in detailed_vuln_ids]
        if not sev_vulns:
            continue

        # Section header
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(*sev_color)
        pdf.cell(0, 8, f"{sev_label} ({len(sev_vulns)})", ln=True)
        pdf.ln(2)

        # Table header
        pdf.set_fill_color(*sev_color)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(50, 7, "Vulnerability ID", 1, 0, "C", True)
        pdf.cell(75, 7, "Component", 1, 0, "C", True)
        pdf.cell(25, 7, "Version", 1, 0, "C", True)
        pdf.cell(30, 7, "CVSS Score", 1, 1, "C", True)

        # Table rows
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(51, 65, 85)
        for vuln in sev_vulns:
            v = vuln.get("vulnerability", {})
            c = vuln.get("component", {})
            vuln_id = v.get("vulnId", "N/A")
            component = c.get("name", "N/A")[:35]
            version = c.get("version", "N/A")[:12]
            score = v.get("cvssV3BaseScore") or v.get("cvssV2BaseScore") or "N/A"

            # Link to detail section if available
            if vuln_id in vuln_links:
                pdf.set_text_color(59, 130, 246)
                pdf.cell(50, 6, vuln_id, 1, 0, "L", False, vuln_links[vuln_id])
            else:
                pdf.set_text_color(51, 65, 85)
                pdf.cell(50, 6, vuln_id, 1, 0, "L")

            pdf.set_text_color(51, 65, 85)
            pdf.cell(75, 6, sanitize_text(component), 1, 0, "L")
            pdf.cell(25, 6, sanitize_text(str(version)), 1, 0, "C")
            pdf.cell(30, 6, sanitize_text(str(score)), 1, 1, "C")

        pdf.ln(8)

    # Detailed vulnerability information
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(0, 12, "Detailed Vulnerability Information", ln=True)
    pdf.ln(5)

    # Show detailed info for all vulnerabilities
    if detailed_vulns:
        for vuln in detailed_vulns[:50]:
            v = vuln.get("vulnerability", {})
            c = vuln.get("component", {})

            vuln_id = v.get("vulnId", "N/A")
            severity = v.get("severity", "N/A")
            score = v.get("cvssV3BaseScore") or v.get("cvssV2BaseScore") or "N/A"
            component = c.get("name", "N/A")
            version = c.get("version", "N/A")
            description = v.get("description", "No description available")[:400]
            cwes = v.get("cwes", [])
            published = v.get("published", "")

            sev_color = (220, 38, 38) if severity == "CRITICAL" else (234, 88, 12)

            # Set link destination
            if vuln_id in vuln_links:
                pdf.set_link(vuln_links[vuln_id], y=pdf.get_y())

            # Vulnerability ID header
            pdf.set_font("Helvetica", "B", 14)
            pdf.set_text_color(*sev_color)
            pdf.cell(0, 8, vuln_id, ln=True)

            # Component and score
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(100, 116, 139)
            pdf.cell(0, 5, sanitize_text(f"{component} v{version} | CVSS: {score} | {severity}"), ln=True)
            pdf.ln(2)

            # Description
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(51, 65, 85)
            pdf.multi_cell(0, 4, sanitize_text(description) + ("..." if len(v.get("description", "")) > 400 else ""))
            pdf.ln(2)

            # CWE info
            if cwes or published:
                pdf.set_font("Helvetica", "", 8)
                pdf.set_text_color(100, 116, 139)
                info_parts = []
                if published:
                    info_parts.append(f"Published: {published[:10]}")
                if cwes:
                    cwe_list = ", ".join([f"CWE-{cwe.get('cweId')}" for cwe in cwes[:3]])
                    info_parts.append(cwe_list)
                pdf.cell(0, 4, " | ".join(info_parts), ln=True)
                pdf.ln(1)

            # External reference link
            if vuln_id.startswith("CVE-"):
                pdf.set_font("Helvetica", "", 8)
                pdf.set_text_color(59, 130, 246)
                link_url = f"https://nvd.nist.gov/vuln/detail/{vuln_id}"
                pdf.cell(0, 4, f"-> {link_url}", ln=True, link=link_url)
            elif vuln_id.startswith("GHSA-"):
                pdf.set_font("Helvetica", "", 8)
                pdf.set_text_color(59, 130, 246)
                link_url = f"https://github.com/advisories/{vuln_id}"
                pdf.cell(0, 4, f"-> {link_url}", ln=True, link=link_url)

            pdf.ln(4)
            pdf.set_draw_color(226, 232, 240)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(6)
    else:
        pdf.set_font("Helvetica", "", 12)
        pdf.set_fill_color(240, 253, 244)
        pdf.set_text_color(22, 163, 74)
        pdf.cell(0, 12, "   [OK] No critical or high severity vulnerabilities found", ln=True, fill=True)

    # Footer information
    pdf.ln(10)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(148, 163, 184)
    pdf.multi_cell(0, 4, "This report shows critical and high severity vulnerabilities only. For a complete analysis including all severity levels, detailed remediation steps, and exploitability metrics, please access the Dependency Track web interface or review the full findings export.", align="C")

    pdf.output("vulnerability-report.pdf")
    print("PDF generated successfully")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: generate_vuln_report.py <project_name> <project_version>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
