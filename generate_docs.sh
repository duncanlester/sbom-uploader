#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# generate_docs.sh
#
# Generates the SBOM / Dependency-Track PowerPoint presentation and Confluence
# page inside a Docker container — nothing needs to be installed on your machine.
#
# Prerequisites:  Docker (running)
#
# Usage:
#   ./generate_docs.sh              # generates both files (default)
#   ./generate_docs.sh pptx         # PowerPoint only
#   ./generate_docs.sh confluence   # Confluence page only
#
# Output (in ./output/):
#   SBOM_DependencyTrack_Presentation.pptx
#   SBOM_DependencyTrack_Confluence.html
# ──────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS_DIR="${SCRIPT_DIR}/resources/scripts"
OUTPUT_DIR="${SCRIPT_DIR}/output"
SCREENSHOTS_DIR="${OUTPUT_DIR}/screenshots"
TARGET="${1:-all}"

# ── Sanity checks ──────────────────────────────────────────────────────────

if ! command -v docker &>/dev/null; then
  echo "ERROR: Docker is not installed or not in PATH." >&2
  exit 1
fi

if ! docker info &>/dev/null; then
  echo "ERROR: Docker daemon is not running." >&2
  exit 1
fi

mkdir -p "${OUTPUT_DIR}" "${SCREENSHOTS_DIR}"

# ── Download Dependency-Track UI screenshots ───────────────────────────────
# These are real screenshots from the official DT GitHub repository and are
# used in the PowerPoint presentation and Confluence page.

DT_RAW="https://raw.githubusercontent.com/DependencyTrack/dependency-track/master/docs/images/screenshots"
DT_SCREENSHOTS="dashboard.png vulnerabilities.png audit-finding-project.png collection-projects-details.png vulnerability.png"

echo "  Downloading Dependency-Track screenshots..."
for img in ${DT_SCREENSHOTS}; do
  dest="${SCREENSHOTS_DIR}/${img}"
  if [ -f "${dest}" ]; then
    echo "    ✓ ${img} (cached)"
  else
    if curl -fsSL --max-time 15 "${DT_RAW}/${img}" -o "${dest}" 2>/dev/null; then
      echo "    ✓ ${img}"
    else
      echo "    ✗ ${img} (unavailable — presentation will use simulated UI)"
      rm -f "${dest}"
    fi
  fi
done
echo ""

# ── Build the command string to execute inside the container ───────────────

case "${TARGET}" in
  pptx)
    CMD="python /scripts/generate_presentation.py"
    LABEL="PowerPoint presentation"
    ;;
  confluence)
    CMD="python /scripts/generate_confluence.py && python /scripts/generate_confluence_markup.py"
    LABEL="Confluence HTML + wiki markup pages"
    ;;
  all|*)
    CMD="python /scripts/generate_presentation.py && python /scripts/generate_confluence.py && python /scripts/generate_confluence_markup.py"
    LABEL="PowerPoint + Confluence HTML + Confluence wiki markup"
    ;;
esac

# ── Run ────────────────────────────────────────────────────────────────────

echo "┌──────────────────────────────────────────────────────────────────────┐"
echo "│  SBOM & Dependency-Track — Document Generator                        │"
echo "└──────────────────────────────────────────────────────────────────────┘"
echo ""
echo "  Generating: ${LABEL}"
echo "  Output dir: ${OUTPUT_DIR}"
echo ""

docker run --rm \
  --name sbom-docgen \
  -v "${SCRIPTS_DIR}:/scripts:ro" \
  -v "${OUTPUT_DIR}:/output" \
  -v "${SCREENSHOTS_DIR}:/screenshots:ro" \
  -e SCREENSHOT_DIR=/screenshots \
  -w /output \
  python:3.11-slim \
  bash -c "
    echo '  [1/2] Installing dependencies...'
    pip install python-pptx --quiet --no-cache-dir
    echo '  [2/2] Running generators...'
    ${CMD}
  "

echo ""
echo "Done!  Output files:"
for f in "${OUTPUT_DIR}"/*.pptx "${OUTPUT_DIR}"/*.html "${OUTPUT_DIR}"/*.wiki; do
  [ -f "${f}" ] && echo "  ✓  ${f}"
done
echo ""
echo "Confluence import options:"
echo "  A) Open the .html file in a browser to preview the storage-format page."
echo "  B) Paste the .wiki file contents into Confluence via:"
echo "       Edit page → Insert → Markup → Confluence Wiki Markup"
echo "  C) For storage format: paste <body> content via:"
echo "       Edit page → Insert → Markup → Confluence Storage Format"
echo "  D) Publish either via the Confluence REST API (see script output above)."
