#!/usr/bin/env bash
# Prints offending paths; empty output + exit 0 = compliant (R1, R2, L3).
# ui/Dockerfile is an owner-requested exception (D3-19): CI's image scan failed on nginx CVEs
# and the fix has to live in that file. api/Dockerfile likewise (D3-20): Debian CVE fixes.
BASE="${A02_BASE:-390deee}"
git diff --name-status "$BASE"..HEAD 2>/dev/null | grep -E '^(D|R)'
git diff --name-status "$BASE"..HEAD 2>/dev/null | grep -E '^M' | grep -vE '_03\.[A-Za-z0-9]+$' | grep -vE '^M\s+(\.gitignore|k8s/base/configmap\.yaml|ui/Dockerfile|api/Dockerfile)$'
git diff --name-status "$BASE"..HEAD 2>/dev/null | awk '$1=="A"{print $2}' | grep -vE '(_03(\.[A-Za-z0-9]+)?$|^harness_03/|/__init__\.py$|^docs/evidence_03/|^eval/results/|^traces/)'
git diff --name-only "$BASE"..HEAD 2>/dev/null | grep -E 'scripts/check_submission\.py|STARTER\.md|assignment\.pdf|Assignment_03\.pdf'
git diff "$BASE"..HEAD 2>/dev/null | grep -nE 'gsk_[A-Za-z0-9]{20,}|AIza[A-Za-z0-9_-]{25,}|sk-[A-Za-z0-9]{30,}'
exit 0
