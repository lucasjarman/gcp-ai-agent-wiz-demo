#!/bin/bash
# Wiz Security Scan Nudge
# PostToolUse hook for Edit|Write — nudges developer to use /wiz-scan
# on the FIRST security-relevant file write per session. Silent after that.

set -euo pipefail

input=$(cat /dev/stdin)

# Extract the file path from tool output or input
file_path=$(echo "$input" | jq -r '.tool_input.file_path // .tool_input.filename // ""')

if [ -z "$file_path" ]; then
  exit 0
fi

# Only nudge for security-relevant files
security_relevant=false
case "$file_path" in
  *.tf|*.tfvars|*.hcl)              security_relevant=true ;;  # Terraform
  *.yaml|*.yml)                      security_relevant=true ;;  # K8s, Helm, CloudFormation, etc.
  *.json)                            security_relevant=true ;;  # CloudFormation, package.json, etc.
  *.toml)                            security_relevant=true ;;  # Cargo.toml, pyproject.toml
  *Dockerfile*|*dockerfile*)         security_relevant=true ;;  # Dockerfiles
  *docker-compose*|*compose*)        security_relevant=true ;;  # Docker Compose
  *kustomization*|*helmfile*)        security_relevant=true ;;  # K8s tooling
  *.bicep|*.pulumi*)                 security_relevant=true ;;  # Azure Bicep, Pulumi
  *requirements*.txt|*Gemfile*|*package-lock.json|*yarn.lock|*pnpm-lock.yaml|*go.sum|*Cargo.lock)
                                     security_relevant=true ;;  # Dependency manifests
  *.env|*.env.*|*credentials*|*secret*) security_relevant=true ;;  # Potentially sensitive
  *.py)                              security_relevant=true ;;  # Python (SAST)
  *.js|*.ts|*.jsx|*.tsx|*.mjs|*.cjs) security_relevant=true ;;  # JavaScript/TypeScript (SAST)
  *.java)                            security_relevant=true ;;  # Java (SAST)
  *.go)                              security_relevant=true ;;  # Go (SAST)
  *.cs|*.vb|*.fs)                    security_relevant=true ;;  # .NET/C#/VB/F# (SAST)
  *.c|*.cpp|*.cc|*.h|*.hpp)          security_relevant=true ;;  # C/C++ (SAST)
  *.clj|*.cljs|*.cljc)              security_relevant=true ;;  # Clojure (SAST)
  *.kt|*.kts)                        security_relevant=true ;;  # Kotlin (SAST)
  *.rb)                              security_relevant=true ;;  # Ruby (SAST)
  *.php)                             security_relevant=true ;;  # PHP (SAST)
  *.rs)                              security_relevant=true ;;  # Rust (SAST)
  *.swift)                           security_relevant=true ;;  # Swift (SAST)
esac

if [ "$security_relevant" != "true" ]; then
  exit 0
fi

# One nudge per session — use session_id to scope the flag
session_id=$(echo "$input" | jq -r '.session_id // "unknown"')
flag_file="/tmp/.wiz-scan-nudge-${session_id}"

if [ -f "$flag_file" ]; then
  exit 0  # Already nudged this session
fi

touch "$flag_file"

# Output the nudge as a systemMessage
jq -n '{
  "systemMessage": "Hint: Use /wiz-scan to perform a full security scan on modified files with the Wiz CLI (IaC misconfigs, secrets, SAST, CVEs, malware)."
}'

exit 0
