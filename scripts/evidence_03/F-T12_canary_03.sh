#!/usr/bin/env bash
# Superseded: the evidence in docs/evidence_03/ was produced by F-T12b_rollback_03.sh, which matches how the
# cluster run actually went. Kept so that older references still work.
exec bash "$(dirname "$0")/F-T12b_rollback_03.sh" "$@"
