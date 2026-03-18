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

# DT paginates at 100 by default — request a large page to get everything
PROJECTS=$(curl -s "${API_URL}/api/v1/project?pageSize=1000&onlyRoot=false" \
  -H "Authorization: Bearer ${TOKEN}")

if [ -z "$PATTERN" ]; then
  MATCHES=$(echo "$PROJECTS" | jq -r '.[] | [.uuid, .name] | @tsv')
else
  MATCHES=$(echo "$PROJECTS" | jq -r --arg pat "$PATTERN" \
    '.[] | select(.name | contains($pat)) | [.uuid, .name] | @tsv')
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
