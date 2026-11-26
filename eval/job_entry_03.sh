#!/bin/sh
# Eval Job entrypoint (Assignment 03, Part C/F). The Job's exit status IS the release gate's.
set -eu
R=/data/eval/results; mkdir -p "$R"
EXP_PTR="$R/last_experiment_${EVAL_TAG}_03.path"

# run_suite exits 5 when any request errored. Whether that many errors are acceptable is
# decided by change_experiment_03 (--max-error-rate), so only other failures stop the Job.
run_suite_tolerating_errors() {
  set +e
  python -m eval.run_suite_03 "$@"
  rc=$?
  set -e
  if [ "$rc" -ne 0 ] && [ "$rc" -ne 5 ]; then exit "$rc"; fi
}

if [ "${GATE_ONLY:-0}" != "1" ]; then
  # 1. baseline suite (against the live api), 2. candidate suite, 3. experiment across the 3 levels
  # REUSE_BASELINE=1 / REUSE_CANDIDATE=1 skip a suite whose result is already stored (a run
  # costs ~25 min on a CPU-only LLM); CANDIDATE_RUNS defaults to the full two-run protocol.
  if [ "${REUSE_BASELINE:-0}" = "1" ] && ls "$R"/suite_03_baseline_*_run1.json >/dev/null 2>&1; then
    echo "reusing stored baseline: $(ls -t "$R"/suite_03_baseline_*_run1.json | head -1)"
  else
    run_suite_tolerating_errors --api "$EVAL_BASELINE_URL" --golden eval/golden_03.jsonl --seed 1337 --runs 2 \
           --out-dir "$R" --tag baseline --require-cold --chroma
  fi
  if [ "${REUSE_CANDIDATE:-0}" = "1" ] && ls "$R"/suite_03_"${EVAL_TAG}"_*_run1.json >/dev/null 2>&1; then
    echo "reusing stored candidate: $(ls -t "$R"/suite_03_"${EVAL_TAG}"_*_run1.json | head -1)"
  else
    run_suite_tolerating_errors --api "$EVAL_TARGET_URL" --golden eval/golden_03.jsonl --seed 1337 \
           --runs "${CANDIDATE_RUNS:-2}" --out-dir "$R" --tag "$EVAL_TAG" --require-cold --chroma
  fi
  python -m eval.change_experiment_03 --baseline "$(ls -t $R/suite_03_baseline_*_run1.json | head -1)" \
         --candidate "$(ls -t $R/suite_03_${EVAL_TAG}_*_run1.json | head -1)" --name "$EVAL_TAG" \
         --out-dir "$R" --out-pointer "$EXP_PTR" --max-error-rate "${MAX_ERROR_RATE:-0}"
fi
EXP="$(cat "$EXP_PTR")"
set +e
python -m eval.release_gate_03 --experiment "$EXP" --thresholds "$GATE_THRESHOLDS_PATH" --out-dir "$R"
RC=$?
echo "release_gate_exit=$RC"
exit $RC
