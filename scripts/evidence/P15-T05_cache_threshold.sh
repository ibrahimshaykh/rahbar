#!/usr/bin/env bash
# P15-T05 · cache-threshold false-hit probe · CA-02, the nine-pair protocol in
# harness/09_CORPUS_EVAL_AND_EVIDENCE_SPEC.md section 6.
# Usage: P15-T05_cache_threshold.sh <threshold-label-for-the-header-line>
# Asks A, then asks B for all nine pairs, and reports whether B came back
# with X-Cache: hit - printing one line per pair:
#   P4 MISS expected=MISS ok
#   P4 HIT expected=MISS FALSE-HIT
set -euo pipefail

IP="${INGRESS_IP:-127.0.0.1}"
HOST="${HOST:-rahbar.local}"
LABEL="${1:-unlabelled}"

ask() {
  local tries=0
  while true; do
    curl -s -D /tmp/p15t05-headers -o /tmp/p15t05-body.json -w '%{http_code}' \
      -X POST "http://$IP/api/ask" \
      -H "Host: $HOST" -H 'Content-Type: application/json' \
      -d "{\"question\": $(python3 -c "import json,sys; print(json.dumps(sys.argv[1]))" "$1")}" \
      --max-time 180 > /tmp/p15t05-code
    if [ "$(cat /tmp/p15t05-code)" -lt 500 ] || [ "$tries" -ge 2 ]; then
      cat /tmp/p15t05-headers
      return
    fi
    tries=$((tries + 1))
    sleep 3
  done
}

probe() {
  local pair="$1" qa="$2" qb="$3" expect="$4"
  # bump the cache generation first so this pair is tested in isolation -
  # otherwise B can match an EARLIER pair's A rather than its own partner
  # (e.g. P4's attendance question could hit P2's, also about attendance).
  kubectl exec -n rahbar deploy/redis -- redis-cli INCR rahbar:cache:gen > /dev/null 2>&1 || true
  ask "$qa" > /tmp/p15t05-a.headers
  sleep 1
  ask "$qb" > /tmp/p15t05-b.headers
  local cache
  cache=$(grep -i '^x-cache:' /tmp/p15t05-b.headers | tr -d '\r' | awk '{print $2}')
  local got="MISS"
  [ "$cache" = "hit" ] && got="HIT"
  if [ "$got" = "$expect" ]; then
    echo "$pair $got expected=$expect ok"
  else
    echo "$pair $got expected=$expect FALSE-HIT"
  fi
}

echo "# threshold label: $LABEL"
probe P1 "What CGPA avoids academic warning?" "What is the minimum CGPA to stay off academic warning?" HIT
probe P2 "What attendance is needed for the final exam?" "How much attendance do I need to sit the final?" HIT
probe P3 "What is the BS fee per credit hour?" "How much does one credit hour cost for BS?" HIT
probe P4 "What is the current attendance requirement?" "What was the previous attendance requirement?" MISS
probe P5 "What CGPA avoids academic warning?" "What CGPA avoids probation?" MISS
probe P6 "What does clause 1.21 require?" "What does clause 1.12 require?" MISS
probe P7 "What is the BS fee per credit hour?" "What is the MS fee per credit hour?" MISS
probe P8 "How do I apply for a hostel room?" "How do I apply for a transcript?" MISS
probe P9 "What is the refund policy for withdrawal?" "What is the refund policy for deferment?" MISS
