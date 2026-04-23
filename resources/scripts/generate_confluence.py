#!/usr/bin/env python3
"""
Generate a Confluence storage-format HTML page documenting the SBOM pipeline
and Dependency-Track vulnerability management workflow.

Output: SBOM_DependencyTrack_Confluence.html
        (paste into Confluence via: Edit → Insert → HTML / Markup, or
         publish via the Confluence REST API)

Usage (standalone):
    python3 generate_confluence.py

Usage (via the generate_docs.sh container script – recommended):
    ./generate_docs.sh
"""

from datetime import datetime
import base64
import os

# ── Screenshot helper ─────────────────────────────────────────────────────
_SCREENSHOT_DIR = os.environ.get('SCREENSHOT_DIR', '/screenshots')


def embed_screenshot(filename: str, alt: str = "", width: int = 750) -> str:
    """Return an <img> tag with a base64-embedded PNG, or empty string if not found."""
    path = os.path.join(_SCREENSHOT_DIR, filename)
    if not os.path.isfile(path):
        return ""
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode("ascii")
    return (
        f'<p style="margin:1rem 0;">'
        f'<img src="data:image/png;base64,{data}" alt="{alt}" '
        f'style="max-width:{width}px;width:100%;border:1px solid #e2e8f0;'
        f'border-radius:6px;box-shadow:0 2px 6px rgba(0,0,0,.12);" />'
        f'</p>'
    )


# ── Confluence Storage Format helpers ──────────────────────────────────────


def info_panel(body: str, title: str = "") -> str:
    t = f'<ac:parameter ac:name="title">{title}</ac:parameter>' if title else ""
    return (
        f'<ac:structured-macro ac:name="info">{t}'
        f"<ac:rich-text-body><p>{body}</p></ac:rich-text-body>"
        f"</ac:structured-macro>"
    )


def note_panel(body: str, title: str = "") -> str:
    t = f'<ac:parameter ac:name="title">{title}</ac:parameter>' if title else ""
    return (
        f'<ac:structured-macro ac:name="note">{t}'
        f"<ac:rich-text-body><p>{body}</p></ac:rich-text-body>"
        f"</ac:structured-macro>"
    )


def warning_panel(body: str, title: str = "") -> str:
    t = f'<ac:parameter ac:name="title">{title}</ac:parameter>' if title else ""
    return (
        f'<ac:structured-macro ac:name="warning">{t}'
        f"<ac:rich-text-body><p>{body}</p></ac:rich-text-body>"
        f"</ac:structured-macro>"
    )


def tip_panel(body: str, title: str = "") -> str:
    t = f'<ac:parameter ac:name="title">{title}</ac:parameter>' if title else ""
    return (
        f'<ac:structured-macro ac:name="tip">{t}'
        f"<ac:rich-text-body><p>{body}</p></ac:rich-text-body>"
        f"</ac:structured-macro>"
    )


def code_block(code: str, language: str = "xml", title: str = "") -> str:
    t = f'<ac:parameter ac:name="title">{title}</ac:parameter>' if title else ""
    return (
        f'<ac:structured-macro ac:name="code">'
        f'<ac:parameter ac:name="language">{language}</ac:parameter>'
        f'<ac:parameter ac:name="linenumbers">true</ac:parameter>'
        f"{t}"
        f"<ac:plain-text-body><![CDATA[{code}]]></ac:plain-text-body>"
        f"</ac:structured-macro>"
    )


def expand_macro(title: str, body: str) -> str:
    return (
        f'<ac:structured-macro ac:name="expand">'
        f'<ac:parameter ac:name="title">{title}</ac:parameter>'
        f"<ac:rich-text-body>{body}</ac:rich-text-body>"
        f"</ac:structured-macro>"
    )


def table_of_contents() -> str:
    return (
        '<ac:structured-macro ac:name="toc">'
        '<ac:parameter ac:name="printable">true</ac:parameter>'
        '<ac:parameter ac:name="style">disc</ac:parameter>'
        '<ac:parameter ac:name="maxLevel">3</ac:parameter>'
        "</ac:structured-macro>"
    )


def status_macro(text: str, colour: str, subtle: bool = False) -> str:
    s = "true" if subtle else "false"
    return (
        f'<ac:structured-macro ac:name="status">'
        f'<ac:parameter ac:name="colour">{colour}</ac:parameter>'
        f'<ac:parameter ac:name="title">{text}</ac:parameter>'
        f'<ac:parameter ac:name="subtle">{s}</ac:parameter>'
        f"</ac:structured-macro>"
    )


def ul(*items: str) -> str:
    lis = "".join(f"<li>{i}</li>" for i in items)
    return f"<ul>{lis}</ul>"


def ol(*items: str) -> str:
    lis = "".join(f"<li>{i}</li>" for i in items)
    return f"<ol>{lis}</ol>"


def th(text: str, bg: str = "#1e3a8a", fg: str = "#ffffff") -> str:
    return (
        f'<th style="background-color:{bg};color:{fg};padding:6px 10px;">'
        f"<strong>{text}</strong></th>"
    )


def td(text: str, color: str = "#0f172a", bg: str = "") -> str:
    bg_style = f"background-color:{bg};" if bg else ""
    return f'<td style="{bg_style}padding:5px 10px;color:{color};">{text}</td>'


def tr(*cells: str, bg: str = "") -> str:
    bg_style = f'style="background-color:{bg};"' if bg else ""
    return f"<tr {bg_style}>{''.join(cells)}</tr>"


def badge(text: str, color: str, fg: str = "#fff") -> str:
    return (
        f'<span style="background:{color};color:{fg};padding:2px 8px;'
        f'border-radius:4px;font-weight:bold;font-size:0.85em;">{text}</span>'
    )


# ── Page sections ──────────────────────────────────────────────────────────


def section_intro() -> str:
    return (
        info_panel(
            "This page describes the SBOM (Software Bill of Materials) pipeline and how "
            "Dependency-Track is used to continuously monitor, triage, and manage "
            "software vulnerabilities across all projects. It covers SBOM generation, "
            "upload, vulnerability triage workflows, comments, suppression, and automated reporting.",
            title="About this page",
        )
        + f"<p><em>Last updated: {datetime.now().strftime('%d %B %Y')}</em></p>"
        + table_of_contents()
    )


def section_what_is_sbom() -> str:
    return (
        "<h2>1. What is an SBOM?</h2>"
        "<p>An <strong>SBOM (Software Bill of Materials)</strong> is a formal, machine-readable "
        "inventory of every open-source and third-party component included in an application — "
        "along with their versions, licences, and dependency relationships. "
        "It is the foundation for understanding what your software is made of and "
        "identifying where security risks exist.</p>"
        "<h3>What an SBOM records</h3>"
        + ul(
            "Component name and version",
            "Package supplier / origin",
            "Dependency relationships (direct and transitive)",
            "Licence identifiers (SPDX format)",
            "Known vulnerability references (CVE cross-links)",
        )
        + "<h3>CycloneDX Format</h3>"
        "<p>All SBOMs in this pipeline use the <strong>CycloneDX</strong> standard "
        "(an OWASP project). CycloneDX is natively supported by Dependency-Track, "
        "<code>cdxgen</code>, and the CycloneDX Maven / Gradle plugins. "
        "SBOMs are stored as JSON files.</p>"
        + tip_panel(
            "CycloneDX is the recommended SBOM format for Dependency-Track. "
            "SPDX format is also supported but CycloneDX provides richer metadata "
            "for vulnerability correlation.",
            title="Why CycloneDX?",
        )
        + "<h3>Why do SBOMs matter?</h3>"
        + ul(
            "Provides complete visibility into <em>all</em> transitive dependencies — not just direct ones",
            "Enables rapid impact assessment when a new CVE is published",
            "Supports licence compliance and open-source governance",
            "Creates an auditable supply-chain record",
            "Required by emerging software security regulations and standards",
        )
    )


def section_sbom_generation() -> str:
    pom_snippet = """\
<plugin>
  <groupId>org.cyclonedx</groupId>
  <artifactId>cyclonedx-maven-plugin</artifactId>
  <version>2.9.1</version>
  <executions>
    <execution>
      <phase>package</phase>
      <goals>
        <goal>makeAggregateBom</goal>
      </goals>
    </execution>
  </executions>
  <configuration>
    <outputFormat>json</outputFormat>
    <outputName>sbom</outputName>
  </configuration>
</plugin>"""

    pipeline_steps = (
        "<ol>"
        "<li>Developer pushes code to Git → Jenkins pipeline triggered</li>"
        "<li>CycloneDX Maven plugin runs during <code>mvn package</code></li>"
        "<li>Plugin generates <code>sbom.json</code> reflecting the resolved dependency tree</li>"
        "<li>Jenkins <code>uploadSBOM()</code> shared library step posts the SBOM to Dependency-Track</li>"
        "<li>Dependency-Track enriches components with NVD / OSV / GitHub Advisory data</li>"
        "<li>Vulnerabilities are visible immediately in the Dependency-Track dashboard</li>"
        "</ol>"
    )

    return (
        "<h2>2. How SBOMs Are Generated</h2>"
        "<p>Two complementary approaches are used, both feeding directly into Dependency-Track.</p>"
        "<h3>2a. cdxgen — Any Language / Repository</h3>"
        "<p><code>cdxgen</code> is a polyglot SBOM generator that scans source trees and "
        "lock files. It is used for repositories that do not use Maven as their build tool.</p>"
        + ul(
            "Supports: Java, Node.js, Python, .NET, Go, Ruby, and more",
            "Scans source tree and dependency lock files automatically",
            "Runs as a Jenkins pipeline step via the <code>cdxgenRepo()</code> shared library call",
            "No changes are needed to the target repository",
            "Supports pinned image versions for reproducible pipeline builds",
        )
        + tip_panel(
            "Use <code>cdxgenRepo(env.SBOM_FILE, true, '', '17')</code> for Java repos to "
            "enable the Java-specific cdxgen image which can run Maven to resolve the full "
            "dependency tree.",
            title="Java repositories",
        )
        + "<h3>2b. CycloneDX Maven Plugin — In-House Java Code</h3>"
        "<p>For internally developed Java applications, the CycloneDX Maven plugin is added "
        "directly to <code>pom.xml</code>. The SBOM is generated and published to Dependency-Track "
        "<strong>automatically as part of the standard Maven build</strong>.</p>"
        + ul(
            "Zero additional tooling — everything runs inside the existing <code>mvn package</code> lifecycle",
            "Generates a precise SBOM reflecting the exact resolved dependency tree",
            "Vulnerability status is visible in Dependency-Track the moment the build lands",
            "Policy violations surface in the CI pipeline — not weeks later",
            "Developers get immediate feedback on new vulnerabilities introduced by their changes",
        )
        + code_block(pom_snippet, language="xml", title="Add to pom.xml")
        + "<h3>Maven Pipeline Flow</h3>"
        + pipeline_steps
        + note_panel(
            "The <code>uploadSBOM()</code> Jenkins shared library step handles project "
            "creation/lookup and parent-project grouping automatically. No manual Dependency-Track "
            "configuration is needed per project.",
            title="Automatic project management",
        )
        + "<h3>2c. Syft — Docker / Container Images</h3>"
        "<p><strong>Syft</strong> (by Anchore) scans Docker image layers to generate a full "
        "container SBOM — capturing every OS package and language library baked into the image, "
        "not just the application dependencies declared in a manifest.</p>"
        + ul(
            "Scans a pulled or locally built Docker image",
            "Identifies OS packages (Alpine, Debian, RHEL) <em>and</em> language libraries inside the image",
            "Outputs CycloneDX JSON — uploads directly to Dependency-Track via <code>uploadSBOM()</code>",
            "Used via the <code>syftImage()</code> Jenkins shared-library step",
            "Often used alongside <strong>Grype</strong> (also by Anchore) for pre-upload vulnerability triage",
        )
        + tip_panel(
            "Run <code>grypeScan()</code> after <code>syftImage()</code> to get an immediate "
            "vulnerability report before the SBOM is uploaded. Grype uses the same intelligence "
            "sources as Dependency-Track and is fast enough to run on every build.",
            title="Syft + Grype Together",
        )
    )


def section_dt_overview() -> str:
    features_table = (
        "<table>"
        + tr(
            th("Feature"),
            th("Description"),
        )
        + tr(
            td("<strong>Continuous Monitoring</strong>"),
            td(
                "Checks every component against NVD, OSV, GitHub Advisory, and Sonatype OSS Index "
                "automatically — no manual CVE searches required."
            ),
            bg="#f8fafc",
        )
        + tr(
            td("<strong>Policy Engine</strong>"),
            td(
                "Define licence policies, severity thresholds, and component allow/block lists. "
                "Violations are surfaced instantly and can break the build."
            ),
        )
        + tr(
            td("<strong>Portfolio / Collection View</strong>"),
            td(
                "Group child projects into an aggregate collection project. See combined risk "
                "across a product portfolio at a glance."
            ),
            bg="#f8fafc",
        )
        + tr(
            td("<strong>REST API</strong>"),
            td(
                "Fully headless via REST API. All pipeline integrations (SBOM upload, "
                "report export) use the API — no manual UI interaction needed."
            ),
        )
        + tr(
            td("<strong>Vulnerability Triage</strong>"),
            td(
                "Each finding can be given an analysis state, a justification, "
                "analyst comments, and optionally suppressed — all recorded with a full audit trail."
            ),
            bg="#f8fafc",
        )
        + tr(
            td("<strong>PDF Reporting</strong>"),
            td(
                "Jenkins pipelines generate branded PDF reports (vulnerability and SBOM component) "
                "automatically and archive them as build artefacts."
            ),
        )
        + "</table>"
    )

    return (
        "<h2>3. Dependency-Track Overview</h2>"
        "<p>Dependency-Track is an <strong>OWASP flagship</strong> platform that ingests CycloneDX "
        "SBOMs and continuously monitors every component for new vulnerabilities. It provides a "
        "central, always-current view of risk across the entire software portfolio.</p>"
        + embed_screenshot("dashboard.png", alt="Dependency-Track Portfolio Dashboard")
        + features_table
        + embed_screenshot("collection-projects-details.png", alt="Collection Project Detail View")
        + "<h3>Vulnerability Intelligence Sources</h3>"
        + "<p>Dependency-Track queries the following feeds automatically on a rolling schedule. "
        "No manual CVE searching is required — new vulnerabilities are matched against your "
        "entire component inventory the moment a feed refreshes.</p>"
        + (
            "<table>"
            + tr(th("Source"), th("Maintained by"), th("Scope"), th("Notes"))
            + tr(
                td("<strong>NVD</strong> — National Vulnerability Database"),
                td("NIST"),
                td("All languages &amp; ecosystems"),
                td("Canonical CVE registry with CVSS v2/v3/v4 scores. Primary authoritative source."),
                bg="#f8fafc",
            )
            + tr(
                td("<strong>OSV</strong> — Open Source Vulnerabilities"),
                td("Google"),
                td("PyPI, npm, Maven, Go, Cargo, Ruby gems &amp; more"),
                td("Open database with precise package-URL matching; often earlier disclosure than NVD."),
            )
            + tr(
                td("<strong>GitHub Advisory Database</strong>"),
                td("GitHub / community"),
                td("GitHub-hosted packages across all ecosystems"),
                td("Curated advisories tied directly to package versions; highly accurate matching."),
                bg="#f8fafc",
            )
            + tr(
                td("<strong>Sonatype OSS Index</strong>"),
                td("Sonatype"),
                td("Maven Central, npm"),
                td("Component intelligence with licence and ecosystem metadata; strong Java coverage."),
            )
            + tr(
                td("<strong>VulnDB</strong>"),
                td("Risk Based Security"),
                td("All ecosystems"),
                td("Optional commercial feed. Broader coverage and earlier disclosure than NVD. Configurable in DT settings."),
                bg="#f8fafc",
            )
            + "</table>"
        )
        + "<h3>SBOM Generation &amp; Detection Tools</h3>"
        + "<p>The pipeline supports multiple tools for generating SBOMs and scanning "
        "for vulnerabilities — choose the right tool for the project type.</p>"
        + (
            "<table>"
            + tr(th("Tool"), th("Type"), th("Use Case"), th("Jenkins Step"))
            + tr(
                td("<strong>cdxgen</strong>"),
                td("SBOM Generator"),
                td("Polyglot — Java, Node.js, Python, Go, .NET, Ruby, Cargo &amp; more. Source-tree and lock-file scanning."),
                td("<code>cdxgenRepo()</code>"),
                bg="#f8fafc",
            )
            + tr(
                td("<strong>CycloneDX Maven Plugin</strong>"),
                td("SBOM Generator"),
                td("Java/Maven — embedded in pom.xml; generates an exact resolved-dependency-tree SBOM at build time."),
                td("Runs automatically via <code>mvn package</code>"),
            )
            + tr(
                td("<strong>Syft</strong> (Anchore)"),
                td("SBOM Generator"),
                td("Docker / container images — scans image layers to produce a full container SBOM."),
                td("<code>syftImage()</code>"),
                bg="#f8fafc",
            )
            + tr(
                td("<strong>Grype</strong> (Anchore)"),
                td("Vulnerability Scanner"),
                td("Consumes a Syft or cdxgen SBOM and scans for known vulnerabilities. Used for pre-upload triage."),
                td("<code>grypeScan()</code>"),
            )
            + tr(
                td("<strong>CycloneDX Gradle / Node / .NET</strong>"),
                td("SBOM Generator"),
                td("Ecosystem-specific build plugins that mirror the Maven plugin approach for Gradle, npm, and .NET SDK projects."),
                td("Language-native build steps"),
                bg="#f8fafc",
            )
            + "</table>"
        )
        + tip_panel(
            "All tools produce <strong>CycloneDX JSON</strong> SBOMs that feed directly into "
            "Dependency-Track via the <code>uploadSBOM()</code> Jenkins shared-library step. "
            "The format is consistent regardless of the generator used.",
            title="Consistent Format Across All Tools",
        )
    )


def section_vuln_workflow() -> str:
    scr = embed_screenshot("vulnerabilities.png", alt="Vulnerability Findings List")
    steps_table = (
        "<table>"
        + tr(
            th("Step"),
            th("Action"),
            th("Notes"),
        )
        + tr(
            td(badge("1", "#1e3a8a") + " Ingest SBOM"),
            td("SBOM uploaded via Jenkins pipeline."),
            td("DT resolves all components and cross-references vulnerability feeds."),
            bg="#f8fafc",
        )
        + tr(
            td(badge("2", "#06747c") + " Review Findings"),
            td("Open the project in Dependency-Track."),
            td(
                "Findings are listed by severity: "
                + badge("CRITICAL", "#b91c1c")
                + " "
                + badge("HIGH", "#d97706")
                + " "
                + badge("MEDIUM", "#ca8a04")
                + " "
                + badge("LOW", "#15803d")
            ),
        )
        + tr(
            td(badge("3", "#d97706", "#1e293b") + " Triage"),
            td("Assess each finding."),
            td(
                "Decide: fix immediately, accept risk with justification, suppress, "
                "or escalate to engineering."
            ),
            bg="#f8fafc",
        )
        + tr(
            td(badge("4", "#7c3aed") + " Record Analysis"),
            td("Document your decision inside Dependency-Track."),
            td(
                "Set the analysis state, add an analyst comment, optionally suppress. "
                "All actions are time-stamped and attributed."
            ),
        )
        + tr(
            td(badge("5", "#15803d") + " Remediate &amp; Re-scan"),
            td("Engineering upgrades the dependency."),
            td(
                "The next pipeline run re-uploads the SBOM. "
                "The finding disappears from the dashboard automatically."
            ),
            bg="#f8fafc",
        )
        + "</table>"
    )

    return (
        "<h2>4. Managing Vulnerabilities</h2>"
        "<p>Dependency-Track surfaces every finding. Your team then triages, analyses, and "
        "resolves each one — all recorded within the platform to provide a full audit trail.</p>"
        + scr
        + steps_table
    )


def section_analysis_actions() -> str:
    states_table = (
        "<table>"
        + tr(
            th("Analysis State"),
            th("Meaning"),
            th("When to use"),
        )
        + tr(
            td(badge("NOT_AFFECTED", "#15803d")),
            td("The vulnerability does not apply to this deployment context."),
            td(
                "The affected code path is unused, a mitigating control is in place, "
                "or the component is used in a way that is not exploitable."
            ),
            bg="#f0fdf4",
        )
        + tr(
            td(badge("IN_TRIAGE", "#d97706", "#1e293b")),
            td("The finding is being actively investigated."),
            td(
                "Interim state — use while the team is determining the impact "
                "and deciding on the appropriate response."
            ),
        )
        + tr(
            td(badge("EXPLOITABLE", "#b91c1c")),
            td("Confirmed — the vulnerability is present and exploitable."),
            td("Immediate remediation required. Escalate to engineering."),
            bg="#fff1f2",
        )
        + tr(
            td(badge("RESOLVED", "#64748b")),
            td("The dependency has been upgraded; the vulnerability is gone."),
            td(
                "The next SBOM upload will remove this finding automatically. "
                "This state confirms the fix was verified."
            ),
        )
        + tr(
            td(badge("FALSE_POSITIVE", "#64748b")),
            td("The vulnerability does not apply at all."),
            td(
                "Typically because the affected code path is never invoked, "
                "or the CVE was incorrectly assigned to this package version.",
            ),
            bg="#f8fafc",
        )
        + "</table>"
    )

    comment_example = expand_macro(
        "Example analyst comment (CVE-2021-44228 / log4j-core 2.14.1)",
        "<p><em>Reviewed 2025-01-15 by J. Smith.<br/>"
        "Our deployment uses the JNDI lookup feature disabled via "
        "<code>log4j2.formatMsgNoLookups=true</code> JVM flag set at container startup. "
        "Confirmed with DevOps — the attack vector is mitigated. "
        "Tracking upgrade to log4j 2.17.1 in Q1 sprint board (JIRA-4821).</em></p>",
    )

    return (
        "<h2>5. Vulnerability Analysis — Comments, Suppression &amp; State</h2>"
        "<p>Every finding in Dependency-Track can be analysed, commented on, and formally "
        "recorded. This creates an <strong>audit trail of all security decisions</strong> "
        "made by the team.</p>"
        + embed_screenshot("audit-finding-project.png", alt="Audit Finding — Analysis Panel")
        + "<h3>Analysis States</h3>"
        + states_table
        + "<h3>Analyst Comments</h3>"
        "<p>Free-text comments can be added to any finding. Comments should include:</p>"
        + ul(
            "The date and analyst name",
            "The reason for the decision (e.g. mitigating control, unused code path)",
            "Any linked tickets or evidence (e.g. JIRA issue, PR number)",
            "A remediation timeline if applicable",
        )
        + comment_example
        + "<h3>Suppression</h3>"
        "<p>When a finding is accepted or not applicable, it can be <strong>suppressed</strong> "
        "so it no longer inflates your vulnerability counts or risk score.</p>"
        + ul(
            "Suppressed findings are hidden from the default dashboard view",
            "They remain fully searchable with the <em>Show suppressed</em> filter",
            "All original CVE details, CVSS scores, and analyst notes are preserved",
            "Suppression can be revoked at any time — fully reversible",
            "Suppressed findings are still included in the vulnerability PDF report",
            "The audit trail records who suppressed a finding and when",
        )
        + warning_panel(
            "<strong>Suppression is not remediation.</strong> Always pair suppression with a "
            "documented justification and a remediation timeline where applicable. "
            "Suppressed findings should be reviewed periodically to ensure the justification "
            "remains valid.",
            title="Important",
        )
    )


def section_reporting() -> str:
    vuln_table_header = (
        "<table>"
        + tr(
            th("CVE ID"),
            th("Component"),
            th("Version"),
            th("Severity"),
            th("CVSS"),
            th("Analysis State"),
            th("Description"),
        )
    )

    def sev_badge(s: str) -> str:
        colors = {
            "CRITICAL": "#b91c1c",
            "HIGH": "#d97706",
            "MEDIUM": "#ca8a04",
            "LOW": "#15803d",
        }
        return badge(s, colors.get(s, "#64748b"))

    def state_badge(s: str) -> str:
        colors = {
            "NOT_AFFECTED": "#15803d",
            "IN_TRIAGE": "#d97706",
            "EXPLOITABLE": "#b91c1c",
            "RESOLVED": "#64748b",
            "FALSE_POSITIVE": "#64748b",
        }
        return badge(s, colors.get(s, "#64748b"))

    vuln_rows = [
        ("CVE-2021-44228", "log4j-core",         "2.14.1", "CRITICAL", "10.0", "NOT_AFFECTED",  "JNDI disabled via JVM flag — mitigated"),
        ("CVE-2022-42003", "jackson-databind",    "2.13.0", "HIGH",     "7.5",  "IN_TRIAGE",     "Resource consumption — under review"),
        ("CVE-2023-20863", "spring-expression",   "5.3.25", "HIGH",     "6.5",  "IN_TRIAGE",     "ReDoS — investigating impact"),
        ("CVE-2022-45868", "h2database",          "2.1.210","HIGH",     "7.8",  "EXPLOITABLE",   "Upgrade to 2.2.x scheduled sprint 14"),
        ("CVE-2023-34042", "spring-security-web", "5.7.5",  "MEDIUM",   "5.3",  "FALSE_POSITIVE","Unused endpoint — confirmed FP"),
        ("CVE-2023-20861", "spring-expression",   "5.3.25", "MEDIUM",   "5.9",  "RESOLVED",      "Upgraded to 6.0.8 in PR #441"),
    ]

    rows_html = ""
    for i, (cve, comp, ver, sev, score, state, desc) in enumerate(vuln_rows):
        bg = "#f8fafc" if i % 2 == 0 else ""
        rows_html += tr(
            td(f"<code>{cve}</code>"),
            td(comp),
            td(ver),
            td(sev_badge(sev)),
            td(score),
            td(state_badge(state)),
            td(desc),
            bg=bg,
        )

    vuln_example_table = vuln_table_header + rows_html + "</table>"

    comp_table_header = (
        "<table>"
        + tr(
            th("Component"),
            th("Version"),
            th("Supplier"),
            th("Type"),
            th("Licence"),
            th("Scope"),
        )
    )

    def lic_badge(lic: str) -> str:
        colors = {
            "Apache-2.0": "#15803d",
            "MIT": "#15803d",
            "LGPL-2.1": "#d97706",
            "GPL-2.0": "#b91c1c",
            "UNKNOWN": "#b91c1c",
        }
        return badge(lic, colors.get(lic, "#64748b"))

    comp_rows = [
        ("spring-boot-starter-web", "3.2.1",  "Pivotal / VMware",  "Library", "Apache-2.0", "Required"),
        ("jackson-databind",        "2.16.1", "FasterXML",         "Library", "Apache-2.0", "Required"),
        ("log4j-api",               "2.22.1", "Apache",            "Library", "Apache-2.0", "Required"),
        ("hibernate-core",          "6.4.2",  "Red Hat",           "Library", "LGPL-2.1",   "Required"),
        ("commons-lang3",           "3.14.0", "Apache",            "Library", "Apache-2.0", "Required"),
        ("bouncy-castle-provider",  "1.78",   "Legion of the BC",  "Library", "MIT",        "Optional"),
        ("netty-handler",           "4.1.107","Netty Project",     "Library", "Apache-2.0", "Required"),
        ("unknown-lib",             "0.9.1",  "(unknown)",         "Library", "UNKNOWN",    "Required"),
    ]

    comp_rows_html = ""
    for i, (name, ver, supplier, typ, lic, scope) in enumerate(comp_rows):
        bg = "#f8fafc" if i % 2 == 0 else ""
        comp_rows_html += tr(
            td(name),
            td(ver),
            td(supplier),
            td(typ),
            td(lic_badge(lic)),
            td(scope),
            bg=bg,
        )

    comp_example_table = comp_table_header + comp_rows_html + "</table>"

    return (
        "<h2>6. Automated Reporting</h2>"
        "<p>Jenkins pipelines generate shareable PDF reports from live Dependency-Track data. "
        "No manual export steps are required — reports are auto-archived as Jenkins build artefacts.</p>"
        "<h3>Security Analysis (Vulnerability) Report</h3>"
        + ul(
            "One report per project, or across all active projects via <code>exportAllDTReports()</code>",
            "Executive summary showing Critical / High / Medium / Low counts and overall risk level",
            "Per-vulnerability detail: CVE ID, component, version, CVSS score",
            "Analyst comments and suppression status included",
            "Landscape A4 PDF — ready to share with management or auditors",
            "Auto-archived as a Jenkins build artefact",
        )
        + "<h3>SBOM Component Report</h3>"
        + ul(
            "Full component inventory: name, version, supplier, licence",
            "Supports single project or all active projects",
            "Collection projects produce merged reports across all children",
            "Useful for licence compliance and open-source governance audits",
            "Flags components with missing or restrictive licences (GPL, UNKNOWN)",
            "Landscape A4 PDF — consistent, branded format",
        )
        + "<h2>7. Example Report Data</h2>"
        "<h3>Sample — Security Analysis Report (customer-api v1.8.0)</h3>"
        "<p>The table below illustrates the per-finding detail included in the PDF vulnerability report:</p>"
        + vuln_example_table
        + "<h3>Sample — SBOM Component Report (my-billing-service v2.4.1)</h3>"
        "<p>The table below illustrates the component inventory included in the PDF SBOM report. "
        "187 total components (43 direct, 144 transitive) across 12 unique licences:</p>"
        + comp_example_table
        + note_panel(
            "Licence colours: "
            + badge("Apache-2.0", "#15803d")
            + " "
            + badge("MIT", "#15803d")
            + " = permissive; "
            + badge("LGPL-2.1", "#d97706", "#1e293b")
            + " = weak copyleft (review required); "
            + badge("UNKNOWN", "#b91c1c")
            + " = action required.",
            title="Licence colour key",
        )
    )


def section_pipeline() -> str:
    pipeline_table = (
        "<table>"
        + tr(
            th("Shared Library Function"),
            th("Purpose"),
            th("Typical Usage"),
        )
        + tr(
            td("<code>cdxgenRepo()</code>"),
            td("Generate SBOM for any language repository using cdxgen"),
            td("<code>cdxgenRepo(env.SBOM_FILE, true, '', '17')</code>"),
            bg="#f8fafc",
        )
        + tr(
            td("<code>uploadSBOM()</code>"),
            td("Upload SBOM and create/update Dependency-Track project"),
            td("<code>uploadSBOM(sbomFile: ..., projectName: ..., projectVersion: ...)</code>"),
        )
        + tr(
            td("<code>createDTCollectionProject()</code>"),
            td("Group child projects into an aggregate collection with combined metrics"),
            td("<code>createDTCollectionProject(name: 'my-portfolio', version: '1.0')</code>"),
            bg="#f8fafc",
        )
        + tr(
            td("<code>exportDTReport()</code>"),
            td("Generate vulnerability PDF for a single project"),
            td("<code>exportDTReport(projectName: ..., projectVersion: ...)</code>"),
        )
        + tr(
            td("<code>exportAllDTReports()</code>"),
            td("Generate vulnerability PDFs for every active Dependency-Track project"),
            td("<code>exportAllDTReports(env.DEPENDENCY_TRACK_API_URL)</code>"),
            bg="#f8fafc",
        )
        + tr(
            td("<code>exportSBOMReport()</code>"),
            td("Generate SBOM component PDF for a single project"),
            td("<code>exportSBOMReport(projectName: ..., projectVersion: ...)</code>"),
        )
        + tr(
            td("<code>grypeScan()</code>"),
            td("Run Grype container image vulnerability scan as a pipeline stage"),
            td("<code>grypeScan(image: 'myapp:latest')</code>"),
            bg="#f8fafc",
        )
        + "</table>"
    )

    return (
        "<h2>8. Pipeline Overview</h2>"
        "<p>The end-to-end flow from source commit to vulnerability insight is fully automated "
        "via the Jenkins shared library.</p>"
        + ol(
            "Developer pushes code to Git — Jenkins pipeline triggered",
            "SBOM generated via <code>cdxgenRepo()</code> or the CycloneDX Maven plugin",
            "<code>uploadSBOM()</code> posts the SBOM to Dependency-Track via REST API",
            "Dependency-Track enriches components against NVD, OSV, and GitHub Advisories",
            "Vulnerabilities are listed by severity with CVSS scores in the DT dashboard",
            "Team triages findings, records analysis, and suppresses accepted risks",
            "<code>exportAllDTReports()</code> generates PDF reports, archived as build artefacts",
        )
        + "<h3>Jenkins Shared Library Reference</h3>"
        + pipeline_table
    )


def section_swagger_api() -> str:
    endpoint_table = (
        "<table>"
        + tr(th("Endpoint Group"), th("Path Prefix"), th("Key Operations"))
        + tr(
            td("<strong>BOM / SBOM Upload</strong>"),
            td("<code>/api/v1/bom</code>"),
            td("Upload a CycloneDX or SPDX BOM; poll processing status"),
            bg="#f8fafc",
        )
        + tr(
            td("<strong>Projects</strong>"),
            td("<code>/api/v1/project</code>"),
            td("Create, update, delete, tag, and search projects; manage versions and parent/child relationships"),
        )
        + tr(
            td("<strong>Findings / Vulnerabilities</strong>"),
            td("<code>/api/v1/finding</code>"),
            td("List all findings for a project; export as FPF or SARIF; summary counts by severity"),
            bg="#f8fafc",
        )
        + tr(
            td("<strong>Analysis</strong>"),
            td("<code>/api/v1/analysis</code>"),
            td("Read and write analysis state, justification, comments, suppression — programmatic triage"),
        )
        + tr(
            td("<strong>Vulnerability</strong>"),
            td("<code>/api/v1/vulnerability</code>"),
            td("Look up a specific CVE; list all vulns for a component; source feed status"),
            bg="#f8fafc",
        )
        + tr(
            td("<strong>Component</strong>"),
            td("<code>/api/v1/component</code>"),
            td("Search components across the portfolio; resolve package URLs; identify all projects affected by a component"),
        )
        + tr(
            td("<strong>Policies</strong>"),
            td("<code>/api/v1/policy</code>"),
            td("Create and manage licence and severity policies; list violations"),
            bg="#f8fafc",
        )
        + tr(
            td("<strong>Notifications</strong>"),
            td("<code>/api/v1/notification</code>"),
            td("Configure Slack, e-mail, webhook, and MS Teams alert subscriptions"),
        )
        + tr(
            td("<strong>Metrics</strong>"),
            td("<code>/api/v1/metrics</code>"),
            td("Portfolio-level and per-project risk scores; trend data over time"),
            bg="#f8fafc",
        )
        + "</table>"
    )

    return (
        "<h2>9. API Explorer — Swagger UI</h2>"
        "<p>Dependency-Track ships with a built-in <strong>Swagger / OpenAPI UI</strong> "
        "that gives you an interactive, browser-based explorer for every endpoint the platform "
        "exposes. It is the fastest way to understand what is possible and to prototype "
        "integrations before writing code.</p>"
        + info_panel(
            "Open <code>http://&lt;your-dt-host&gt;/api/swagger-ui/</code> in a browser. "
            "Click <strong>Authorize</strong> in the top-right, enter your API key "
            "(from Administration → Access Management → API Keys), and every endpoint "
            "becomes executable directly from the browser.",
            title="Accessing the Swagger UI",
        )
        + "<h3>What You Can Explore</h3>"
        + endpoint_table
        + "<h3>Practical Uses of the Swagger UI</h3>"
        + ul(
            "<strong>Prototype automations</strong> — try an endpoint interactively before writing "
            "a Jenkins step or script",
            "<strong>Debug uploads</strong> — POST a BOM directly and inspect the raw JSON response",
            "<strong>Bulk triage</strong> — use the <code>PUT /api/v1/analysis</code> endpoint to "
            "set analysis state across many findings from a script",
            "<strong>Build dashboards</strong> — <code>GET /api/v1/metrics/portfolio</code> returns "
            "live counts suitable for Grafana or a custom status page",
            "<strong>Impact analysis</strong> — <code>GET /api/v1/component/identity</code> with a "
            "package URL instantly shows every project that includes a component",
            "<strong>Policy automation</strong> — create licence policies via "
            "<code>POST /api/v1/policy</code> and wire them to break-build notifications",
        )
        + tip_panel(
            "The full OpenAPI specification (<code>dependencytrack-openapi.yaml</code>) is also "
            "available in this repository. Import it into Postman, Insomnia, or any REST client "
            "for a complete offline API reference with saved example requests.",
            title="OpenAPI Spec in this Repository",
        )
        + note_panel(
            "All pipeline operations in this project — SBOM upload, project creation, findings "
            "export, analysis recording — use the same REST API the Swagger UI exposes. "
            "If something is in the UI it can also be automated.",
            title="Everything in the UI is in the API",
        )
        + "<h3>Integration Ecosystem</h3>"
        + "<p>The Dependency-Track REST API enables integration with ticketing systems (Jira), "
        "SIEMs (Splunk, Elasticsearch), and executive dashboards — giving full visibility "
        "from developer laptop to boardroom. Any tool that can make an HTTP request can "
        "integrate with Dependency-Track.</p>"
        + (
            "<table>"
            + tr(th("Integration"), th("API Endpoint(s) Used"), th("What It Enables"))
            + tr(
                td("<strong>Jira / Ticketing</strong>"),
                td("<code>GET /api/v1/finding/{project}</code><br><code>POST /api/v1/analysis</code>"),
                td("Auto-create Jira issues for Critical/High findings; sync analysis state back when tickets are resolved"),
                bg="#f8fafc",
            )
            + tr(
                td("<strong>Splunk / Elasticsearch</strong>"),
                td("<code>GET /api/v1/finding/{project}</code><br>Notification webhooks"),
                td("Stream vulnerability events and analysis decisions into your SIEM for correlation, alerting, and compliance reporting"),
            )
            + tr(
                td("<strong>Grafana Dashboards</strong>"),
                td("<code>GET /api/v1/metrics/portfolio</code><br><code>GET /api/v1/metrics/project/{uuid}</code>"),
                td("Pull live risk scores and trend data into Grafana panels for real-time executive-level visibility"),
                bg="#f8fafc",
            )
            + tr(
                td("<strong>MS Teams / Slack</strong>"),
                td("<code>POST /api/v1/notification/publisher</code>"),
                td("Configure webhook notifications for new Critical or High findings so the right team is alerted immediately"),
            )
            + tr(
                td("<strong>PagerDuty / OpsGenie</strong>"),
                td("Outbound webhook from notification rules"),
                td("Trigger on-call alerts when newly introduced Critical vulnerabilities are detected in production-bound builds"),
                bg="#f8fafc",
            )
            + tr(
                td("<strong>Custom / Executive Dashboards</strong>"),
                td("<code>GET /api/v1/metrics/portfolio</code><br><code>GET /api/v1/project</code>"),
                td("Schedule daily metrics exports; feed bespoke reporting tools or management dashboards with live risk data"),
            )
            + "</table>"
        )
        + info_panel(
            "Dependency-Track also supports outbound notifications via "
            "<strong>Slack, MS Teams, e-mail, and generic webhooks</strong> — all configurable "
            "from Administration &#8594; Notifications. Each notification can be scoped to specific "
            "projects, portfolios, or severity levels so the right team gets exactly the signal they need.",
            title="Built-in Notification Channels",
        )
    )


def section_benefits() -> str:
    benefits = [
        ("#1e3a8a", "&#128270;", "Complete Visibility",
         "Every dependency &#8212; direct and transitive &#8212; is inventoried. "
         "No blind spots in your software supply chain."),
        ("#06747c", "&#128161;", "Continuous Monitoring",
         "New CVEs are automatically matched against your component inventory. "
         "Updates arrive as soon as vulnerability feeds refresh &#8212; no manual scans."),
        ("#7c3aed", "&#9989;", "Structured Triage",
         "Analysis states, analyst comments, and suppression give every security decision "
         "a governed, auditable home inside the platform."),
        ("#d97706", "&#128196;", "Automated Reporting",
         "Shareable PDF reports (vulnerability &#38; SBOM) generated automatically on every build. "
         "No manual export effort required."),
        ("#b91c1c", "&#128640;", "Shift-Left Security",
         "Maven builds upload SBOMs at build time &#8212; vulnerabilities surface during development, "
         "not after production deployment."),
        ("#15803d", "&#128737;", "Policy Enforcement",
         "Define severity thresholds and licence rules. Violations break the build before "
         "bad dependencies ever reach a release artefact."),
        ("#0ea5e9", "&#127760;", "Polyglot Coverage",
         "Maven, Node.js, Python, Go, Docker images &#8212; cdxgen handles all ecosystems "
         "with a single Jenkins shared-library step."),
        ("#6b7280", "&#128295;", "REST API &#38; Integrations",
         "Full headless API enables Jira, Splunk, Grafana, and custom tooling integrations. "
         "Every UI action is automatable."),
        ("#1e3a8a", "&#128100;", "Audit-Ready",
         "Every analysis state change, comment, and suppression is timestamped and attributed. "
         "Compliance evidence is generated as a byproduct of normal work."),
    ]

    cards = ""
    for colour, icon, title, desc in benefits:
        cards += (
            f'<div style="border-top:4px solid {colour};background:#f8fafc;padding:1rem 1.25rem;'
            f'border-radius:6px;box-shadow:0 1px 3px rgba(0,0,0,.07);">'
            f'<div style="font-size:1.6rem;line-height:1;margin-bottom:.5rem;">{icon}</div>'
            f'<p style="margin:0 0 .35rem;font-weight:700;color:{colour};font-size:.95rem;">{title}</p>'
            f'<p style="margin:0;font-size:.88rem;color:#374151;line-height:1.5;">{desc}</p>'
            f'</div>'
        )

    grid = (
        '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));'
        'gap:1rem;margin:1.5rem 0;">'
        + cards
        + '</div>'
    )

    return (
        "<h2>10. Benefits Summary</h2>"
        "<p>Adopting the SBOM pipeline and Dependency-Track gives engineering, security, "
        "and compliance teams a single, continuous view of software risk &#8212; with no "
        "manual overhead.</p>"
        + grid
        + tip_panel(
            "The Dependency-Track REST API enables integration with ticketing systems "
            "(Jira), SIEMs (Splunk, Elasticsearch), and executive dashboards &#8212; giving "
            "full visibility from developer laptop to boardroom.",
            title="Integration Ecosystem",
        )
    )


# ── Assemble and write ─────────────────────────────────────────────────────


def build_confluence_page(out_path: str = "SBOM_DependencyTrack_Confluence.html") -> None:
    body = (
        section_intro()
        + section_what_is_sbom()
        + section_sbom_generation()
        + section_dt_overview()
        + section_vuln_workflow()
        + section_analysis_actions()
        + section_reporting()
        + section_pipeline()
        + section_swagger_api()
        + section_benefits()
    )

    # Wrap in a minimal HTML shell so the file can also be previewed in a browser
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>SBOM &amp; Vulnerability Management with Dependency-Track</title>
  <style>
    body  {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
             max-width: 1100px; margin: 0 auto; padding: 2rem; color: #0f172a; }}
    h1   {{ color: #1e3a8a; border-bottom: 3px solid #1e3a8a; padding-bottom: .4rem; }}
    h2   {{ color: #1e3a8a; margin-top: 2rem; }}
    h3   {{ color: #06747c; }}
    code {{ background: #f1f5f9; padding: 1px 5px; border-radius: 3px; font-size: .92em; }}
    pre  {{ background: #1e293b; color: #e2e8f0; padding: 1rem; border-radius: 6px;
            overflow-x: auto; }}
    table{{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
    th, td {{ border: 1px solid #e2e8f0; vertical-align: top; }}
    ul, ol {{ margin: .5rem 0 .5rem 1.5rem; }}
    li   {{ margin: .25rem 0; }}
    /* Confluence macro approximations */
    ac\\:structured-macro[ac\\:name="info"]    {{ display:block; background:#e8f4fd;
        border-left:4px solid #1976d2; padding:.75rem 1rem; margin:.75rem 0; border-radius:4px; }}
    ac\\:structured-macro[ac\\:name="note"]    {{ display:block; background:#fff8e1;
        border-left:4px solid #f9a825; padding:.75rem 1rem; margin:.75rem 0; border-radius:4px; }}
    ac\\:structured-macro[ac\\:name="warning"] {{ display:block; background:#fce4ec;
        border-left:4px solid #c62828; padding:.75rem 1rem; margin:.75rem 0; border-radius:4px; }}
    ac\\:structured-macro[ac\\:name="tip"]     {{ display:block; background:#e8f5e9;
        border-left:4px solid #2e7d32; padding:.75rem 1rem; margin:.75rem 0; border-radius:4px; }}
  </style>
</head>
<body>
<h1>SBOM &amp; Vulnerability Management with Dependency-Track</h1>
{body}
</body>
</html>"""

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Saved: {out_path}")
    print(
        "\nTo import into Confluence:\n"
        "  Option A: Edit page → Insert → Markup → Confluence Storage Format\n"
        "            Paste the content between <body> tags (the Confluence macros\n"
        "            are in storage format and will render natively).\n"
        "  Option B: Use the Confluence REST API:\n"
        "            curl -u user:token -X POST '<base>/rest/api/content' \\\n"
        "              -H 'Content-Type: application/json' \\\n"
        "              -d '{\"type\":\"page\",\"title\":\"SBOM & Vulnerability Management\",\n"
        "                   \"space\":{\"key\":\"YOUR_SPACE\"},\n"
        "                   \"body\":{\"storage\":{\"value\":\"<paste body here>\",\n"
        "                   \"representation\":\"storage\"}}}'"
    )


if __name__ == "__main__":
    build_confluence_page()
