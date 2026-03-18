#!/usr/bin/env bash
# delete-projects.sh — delete Dependency-Track projects matching a name pattern
#
# Usage:
#   ./delete-projects.sh                        # deletes ALL projects (no filter)
#   ./delete-projects.sh -purl                  # deletes projects whose name ends in -purl
#   ./delete-projects.sh jenkins-plugin         # deletes projects whose name contains jenkins-plugin
#
# Environment variables (override defaults):
#   DT_URL      Dependency-Track base URL  (default: http://localhost:8081)
#   DT_USERNAME DT admin username           (default: admin)
#   DT_PASSWORD DT admin password           (default: password)

set -euo pipefail

API_URL="${DT_URL:-http://localhost:8081}"
USERNAME="${DT_USERNAME:-admin}"
PASSWORD="${DT_PASSWORD:-password}"
PATTERN="${1:-}"

# Obtain JWT token
TOKEN=$(curl -s -X POST "${API_URL}/api/v1/user/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=${USERNAME}&password=${PASSWORD}")

if [ -z "$TOKEN" ]; then
  echo "ERROR: failed to obtain auth token" >&2
  exit 1
fi

echo "Fetching project list..."

# DT paginates — fetch all pages
PAGE=1
PAGE_SIZE=100
ALL_PROJECTS='[]'
while true; do
  PAGE_DATA=$(curl -s "${API_URL}/api/v1/project?pageNumber=${PAGE}&pageSize=${PAGE_SIZE}&onlyRoot=false" \
    -H "Authorization: Bearer ${TOKEN}")
  PAGE_COUNT=$(echo "$PAGE_DATA" | jq 'length')
  ALL_PROJECTS=$(echo "$ALL_PROJECTS $PAGE_DATA" | jq -s '.[0] + .[1]')
  if [ "$PAGE_COUNT" -lt "$PAGE_SIZE" ]; then
    break
  fi
  PAGE=$((PAGE + 1))
done

if [ -z "$PATTERN" ]; then
  MATCHES=$(echo "$ALL_PROJECTS" | jq -r '.[] | [.uuid, .name] | @tsv')
else
  MATCHES=$(echo "$ALL_PROJECTS" | jq -r --arg pat "$PATTERN" \
    '.[] | select(.name | ascii_downcase | contains($pat | ascii_downcase)) | [.uuid, .name] | @tsv')
fi

if [ -z "$MATCHES" ]; then
  echo "No projects matched pattern '${PATTERN:-<all>}'."
  exit 0
fi

COUNT=$(echo "$MATCHES" | wc -l | tr -d ' ')
echo "Found ${COUNT} project(s) matching '${PATTERN:-<all>}':"
echo "$MATCHES" | awk -F'\t' '{ printf "  %s  %s\n", $1, $2 }'
echo

read -r -p "Delete all ${COUNT} project(s)? [y/N] " CONFIRM
if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
  echo "Aborted."
  exit 0
fi

echo "$MATCHES" | while IFS=$'\t' read -r UUID NAME; do
  echo "Deleting '${NAME}' (${UUID})..."
  HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE \
    "${API_URL}/api/v1/project/${UUID}" \
    -H "Authorization: Bearer ${TOKEN}")
  if [ "$HTTP_STATUS" -eq 204 ]; then
    echo "  OK"
  else
    echo "  WARNING: unexpected HTTP ${HTTP_STATUS}"
  fi
done

echo "Done."
