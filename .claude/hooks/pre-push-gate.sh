#!/bin/bash
# Wiz Pre-Push Security Gate
# PreToolUse hook for Bash — intercepts `git push` commands and runs wizcli dir scan.
#
# Behavior:
#   WIZ_HOOK_MODE=audit  (default) → warn via permissionDecisionReason, allow push
#   WIZ_HOOK_MODE=block            → deny via permissionDecision, block push
#
# Fail-open: backend failures, timeouts, or wizcli errors never block the developer.
#
# Difference from pre-commit-gate.sh:
#   - Longer timeout (push is the final gate before code leaves the machine)
#   - Scans secrets, sensitive data, and malware only (other scanners disabled for speed)

set -uo pipefail

input=$(cat /dev/stdin)

# Extract the bash command being executed
cmd=$(echo "$input" | jq -r '.tool_input.command // ""')

# Only intercept git push commands (including those chained after &&, ;, ||, or |)
if [[ ! "$cmd" =~ (^|[[:space:]]|;|&|\|)git[[:space:]]+push ]]; then
  exit 0
fi

# --- Configuration ---
MODE="${WIZ_HOOK_MODE:-audit}"
INNER_TIMEOUT="${WIZ_SCAN_TIMEOUT:-100}"

export WIZ_AGENT="claude_code"
export WIZ_AGENT_TRIGGER="pre-push"
export WIZ_AGENT_VERSION="${WIZ_AGENT_VERSION:-$(claude --version 2>/dev/null | head -1 || echo "unknown")}"

# --- Check wizcli is installed ---
WIZCLI=$(command -v wizcli 2>/dev/null || true)
if [ -z "$WIZCLI" ]; then
  jq -n '{
    "systemMessage": "⚠️ Wiz CLI is not installed. Run /wizcli-setup to install and authenticate.",
    "hookSpecificOutput": {
      "hookEventName": "PreToolUse",
      "permissionDecision": "allow",
      "permissionDecisionReason": "Wiz CLI is not installed. Proceeding without security scan.",
      "additionalContext": "IMPORTANT: You MUST inform the user before continuing: Wiz CLI is not installed. Run /wizcli-setup to install and authenticate. Do NOT proceed without showing this warning."
    }
  }'
  exit 0
fi

# --- Run wizcli scan with inner timeout ---
# Use background process + kill timer for macOS/Linux portability
printf "🔍 Running Wiz security scan (pre-push)...\n" > /dev/tty 2>/dev/null || true
scan_output_file=$(mktemp)
scan_stderr_file=$(mktemp)
"$WIZCLI" scan dir . --stdout json --use-device-code --agent-version="$WIZ_AGENT_VERSION" --agent-operation="$WIZ_AGENT_TRIGGER" --by-policy-hits="BLOCK" --by-policy-hits="AUDIT" --disabled-scanners=Vulnerability,Misconfiguration,SoftwareSupplyChain,AIModels,SAST --no-publish > "$scan_output_file" 2>"$scan_stderr_file" &
scan_pid=$!
(sleep "$INNER_TIMEOUT" && kill "$scan_pid" 2>/dev/null) &
timer_pid=$!
wait "$scan_pid" 2>/dev/null
wizcli_exit=$?
kill "$timer_pid" 2>/dev/null
wait "$timer_pid" 2>/dev/null
# If the scan was killed by the timer, set exit code to 124 (matches timeout behavior)
if [ "$wizcli_exit" -eq 137 ] || [ "$wizcli_exit" -eq 143 ]; then
  wizcli_exit=124
fi
scan_output=$(cat "$scan_output_file")
rm -f "$scan_output_file" "$scan_stderr_file"

case $wizcli_exit in
  0|4)
    # 0 = success, 4 = policy failure — both produce parseable results
    ;;
  1)
    jq -n '{
      "systemMessage": "⚠️ Wiz scan: general failure. Proceeding without security scan.",
      "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "allow",
        "permissionDecisionReason": "Wiz scan: general failure. Proceeding without security scan."
      }
    }'
    exit 0
    ;;
  2)
    jq -n '{
      "systemMessage": "⚠️ Wiz scan: command error. Proceeding without security scan.",
      "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "allow",
        "permissionDecisionReason": "Wiz scan: command error. Proceeding without security scan."
      }
    }'
    exit 0
    ;;
  3)
    jq -n '{
      "systemMessage": "⚠️ Wiz CLI not authenticated. Run /wizcli-setup to authenticate.",
      "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "allow",
        "permissionDecisionReason": "Wiz CLI not authenticated. Proceeding without security scan.",
        "additionalContext": "IMPORTANT: You MUST inform the user before continuing: Wiz CLI is not authenticated. Run /wizcli-setup to authenticate. Do NOT proceed without showing this warning."
      }
    }'
    exit 0
    ;;
  5)
    jq -n '{
      "systemMessage": "⚠️ Wiz scan: not a valid git repository. Proceeding without security scan.",
      "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "allow",
        "permissionDecisionReason": "Wiz scan: not a valid git repository. Proceeding without security scan."
      }
    }'
    exit 0
    ;;
  124)
    jq -n '{
      "systemMessage": "⚠️ Wiz scan timed out. Proceeding without security scan.",
      "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "allow",
        "permissionDecisionReason": "Wiz scan timed out. Proceeding without security scan."
      }
    }'
    exit 0
    ;;
  126)
    jq -n '{
      "systemMessage": "⚠️ Wiz scan: permission denied on wizcli binary. Run: chmod +x $(command -v wizcli)",
      "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "allow",
        "permissionDecisionReason": "Wiz scan: permission denied on wizcli binary. Proceeding without security scan.",
        "additionalContext": "wizcli binary permission denied (exit 126). Suggest running: chmod +x $(command -v wizcli)"
      }
    }'
    exit 0
    ;;
  127)
    jq -n '{
      "systemMessage": "⚠️ Wiz CLI not found. Run /wizcli-setup to install and authenticate.",
      "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "allow",
        "permissionDecisionReason": "Wiz CLI not found. Proceeding without security scan.",
        "additionalContext": "IMPORTANT: You MUST inform the user before continuing: Wiz CLI is not installed. Run /wizcli-setup to install and authenticate. Do NOT proceed without showing this warning."
      }
    }'
    exit 0
    ;;
  *)
    jq -n --arg exit_code "$wizcli_exit" '{
      "systemMessage": ("⚠️ Wiz scan: unexpected error (exit " + $exit_code + "). Proceeding without security scan."),
      "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "allow",
        "permissionDecisionReason": ("Wiz scan: unexpected error (exit " + $exit_code + "). Proceeding without security scan.")
      }
    }'
    exit 0
    ;;
esac

# --- Exit code 0: check verdict before declaring clean pass ---
if [ $wizcli_exit -eq 0 ]; then
  verdict=$(echo "$scan_output" | jq -r '.status.verdict // "CLEAN"' 2>/dev/null || echo "CLEAN")
  if [ "$verdict" = "WARN_BY_POLICY" ]; then
    # Fall through to the policy-failure parsing below
    wizcli_exit=4
  else
    jq -n '{
      "systemMessage": "✅ Wiz security scan (pre-push) passed. No secrets or sensitive data found.",
      "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "allow",
        "permissionDecisionReason": "Wiz pre-push scan passed. No secrets or sensitive data found.",
        "additionalContext": "IMPORTANT: You MUST display the following to the user as a markdown blockquote before continuing:\n\n> **Wiz Security Scan (pre-push):** Passed. No secrets or sensitive data found.\n\nDo NOT skip this."
      }
    }'
    exit 0
  fi
fi

# --- Exit code 4: policy failure — parse findings ---
# Extract per-scanner severity counts from .result.analytics and build summary.
summary=$(echo "$scan_output" | jq -r '
  .result.analytics as $a |
  {
    "secrets": "Secrets",
    "malware": "Malware"
  } as $names |

  # Sensitive data is not in analytics — count directly from findings
  ([.result.dataFindings // [] | .[] | .severity] |
    { c: map(select(. == "CRITICAL")) | length,
      h: map(select(. == "HIGH")) | length,
      m: map(select(. == "MEDIUM")) | length,
      l: map(select(. == "LOW")) | length,
      i: map(select(. == "INFO")) | length }) as $df |

  [ $names | to_entries[] |
    .key as $k | .value as $label |
    $a[$k] // null |
    if . == null then empty
    else
      (.criticalCount // 0) as $c |
      (.highCount // 0) as $h |
      (.mediumCount // 0) as $m |
      (.lowCount // 0) as $l |
      (.infoCount // 0) as $i |
      if ($c + $h + $m + $l + $i) > 0 then
        "  - " + $label + ": " + ([$c, $h, $m, $l, $i] | map(tostring) | join("/"))
      else empty
      end
    end
  ] as $analytics_lines |

  (if ($df.c + $df.h + $df.m + $df.l + $df.i) > 0 then
    ["  - Sensitive Data: " + ([$df.c, $df.h, $df.m, $df.l, $df.i] | map(tostring) | join("/"))]
  else [] end) as $data_lines |

  ($analytics_lines + $data_lines) as $lines |

  ([$names | keys[] | $a[.] // {} | .criticalCount // 0] | add) + $df.c |  . as $tc |
  ([$names | keys[] | $a[.] // {} | .highCount // 0] | add) + $df.h |  . as $th |
  ([$names | keys[] | $a[.] // {} | .mediumCount // 0] | add) + $df.m | . as $tm |
  ([$names | keys[] | $a[.] // {} | .lowCount // 0] | add) + $df.l |  . as $tl |
  ([$names | keys[] | $a[.] // {} | .infoCount // 0] | add) + $df.i |  . as $ti |

  "Wiz pre-push scan found: " + ($tc|tostring) + " critical, " + ($th|tostring) + " high, " + ($tm|tostring) + " medium, " + ($tl|tostring) + " low, " + ($ti|tostring) + " info issue(s)." +
  if ($lines | length) > 0 then "\n" + ($lines | join("\n")) + "\n  (per-scanner format: critical/high/medium/low/info)"
  else ""
  end
' 2>/dev/null)

if [ -z "$summary" ]; then
  summary="Wiz pre-push scan found issues but could not parse counts."
fi

# --- Build structured findings from enabled scanners (secrets, malware) ---
findings=$(echo "$scan_output" | jq -r '
  # --- Secrets ---
  ([.result.secrets // [] | .[] | {
    type: (.type // "unknown"),
    path: (.path // "unknown"),
    line: (.startLine // 0),
    severity: (.severity // "HIGH")
  }]) as $secrets |

  # --- Malware ---
  ([.result.malwares // [] | .[] | {
    name: (.name // "unknown"),
    path: (.path // "unknown"),
    severity: (.severity // "CRITICAL")
  }]) as $malware |

  # --- Sensitive Data ---
  ([.result.dataFindings // [] | .[] | {
    type: (.dataClassifier.name // "unknown"),
    path: ([.examples // [] | .[].path] | first // "unknown"),
    severity: (.severity // "HIGH")
  }]) as $data |

  (if ($secrets | length) > 0 then
    "SECRETS (" + ($secrets | length | tostring) + " findings):\n" +
    ($secrets | map("  - " + .type + " at " + .path + ":" + (.line|tostring) + " [" + .severity + "]") | join("\n")) + "\n\n"
  else "" end) +

  (if ($data | length) > 0 then
    "SENSITIVE DATA (" + ($data | length | tostring) + " findings):\n" +
    ($data | map("  - " + .type + " at " + .path + " [" + .severity + "]") | join("\n")) + "\n\n"
  else "" end) +

  (if ($malware | length) > 0 then
    "MALWARE (" + ($malware | length | tostring) + " findings):\n" +
    ($malware | map("  - " + .name + " at " + .path + " [" + .severity + "]") | join("\n")) + "\n\n"
  else "" end)
' 2>/dev/null || echo "")

# --- Save trimmed scan output for remediation (strip policy bloat, null sections, metadata) ---
echo "$scan_output" | jq '{
  scanId: .id,
  verdict: .status.verdict,
  findings: {
    vulnerabilities: [.result.libraries // [] | .[] |
      select(.vulnerabilities | length > 0) | {
        package: .name, version: .version,
        path: .path, startLine: .startLine,
        vulnerabilities: [.vulnerabilities[] | {
          name, severity, description, score,
          fixedVersion, hasExploit, hasCisaKevExploit,
          epssProbability, weightedSeverity,
          fileRemediation
        }]
      }],
    secrets: [.result.secrets // [] | .[] | {
      type, path, lineNumber: .startLine,
      severity, snippet, contains
    }],
    sast: [.result.sast // [] | .[] | {
      name, severity, description,
      filePath, startLine, endLine, snippet,
      impact, likelihood, fileRemediation
    }],
    sensitiveData: [.result.dataFindings // [] | .[] | {
      classifier: .dataClassifier.name,
      severity, matchCount,
      paths: [.examples // [] | .[].path] | unique
    }],
    malware: [.result.malwares // [] | .[] | {
      path, malwareDetails
    }],
    supplyChain: [.result.softwareSupplyChain // [] | .[] | {
      name, severity, licenseNames,
      package: .codeLibrary
    }],
    aiModels: [.result.aiModels // [] | .[] | {
      path, modelFormat, name, vulnerabilities
    }]
  }
}' > /tmp/.wiz-scan-latest.json

# --- Audit mode: warn and proceed ---
if [ "$MODE" = "audit" ]; then
  jq -n --arg msg "$summary" --arg findings "$findings" '{
    "systemMessage": ("⚠️ Wiz Security Scan (pre-push): " + $msg),
    "hookSpecificOutput": {
      "hookEventName": "PreToolUse",
      "permissionDecision": "allow",
      "permissionDecisionReason": $msg,
      "additionalContext": (
        "IMPORTANT: You MUST display the following to the user as a markdown blockquote before continuing:\n\n> **Wiz Security Scan (pre-push):** " + $msg + "\n\nDo NOT paraphrase or skip this.\n\n" +
        if ($findings | length) > 0 then
          "After displaying the scan summary above, you MUST:\n" +
          "1. Inform the user: Full scan results saved to /tmp/.wiz-scan-latest.json\n" +
          "2. Ask the user: Would you like me to create a remediation plan using the Wiz scan results?\n" +
          "3. WAIT for the user to respond. Do NOT proceed with remediation until they confirm.\n" +
          "4. If the user confirms, call the `scan_findings_remediation_planner` MCP tool to get finding-type-specific remediation guidelines. If the MCP tool is unavailable, proceed with best-effort remediation based on the findings. Then read /tmp/.wiz-scan-latest.json for detailed finding descriptions and context. Present a remediation plan organized by priority for the user to approve BEFORE making any changes.\n\n" +
          "=== FINDINGS ===\n\n" + $findings
        else ""
        end
      )
    }
  }'
  exit 0
fi

# --- Block mode: deny the tool call ---
jq -n --arg msg "$summary" --arg findings "$findings" '{
  "systemMessage": ("❌ " + $msg),
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": ($msg + " Remediate findings before pushing."),
    "additionalContext": (
      if ($findings | length) > 0 then
        "The push was BLOCKED due to security policy violations.\n\n" +
        "You MUST display the following to the user:\n" +
        "1. The scan summary above\n" +
        "2. Inform the user: Full scan results saved to /tmp/.wiz-scan-latest.json\n" +
        "3. Ask the user: Would you like me to create a remediation plan using the Wiz scan results?\n" +
        "4. WAIT for the user to respond. Do NOT proceed with remediation until they confirm.\n" +
        "5. If the user confirms, call the `scan_findings_remediation_planner` MCP tool to get finding-type-specific remediation guidelines. If the MCP tool is unavailable, proceed with best-effort remediation based on the findings. Then read /tmp/.wiz-scan-latest.json for detailed finding descriptions and context. Present a remediation plan organized by priority for the user to approve BEFORE making any changes.\n\n" +
        "=== FINDINGS ===\n\n" + $findings
      else ""
      end
    )
  }
}'
exit 0
