#!/usr/bin/env python3
"""
Generate a Confluence Wiki Markup (.wiki) file documenting the SBOM pipeline
and Dependency-Track vulnerability management workflow.

This uses the *legacy* Confluence wiki markup syntax (not storage format) which
can be pasted directly into Confluence via:
    Edit → Insert → Markup → Confluence Wiki Markup

Output: SBOM_DependencyTrack_Confluence.wiki

Usage (standalone):
    python3 generate_confluence_markup.py

Usage (via the generate_docs.sh container script – recommended):
    ./generate_docs.sh
"""

from datetime import datetime
import os
import re

# ── Real DT screenshot URLs (GitHub raw) ──────────────────────────────────
DT_RAW = (
    "https://raw.githubusercontent.com/DependencyTrack/"
    "dependency-track/master/docs/images/screenshots"
)
DT_DOCS = "https://docs.dependencytrack.org"


# ── Wiki markup helper functions ───────────────────────────────────────────

def h1(text: str) -> str:
    return f"h1. {text}\n"


def h2(text: str) -> str:
    return f"h2. {text}\n"


def h3(text: str) -> str:
    return f"h3. {text}\n"


def info(body: str, title: str = "Info") -> str:
    return f"{{info:title={title}}}\n{body}\n{{info}}\n\n"


def note(body: str, title: str = "Note") -> str:
    return f"{{note:title={title}}}\n{body}\n{{note}}\n\n"


def warning(body: str, title: str = "Warning") -> str:
    return f"{{warning:title={title}}}\n{body}\n{{warning}}\n\n"


def tip(body: str, title: str = "Tip") -> str:
    return f"{{tip:title={title}}}\n{body}\n{{tip}}\n\n"


def code(content: str, lang: str = "xml", title: str = "") -> str:
    title_part = f"|title={title}" if title else ""
    return f"{{code:language={lang}{title_part}}}\n{content}\n{{code}}\n\n"


def expand(body: str, title: str = "Show more") -> str:
    # Strip trailing whitespace from body so there's no blank line before {expand}
    return f"{{expand:title={title}}}\n{body.rstrip()}\n{{expand}}\n\n"


def status_badge(colour: str, title: str) -> str:
    # {status} macros use | as param separators which breaks table cell parsing.
    # Use {color:X}*text*{color} instead — safe in all contexts.
    _colour_map = {
        "Green":  "green",
        "Blue":   "blue",
        "Red":    "red",
        "Yellow": "darkorange",
        "Grey":   "gray",
    }
    c = _colour_map.get(colour, "gray")
    return f"{{color:{c}}}*{title}*{{color}}"


def screenshot(filename: str, width: int = 700, alt: str = "") -> str:
    url = f"{DT_RAW}/{filename}"
    return f"!{url}|width={width},alt={alt}!\n\n"


def toc() -> str:
    return "{toc:maxLevel=3|style=disc|minLevel=2}\n\n"


def hr() -> str:
    return "----\n\n"


def ul(*items) -> str:
    return "\n".join(f"* {item}" for item in items) + "\n\n"


def ol(*items) -> str:
    return "\n".join(f"# {item}" for item in items) + "\n\n"


def table_row(*cells, header: bool = False) -> str:
    sep = "||" if header else "|"
    return sep + sep.join(cells) + sep + "\n"


# ── Page sections ─────────────────────────────────────────────────────────

def section_intro() -> str:
    now = datetime.now().strftime("%d %B %Y")
    return (
        h1("SBOM Pipeline & Vulnerability Management with Dependency-Track")
        + info(
            f"*Document Owner:* Platform Engineering Team | "
            f"*Last Updated:* {now} | "
            f"*Status:* {status_badge('Green', 'ACTIVE')}",
            title="Document Information",
        )
        + "This page describes the end-to-end Software Bill of Materials (SBOM) "
        "pipeline that automatically generates, uploads, and tracks vulnerabilities "
        "across all managed repositories using "
        "[Dependency-Track|https://dependencytrack.org].\n\n"
        + toc()
    )


def section_what_is_sbom() -> str:
    return (
        h2("What is an SBOM?")
        + "A *Software Bill of Materials (SBOM)* is a formal, machine-readable "
        "inventory of every component, library, and dependency within a software "
        "product — along with their versions, licences, and known vulnerabilities.\n\n"
        + ul(
            "*Transparency* — know exactly what is inside every artefact",
            "*Compliance* — satisfy regulatory and supply-chain audit requirements",
            "*Risk Reduction* — identify and remediate vulnerabilities proactively",
            "*Licence Governance* — detect licence conflicts before they reach production",
            "*Faster Response* — immediately know which projects are affected when a new CVE is published",
        )
        + note(
            "The [CycloneDX|https://cyclonedx.org] format is used throughout this "
            "pipeline (JSON serialisation). CycloneDX is an OWASP standard and is "
            "natively supported by Dependency-Track.",
            title="SBOM Standard",
        )
    )


def section_sbom_generation() -> str:
    maven_pom = """\
<plugin>
    <groupId>org.cyclonedx</groupId>
    <artifactId>cyclonedx-maven-plugin</artifactId>
    <version>2.9.1</version>
    <configuration>
        <projectType>library</projectType>
        <schemaVersion>1.4</schemaVersion>
        <includeBomSerialNumber>true</includeBomSerialNumber>
        <includeCompileScope>true</includeCompileScope>
        <includeTestScope>false</includeTestScope>
        <includeRuntimeScope>true</includeRuntimeScope>
        <includeSystemScope>true</includeSystemScope>
        <includeProvidedScope>true</includeProvidedScope>
        <includeLicenseText>false</includeLicenseText>
        <outputFormat>all</outputFormat>
    </configuration>
    <executions>
        <execution>
            <phase>package</phase>
            <goals>
                <goal>makeAggregateBom</goal>
            </goals>
        </execution>
    </executions>
</plugin>"""

    cdxgen_example = """\
// Jenkinsfile (non-Maven project)
cdxgenRepo(
    projectName: "my-nodejs-app",
    projectVersion: "1.0.0",
    dtUrl: "https://dependencytrack.example.com",
    dtApiKey: credentials('DT_API_KEY')
)"""

    return (
        h2("SBOM Generation")
        + h3("Maven Projects")
        + "The [CycloneDX Maven Plugin|https://github.com/CycloneDX/cyclonedx-maven-plugin] "
        "is added to the project POM. It runs automatically during the *package* phase "
        "and outputs a CycloneDX JSON SBOM at `target/bom.json`.\n\n"
        + code(maven_pom, lang="xml", title="pom.xml — CycloneDX Maven Plugin")
        + h3("Non-Maven Projects (cdxgen)")
        + "For Node.js, Python, Go, and other ecosystems the "
        "[cdxgen|https://github.com/CycloneDX/cdxgen] tool runs inside a Docker "
        "container as a Jenkins pipeline step — no installation required.\n\n"
        + code(cdxgen_example, lang="groovy", title="Jenkinsfile — cdxgenRepo shared library step")
        + tip(
            "cdxgen supports over 20 package ecosystems including npm, pip, Gradle, "
            "Go modules, Cargo, and more. The Jenkins shared library "
            "(`vars/cdxgenRepo.groovy`) abstracts the Docker invocation.",
            title="Multi-Language Support",
        )
        + h3("Docker / Container Images (Syft + Grype)")
        + "*Syft* (Anchore) scans Docker image layers to generate a container SBOM, capturing "
        "every OS package and language library baked into the image. "
        "*Grype* (also Anchore) consumes the Syft SBOM for immediate vulnerability triage.\n\n"
        + ul(
            "Scans a pulled or locally built Docker image via the `syftImage()` shared-library step",
            "Identifies OS packages (Alpine/Debian/RHEL) *and* language libraries inside the image",
            "Outputs CycloneDX JSON — uploads to Dependency-Track via `uploadSBOM()`",
            "Run `grypeScan()` immediately after to get a pre-upload vulnerability report",
        )
        + h3("SBOM Generation Tools — Summary")
        + table_row("Tool", "Type", "Use Case", "Jenkins Step", header=True)
        + table_row("*cdxgen*",                      "SBOM Generator",       "Polyglot — Java, Node.js, Python, Go, .NET, Ruby, Cargo & more",     "`cdxgenRepo()`")
        + table_row("*CycloneDX Maven Plugin*",       "SBOM Generator",       "Java/Maven — exact resolved-dependency-tree SBOM at build time",     "Auto via `mvn package`")
        + table_row("*Syft (Anchore)*",               "SBOM Generator",       "Docker/container images — scans image layers",                        "`syftImage()`")
        + table_row("*Grype (Anchore)*",              "Vuln Scanner",         "Consumes a Syft/cdxgen SBOM; pre-upload vulnerability triage",        "`grypeScan()`")
        + table_row("*CycloneDX Gradle/Node/.NET*",   "SBOM Generator",       "Ecosystem-specific build plugins for Gradle, npm, and .NET SDK",      "Language-native")
        + "\n"
    )


def section_dt_overview() -> str:
    return (
        h2("Dependency-Track Overview")
        + screenshot("dashboard.png", width=700, alt="Dependency-Track Portfolio Dashboard")
        + "Dependency-Track is an OWASP flagship project that provides a continuous "
        "component analysis platform. Once an SBOM is uploaded it:\n\n"
        + ol(
            "Parses every component and resolves it against its package ecosystem",
            "Queries vulnerability intelligence sources (NVD, OSV, GitHub Advisories, VulnDB)",
            "Calculates inherited risk for each project and component",
            "Surfaces findings in a searchable, filterable dashboard",
            "Triggers policy violations for licence and version rules",
        )
        + screenshot("collection-projects-details.png", width=700, alt="Collection Project Detail")
        + h3("Key Capabilities")
        + table_row("Capability", "Description", header=True)
        + table_row("Portfolio Dashboard", "Aggregate risk view across all projects")
        + table_row("Policy Engine", "Enforce licence, severity, and CVSS threshold rules")
        + table_row("VEX / Analysis", "Record analyst decisions against each finding")
        + table_row("Notifications", "Webhook, e-mail, and Slack alerts on new findings")
        + table_row("REST API", "Full programmatic access — CI/CD and SIEM integration")
        + "\n"
        + h3("Vulnerability Intelligence Sources")
        + "Dependency-Track queries the following feeds automatically. "
        "New vulnerabilities are matched against your entire component inventory "
        "the moment a feed refreshes — no manual CVE searching required.\n\n"
        + table_row("Source", "Maintained By", "Scope", "Notes", header=True)
        + table_row("*NVD* — National Vulnerability Database",  "NIST",              "All languages & ecosystems",            "Canonical CVE registry with CVSS v2/v3/v4. Primary authoritative source.")
        + table_row("*OSV* — Open Source Vulnerabilities",       "Google",            "PyPI, npm, Maven, Go, Cargo, Gems",     "Open DB with precise package-URL matching; often earlier disclosure than NVD.")
        + table_row("*GitHub Advisory Database*",               "GitHub / community", "GitHub-hosted packages",                "Curated advisories tied directly to package versions; highly accurate matching.")
        + table_row("*Sonatype OSS Index*",                     "Sonatype",          "Maven Central, npm",                    "Component intelligence with licence metadata; strong Java coverage.")
        + table_row("*VulnDB*",                                  "Risk Based Security","All ecosystems",                       "Optional commercial feed — broader coverage and earlier disclosure than NVD.")
        + "\n"
        + info(
            "All feeds are queried automatically by Dependency-Track on a rolling schedule. "
            "You can also trigger an immediate re-analysis via the UI or REST API "
            "(`PUT /api/v1/project/<uuid>/metrics/current`) after a feed update.",
            title="Automatic Feed Refresh",
        )
    )


def section_vuln_workflow() -> str:
    return (
        h2("Vulnerability Triage Workflow")
        + screenshot("vulnerabilities.png", width=700, alt="Vulnerability Findings List")
        + "When a new SBOM is uploaded Dependency-Track immediately analyses all "
        "components and surfaces findings. The recommended triage process:\n\n"
        + ol(
            "*Review* — open the Findings tab for the project and review by severity (Critical first)",
            "*Investigate* — click a finding to see CVE details, CVSS vector, affected versions, and fix version",
            "*Analyse* — record an analysis state and justification (see below)",
            "*Remediate or Suppress* — update the dependency version or suppress with documented reason",
            "*Verify* — re-run the pipeline; the finding should clear once the fixed version is uploaded",
        )
        + h3("Analysis States")
        + table_row("State", "Colour", "Meaning", header=True)
        + table_row(status_badge("Green",  "NOT_AFFECTED"),   "Green",  "Component is present but the vulnerability does not apply in this context")
        + table_row(status_badge("Blue",   "IN_TRIAGE"),      "Blue",   "Under active investigation — do not suppress yet")
        + table_row(status_badge("Red",    "EXPLOITABLE"),    "Red",    "Confirmed exploitable — remediation required")
        + table_row(status_badge("Yellow", "FALSE_POSITIVE"), "Yellow", "Incorrect match by the scanner — documented and suppressed")
        + table_row(status_badge("Grey",   "NOT_SET"),        "Grey",   "Default — no analysis recorded yet")
        + "\n"
        + note(
            "All state changes are immutable and timestamped. The full audit trail "
            "is available via the REST API and visible in the Finding detail panel.",
            title="Audit Trail",
        )
    )


def section_analysis_actions() -> str:
    example_comment = (
        "CVSS 9.8 — dependency is included in the WAR but the vulnerable endpoint "
        "(/admin/actuator) is blocked at the network perimeter (WAF rule WAF-042). "
        "Risk accepted pending upgrade to 3.2.1 in Q3 sprint. "
        "Owner: platform-team@example.com"
    )

    return (
        h2("Recording Analysis & Comments")
        + screenshot("audit-finding-project.png", width=700, alt="Audit Finding Panel")
        + "The Analysis panel in Dependency-Track lets each team record a *structured* "
        "decision against every finding. This replaces informal spreadsheet tracking "
        "with a searchable, API-queryable audit log.\n\n"
        + h3("Analysis Fields")
        + ul(
            "*State* — one of: NOT_AFFECTED, IN_TRIAGE, EXPLOITABLE, FALSE_POSITIVE",
            "*Justification* — controlled vocabulary: CODE_NOT_REACHABLE, PROTECTED_BY_MITIGATING_CONTROL, etc.",
            "*Response* — WILL_NOT_FIX, UPDATE, ROLLBACK, WORKAROUND_AVAILABLE, etc.",
            "*Detail* — free-text comment with full context (who, what, why, when)",
            "*Suppressed* — hides the finding from the active list once analysed",
        )
        + h3("Example Analysis Comment")
        + expand(
            code(example_comment, lang="none", title="Example analyst comment"),
            title="Show example comment",
        )
        + tip(
            "All comments and state changes are propagated to *all* projects that "
            "share the same component version — so you only need to analyse once.",
            title="Analysis Propagation",
        )
    )


def section_reporting() -> str:
    vuln_table = (
        table_row("CVE", "Severity", "Component", "Version", "Fix Version", "Status", header=True)
        + table_row("CVE-2021-44228", status_badge("Red", "CRITICAL"), "log4j-core", "2.14.1", "2.17.1", status_badge("Green", "PATCHED"))
        + table_row("CVE-2022-42003", status_badge("Yellow", "HIGH"), "jackson-databind", "2.13.2", "2.13.4.1", status_badge("Blue", "IN_TRIAGE"))
        + table_row("CVE-2023-34062", status_badge("Yellow", "HIGH"), "reactor-netty-http", "1.0.38", "1.0.39", status_badge("Green", "NOT_AFFECTED"))
    )

    return (
        h2("Reporting")
        + "The Jenkins pipeline generates two PDF reports on every build:\n\n"
        + h3("Security Analysis Report")
        + "Lists all current findings from Dependency-Track with analysis state, "
        "suppression flag, and analyst comments. Grouped by project and severity.\n\n"
        + "Sample findings:\n\n"
        + vuln_table
        + "\n"
        + h3("SBOM Component Report")
        + "A full inventory of every component, its version, package URL, and "
        "applicable licences — suitable for regulatory submissions and supply-chain audits.\n\n"
        + note(
            "Both reports are archived as Jenkins build artefacts and can be "
            "downloaded from the build history at any time.",
            title="Report Archiving",
        )
    )


def section_pipeline() -> str:
    shared_lib_table = (
        table_row("Library Step", "File", "Purpose", header=True)
        + table_row("`uploadSBOM`",              "`vars/uploadSBOM.groovy`",              "PUT project, resolve UUID, POST BOM to `/api/v1/bom`")
        + table_row("`cdxgenRepo`",              "`vars/cdxgenRepo.groovy`",              "Run cdxgen in Docker; supports Java-specific image variant")
        + table_row("`createDTCollectionProject`","`vars/createDTCollectionProject.groovy`","Create or update a collection (parent) project with child aggregation")
        + table_row("`exportDTReport`",          "`vars/exportDTReport.groovy`",          "Download findings report for a single project via REST API")
        + table_row("`exportAllDTReports`",      "`vars/exportAllDTReports.groovy`",      "Iterate all DT projects and export findings in bulk")
        + table_row("`fetchAllDTProjects`",      "`vars/fetchAllDTProjects.groovy`",      "Return all project UUIDs from the DT portfolio")
        + table_row("`grypeScan`",               "`vars/grypeScan.groovy`",               "Run Grype OCI image scan and upload results to DT")
        + table_row("`syftImage`",               "`vars/syftImage.groovy`",               "Generate SBOM from a Docker image layer using Syft")
        + table_row("`listJenkinsPlugins`",      "`vars/listJenkinsPlugins.groovy`",      "Export Jenkins plugin list as a CycloneDX SBOM")
        + table_row("`uploadPluginSBOMs`",       "`vars/uploadPluginSBOMs.groovy`",       "Batch-upload plugin SBOMs to Dependency-Track")
    )

    pipeline_snippet = """\
// Jenkinsfile.java — upload SBOM after Maven build
pipeline {
    stages {
        stage('Build & SBOM') {
            steps {
                sh 'mvn package -DskipTests'
                uploadSBOM(
                    projectName: env.JOB_BASE_NAME,
                    projectVersion: env.BUILD_NUMBER,
                    bomPath: 'target/bom.json',
                    dtUrl: 'https://dependencytrack.example.com',
                    dtApiKey: credentials('DT_API_KEY')
                )
            }
        }
    }
}"""

    return (
        h2("CI/CD Pipeline Integration")
        + "SBOM generation and upload happens automatically on every Jenkins build. "
        "The pipeline shared library (`vars/`) provides reusable Groovy steps that "
        "can be dropped into any Jenkinsfile.\n\n"
        + h3("Shared Library Steps")
        + shared_lib_table
        + "\n"
        + h3("Example Jenkinsfile")
        + code(pipeline_snippet, lang="groovy", title="Jenkinsfile.java — Maven + Dependency-Track upload")
        + info(
            "The `uploadSBOM` step automatically creates the project in "
            "Dependency-Track if it does not already exist, using a PUT/PATCH "
            "sequence followed by a POST to `/api/v1/bom`.",
            title="Auto-Create Projects",
        )
    )


def section_swagger_api() -> str:
    endpoint_table = (
        table_row("Endpoint Group", "Path Prefix", "Key Operations", header=True)
        + table_row("*BOM / SBOM Upload*",         "`/api/v1/bom`",           "Upload a CycloneDX or SPDX BOM; poll processing status")
        + table_row("*Projects*",                   "`/api/v1/project`",       "Create, update, delete, tag, and search projects; manage parent/child relationships")
        + table_row("*Findings / Vulnerabilities*", "`/api/v1/finding`",       "List findings for a project; export as FPF or SARIF; severity summary counts")
        + table_row("*Analysis*",                   "`/api/v1/analysis`",      "Read and write analysis state, justification, comments, suppression")
        + table_row("*Vulnerability*",              "`/api/v1/vulnerability`", "Look up a specific CVE; list vulns per component; feed status")
        + table_row("*Component*",                  "`/api/v1/component`",     "Search components; resolve package URLs; find all affected projects")
        + table_row("*Policies*",                   "`/api/v1/policy`",        "Create licence and severity policies; list violations")
        + table_row("*Notifications*",              "`/api/v1/notification`",  "Configure Slack, e-mail, webhook, and MS Teams alerts")
        + table_row("*Metrics*",                    "`/api/v1/metrics`",       "Portfolio and per-project risk scores; trend data over time")
    )

    return (
        h2("API Explorer — Swagger UI")
        + "Dependency-Track ships with a built-in *Swagger / OpenAPI UI* that gives you "
        "an interactive, browser-based explorer for every endpoint the platform exposes. "
        "It is the fastest way to understand what is possible and to prototype integrations "
        "before writing code.\n\n"
        + info(
            "Open {{http://<your-dt-host>/api/swagger-ui/}} in a browser. "
            "Click *Authorize* in the top-right, enter your API key "
            "(Administration \u2192 Access Management \u2192 API Keys), and every "
            "endpoint becomes executable directly from the browser.",
            title="Accessing the Swagger UI",
        )
        + h3("Endpoint Groups")
        + endpoint_table
        + "\n"
        + h3("Practical Uses of the Swagger UI")
        + ul(
            "*Prototype automations* \u2014 try an endpoint interactively before writing a Jenkins step or script",
            "*Debug uploads* \u2014 POST a BOM directly and inspect the raw JSON response",
            "*Bulk triage* \u2014 use {{PUT /api/v1/analysis}} to set analysis state across many findings from a script",
            "*Build dashboards* \u2014 {{GET /api/v1/metrics/portfolio}} returns live counts suitable for Grafana or a status page",
            "*Impact analysis* \u2014 {{GET /api/v1/component/identity}} with a package URL instantly shows every affected project",
            "*Policy automation* \u2014 create licence policies via {{POST /api/v1/policy}} and wire them to break-build notifications",
        )
        + tip(
            "The full OpenAPI specification ({{dependencytrack-openapi.yaml}}) is also available "
            "in this repository. Import it into Postman, Insomnia, or any REST client for a "
            "complete offline API reference with saved example requests.",
            title="OpenAPI Spec in this Repository",
        )
        + note(
            "All pipeline operations in this project \u2014 SBOM upload, project creation, findings "
            "export, analysis recording \u2014 use the same REST API the Swagger UI exposes. "
            "If something is in the UI it can also be automated.",
            title="Everything in the UI is in the API",
        )
        + h3("Integration Ecosystem")
        + "The Dependency-Track REST API enables integration with ticketing systems (Jira), "
        "SIEMs (Splunk, Elasticsearch), and executive dashboards \u2014 giving full visibility "
        "from developer laptop to boardroom. Any tool that can make an HTTP request can "
        "integrate with Dependency-Track.\n\n"
        + table_row("Integration", "API Endpoint(s) Used", "What It Enables", header=True)
        + table_row("*Jira / Ticketing*",
                    "`GET /api/v1/finding/<project>` + `POST /api/v1/analysis`",
                    "Auto-create Jira issues for Critical/High findings; sync analysis state back when tickets are resolved")
        + table_row("*Splunk / Elasticsearch*",
                    "`GET /api/v1/finding/<project>` + notification webhooks",
                    "Stream vulnerability events and analysis decisions into your SIEM for correlation, alerting, and compliance reporting")
        + table_row("*Grafana Dashboards*",
                    "`GET /api/v1/metrics/portfolio` + `GET /api/v1/metrics/project/<uuid>`",
                    "Pull live risk scores and trend data into Grafana panels for real-time executive-level visibility")
        + table_row("*MS Teams / Slack*",
                    "`POST /api/v1/notification/publisher`",
                    "Configure webhook notifications for new Critical or High findings so the right team is alerted immediately")
        + table_row("*PagerDuty / OpsGenie*",
                    "Outbound webhook from notification rules",
                    "Trigger on-call alerts when newly introduced Critical vulnerabilities are detected in production-bound builds")
        + table_row("*Custom / Executive Dashboards*",
                    "`GET /api/v1/metrics/portfolio` + `GET /api/v1/project`",
                    "Schedule daily metrics exports; feed bespoke reporting tools or management dashboards with live risk data")
        + "\n"
        + info(
            "Dependency-Track also supports outbound notifications via "
            "*Slack, MS Teams, e-mail, and generic webhooks* \u2014 all configurable from "
            "Administration \u2192 Notifications. Each notification can be scoped to specific "
            "projects, portfolios, or severity levels so the right team gets exactly the signal they need.",
            title="Built-in Notification Channels",
        )
    )


def section_benefits() -> str:
    rows = (
        table_row("Area", "Benefit", "What it means in practice", header=True)
        + table_row("(/) *Visibility*",    "*Complete Inventory*",        "Every direct and transitive dependency is known. No blind spots in the supply chain.")
        + table_row("(!) *Security*",      "*Continuous Monitoring*",     "New CVEs are matched automatically — no manual scans. Alerts arrive the moment a feed refreshes.")
        + table_row("(/) *Process*",       "*Structured Triage*",         "Analysis states, comments, and suppression give every security decision a governed, auditable home.")
        + table_row("(/) *Efficiency*",    "*Automated Reporting*",       "PDF vulnerability and SBOM reports generated on every build. No manual export effort.")
        + table_row("(!) *Engineering*",   "*Shift-Left Security*",       "SBOMs upload at build time — vulnerabilities surface during development, not after release.")
        + table_row("(x) *Compliance*",    "*Policy Enforcement*",        "Severity and licence rules break the build before bad dependencies reach a release artefact.")
        + table_row("(/) *Coverage*",      "*Polyglot Support*",          "Maven, Node.js, Python, Go, Docker images — one Jenkins shared-library step covers all ecosystems.")
        + table_row("(/) *Integration*",   "*REST API*",                  "Full headless API enables Jira, Grafana, Splunk, and custom tooling integrations.")
        + table_row("(/) *Audit*",         "*Immutable Audit Trail*",     "Every state change, comment, and suppression is timestamped and attributed. Compliance evidence as a byproduct.")
    )

    return (
        h2("Benefits Summary")
        + "Adopting the SBOM pipeline and Dependency-Track gives engineering, security, "
        "and compliance teams a single, continuous view of software risk — with no manual overhead.\n\n"
        + rows
        + "\n"
        + tip(
            "The Dependency-Track REST API enables integration with Jira, Splunk, "
            "Grafana, and executive dashboards — full visibility from developer laptop to boardroom.",
            title="Integration Ecosystem",
        )
        + hr()
        + f"_Generated on {datetime.now().strftime('%d %B %Y at %H:%M')} "
        "by the SBOM pipeline documentation generator._\n"
    )


# ── Build and write the .wiki file ─────────────────────────────────────────

def build_wiki_page():
    out_dir = os.environ.get("OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "SBOM_DependencyTrack_Confluence.wiki")

    parts = [
        section_intro(),
        hr(),
        section_what_is_sbom(),
        hr(),
        section_sbom_generation(),
        hr(),
        section_dt_overview(),
        hr(),
        section_vuln_workflow(),
        hr(),
        section_analysis_actions(),
        hr(),
        section_reporting(),
        hr(),
        section_pipeline(),
        hr(),
        section_swagger_api(),
        hr(),
        section_benefits(),
    ]

    content = "\n".join(parts)

    # Convert Markdown-style backtick inline code to Confluence wiki monospace {{...}}
    # Split on {code}...{code} blocks so we don't touch literal code block content
    code_fence = re.compile(r'(\{code[^}]*\}.*?\{code\})', re.DOTALL)
    segments = code_fence.split(content)
    processed = []
    for i, seg in enumerate(segments):
        if i % 2 == 0:  # outside a code block — convert backticks
            seg = re.sub(r'`([^`\n]+)`', r'{{\1}}', seg)
        processed.append(seg)
    content = "".join(processed)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"Saved: {out_path}")
    print()
    print("To use in Confluence:")
    print("  1. Open or create a Confluence page")
    print("  2. Click Edit → then the '...' (Insert) menu → Markup")
    print("  3. Select 'Confluence Wiki' as the markup language")
    print("  4. Paste the entire contents of SBOM_DependencyTrack_Confluence.wiki")
    print("  5. Click Insert, then Save")
    print()
    print("  Alternatively: use the Confluence REST API to create/update the page")
    print("  with the wiki content as the 'wiki' representation body.")


if __name__ == "__main__":
    build_wiki_page()
