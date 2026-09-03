#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# ELK Stack SBOM Generator
#
# Generates CycloneDX SBOMs for the ELK stack from source code using cdxgen.
# Auto-detects build systems (Maven, Gradle, Go, Node.js) per component.
#
# Usage:
#   VERSION=9.5.2 ./generate-sboms.sh
#   VERSION=9.5.2 COMPONENTS="elasticsearch logstash" ./generate-sboms.sh
#   DRY_RUN=1 VERSION=9.5.2 ./generate-sboms.sh
# =============================================================================

# === Configuration ===
VERSION="${VERSION:-9.5.2}"
BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
REPOS_DIR="${BASE_DIR}/repos"
OUTPUT_DIR="${BASE_DIR}/sbom-output"
CDXGEN_IMAGE="${CDXGEN_IMAGE:-ghcr.io/cdxgen/cdxgen:latest}"
CDXGEN_JAVA_IMAGE="${CDXGEN_JAVA_IMAGE:-ghcr.io/cdxgen/cdxgen-temurin-java26:v13}"
SPEC_VERSION="${SPEC_VERSION:-1.6}"
TIMEOUT_MS="${TIMEOUT_MS:-180000}"
DRY_RUN="${DRY_RUN:-0}"

# Components to scan — override with COMPONENTS="elasticsearch logstash"
ALL_COMPONENTS="elasticsearch kibana beats logstash"
COMPONENTS="${COMPONENTS:-$ALL_COMPONENTS}"

# === Logging ===
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

log_ok() {
    log "OK: $*"
}

log_fail() {
    log "FAIL: $*"
}

log_skip() {
    log "SKIP: $*"
}

# === Phase 1: Clone ===
clone_repo() {
    local name="$1"
    local url="$2"
    local dest="${REPOS_DIR}/${name}"

    if [ -d "$dest/.git" ]; then
        log_skip "$name already cloned at $dest"
        return 0
    fi

    log "Cloning $name (tag v${VERSION})..."
    if [ "$DRY_RUN" -eq 1 ]; then
        log "  DRY RUN: git clone --depth 1 --branch v${VERSION} ${url} ${dest}"
        return 0
    fi

    git clone --depth 1 --branch "v${VERSION}" "$url" "$dest" 2>&1
}

clone_all_repos() {
    log "=== Phase 1: Cloning repositories ==="

    clone_repo "elasticsearch" "https://github.com/elastic/elasticsearch.git"
    clone_repo "kibana"        "https://github.com/elastic/kibana.git"
    clone_repo "beats"         "https://github.com/elastic/beats.git"
    clone_repo "logstash"      "https://github.com/elastic/logstash.git"

    log "Clone phase complete."
}

# === Phase 2: Build System Detection ===
detect_build_system() {
    local dir="$1"

    if [ -f "$dir/build.gradle" ] || [ -f "$dir/build.gradle.kts" ]; then
        echo "gradle"
    elif [ -f "$dir/pom.xml" ]; then
        echo "maven"
    elif [ -f "$dir/go.mod" ]; then
        echo "go"
    elif [ -f "$dir/package.json" ]; then
        echo "nodejs"
    elif [ -f "$dir/Gemfile" ]; then
        echo "ruby"
    else
        echo "unknown"
    fi
}

# === Phase 3: Scan ===
run_cdxgen() {
    local name="$1"
    local repo_dir="$2"
    local scan_path="$3"
    local output_file="$4"
    local extra_env="$5"
    local image="$6"

    local full_scan_path="${repo_dir}/${scan_path}"
    local build_type
    build_type=$(detect_build_system "$full_scan_path")

    log "  Detected build system: $build_type"

    # Pick the right image — Java 26 for Maven/Gradle, default for others
    local use_image="$image"
    case "$build_type" in
        maven|gradle)
            use_image="${CDXGEN_JAVA_IMAGE}"
            ;;
    esac

    # Build docker run command
    local cmd=(
        docker run --rm --network=host
        -v "${repo_dir}:/src:ro"
        -v "${OUTPUT_DIR}:/out"
        -e "CDXGEN_TIMEOUT_MS=${TIMEOUT_MS}"
    )

    # Add extra env vars
    if [ -n "$extra_env" ]; then
        IFS=',' read -ra ENVS <<< "$extra_env"
        for env in "${ENVS[@]}"; do
            cmd+=(-e "$env")
        done
    fi

    # Build system specific env
    case "$build_type" in
        gradle)
            cmd+=(
                -e "GRADLE_CMD=./gradlew"
                -e "GRADLE_USE_DAEMON=false"
                -e "GRADLE_STOP_DAEMON=false"
            )
            ;;
        go)
            cmd+=(-e "GOFLAGS=-mod=mod")
            ;;
        nodejs)
            cmd+=(-e "NODE_OPTIONS=--max-old-space-size=4096")
            ;;
    esac

    cmd+=(
        "$use_image"
        -r -o "/out/${output_file}"
        --spec-version "$SPEC_VERSION"
        "/src/${scan_path}"
    )

    if [ "$DRY_RUN" -eq 1 ]; then
        log "  DRY RUN: ${cmd[*]}"
        return 0
    fi

    log "  Running: cdxgen -> ${output_file}"
    "${cmd[@]}" 2>&1
}

scan_with_retry() {
    local name="$1"
    local repo_dir="$2"
    local scan_path="$3"
    local output_file="$4"
    local extra_env="${5:-}"
    local image="${6:-$CDXGEN_IMAGE}"

    # Attempt 1
    log "Scanning $name (attempt 1)..."
    if run_cdxgen "$name" "$repo_dir" "$scan_path" "$output_file" "$extra_env" "$image"; then
        # Validate output exists and has content
        if [ -f "${OUTPUT_DIR}/${output_file}" ] && [ -s "${OUTPUT_DIR}/${output_file}" ]; then
            log_ok "$name scan succeeded (attempt 1)"
            return 0
        fi
        log_fail "$name scan produced empty output (attempt 1)"
    fi

    # Attempt 2
    log "Scanning $name (attempt 2)..."
    if run_cdxgen "$name" "$repo_dir" "$scan_path" "$output_file" "$extra_env" "$image"; then
        if [ -f "${OUTPUT_DIR}/${output_file}" ] && [ -s "${OUTPUT_DIR}/${output_file}" ]; then
            log_ok "$name scan succeeded (attempt 2)"
            return 0
        fi
        log_fail "$name scan produced empty output (attempt 2)"
    fi

    # Fallback: Docker image scan
    log_fail "$name source scan failed twice, falling back to Docker image scan"
    scan_docker_fallback "$name"
}

scan_docker_fallback() {
    local name="$1"
    local docker_image="docker.elastic.co/${name}/${name}:${VERSION}"

    # Beats is special — filebeat/metricbeat live under docker.elastic.co/beats/
    case "$name" in
        filebeat|metricbeat)
            docker_image="docker.elastic.co/beats/${name}:${VERSION}"
            ;;
    esac

    log "  Fallback: scanning Docker image ${docker_image}"

    if [ "$DRY_RUN" -eq 1 ]; then
        log "  DRY RUN: cdxgen -t docker ${docker_image}"
        return 0
    fi

    docker run --rm --network=host \
        -v "${OUTPUT_DIR}:/out" \
        "$CDXGEN_IMAGE" \
        -r -o "/out/${name}-sbom.json" \
        --spec-version "$SPEC_VERSION" \
        -t docker "$docker_image" 2>&1 || {
            log_fail "$name Docker fallback also failed"
            return 1
        }

    log_ok "$name Docker fallback scan succeeded"
}

# === Component Scan Definitions ===
scan_elasticsearch() {
    log "--- Elasticsearch (Maven/Java) ---"
    scan_with_retry \
        "elasticsearch" \
        "${REPOS_DIR}/elasticsearch" \
        "" \
        "elasticsearch-sbom.json"
}

scan_kibana() {
    log "--- Kibana (Node.js/TypeScript) ---"
    scan_with_retry \
        "kibana" \
        "${REPOS_DIR}/kibana" \
        "kibana/src" \
        "kibana-sbom.json"
}

scan_filebeat() {
    log "--- Filebeat (Go) ---"
    scan_with_retry \
        "filebeat" \
        "${REPOS_DIR}/beats" \
        "filebeat" \
        "filebeat-sbom.json"
}

scan_metricbeat() {
    log "--- Metricbeat (Go) ---"
    scan_with_retry \
        "metricbeat" \
        "${REPOS_DIR}/beats" \
        "metricbeat" \
        "metricbeat-sbom.json"
}

scan_logstash() {
    log "--- Logstash (Gradle/JRuby) ---"
    scan_with_retry \
        "logstash" \
        "${REPOS_DIR}/logstash" \
        "" \
        "logstash-sbom.json"
}

# === Phase 4: Validate ===
validate_sboms() {
    log "=== Phase 3: Validating SBOMs ==="

    local pass=0
    local fail=0

    for sbom in "${OUTPUT_DIR}"/*.json; do
        [ -f "$sbom" ] || continue
        local name
        name=$(basename "$sbom")

        if python3 -c "
import json, sys
try:
    d = json.load(open('${sbom}'))
    comps = d.get('components', [])
    if len(comps) == 0:
        print('FAIL: 0 components')
        sys.exit(1)
    print(f'OK: {len(comps)} components')
except Exception as e:
    print(f'FAIL: {e}')
    sys.exit(1)
" 2>/dev/null; then
            log_ok "$name"
            ((pass++))
        else
            log_fail "$name"
            ((fail++))
        fi
    done

    log "Results: $pass passed, $fail failed"
}

# === Main ===
main() {
    log "============================================"
    log " ELK SBOM Generator"
    log " Version: $VERSION"
    log " cdxgen image: $CDXGEN_IMAGE"
    log " cdxgen java image: $CDXGEN_JAVA_IMAGE"
    log " Output: $OUTPUT_DIR"
    log " Components: $COMPONENTS"
    log "============================================"

    mkdir -p "$REPOS_DIR" "$OUTPUT_DIR"

    clone_all_repos

    log "=== Phase 2: Generating SBOMs ==="

    for component in $COMPONENTS; do
        case "$component" in
            elasticsearch) scan_elasticsearch ;;
            kibana)        scan_kibana ;;
            beats)
                scan_filebeat
                scan_metricbeat
                ;;
            filebeat)      scan_filebeat ;;
            metricbeat)    scan_metricbeat ;;
            logstash)      scan_logstash ;;
            *)
                log_fail "Unknown component: $component"
                ;;
        esac
    done

    validate_sboms

    log "============================================"
    log " Done. SBOMs are in: $OUTPUT_DIR"
    log "============================================"
}

main "$@"
