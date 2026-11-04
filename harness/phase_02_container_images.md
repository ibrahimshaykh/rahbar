# Phase 02 — Container Images

**Goal.** Three Dockerfiles and two `.dockerignore` files, each satisfying every
assertion in the checker's `I · images` section and every security requirement
in §4.7.

**Requirements closed.** SE-03 (the image half), and the `I · api image`,
`I · indexer image`, `I · ui image`, `I · api/.dockerignore`,
`I · indexer/.dockerignore` checker sections.

**Core specs needed.** `07_KUBERNETES_MANIFEST_SPEC.md` §19–§22. Nothing else.

**Preconditions.**

```bash
git rev-parse --abbrev-ref HEAD    # dev
make test 2>&1 | tail -3           # green
ls api/app/main.py indexer/pipeline/run.py ui/index.html ui/nginx.conf
```

---

## The five assertions every image must satisfy

The checker reads each Dockerfile and fails on any of these:

| Assertion | Why it matters | How we satisfy it |
|---|---|---|
| every `FROM` is tag-pinned, never bare and never `:latest` | an unpinned base is the drift problem from Lecture 04: the image you tested is not the image that deploys | `python:3.12-slim-bookworm`, `nginxinc/nginx-unprivileged:1.27-alpine` |
| a non-root `USER` | §4.7 hole 3. A root container that is compromised owns the node's namespace | `USER 10001` (api, indexer), `USER 101` (ui) |
| exec-form `CMD`/`ENTRYPOINT` | shell form wraps the process in `/bin/sh -c`, so SIGTERM reaches the shell and not PID 1: `preStop` and `terminationGracePeriodSeconds` silently stop working | `CMD ["uvicorn", ...]` |
| no credential in the Dockerfile | −20 | nothing is `ENV`-ed that looks like a secret |
| `.dockerignore` excludes `.git` and `__pycache__` | a 40 MB build context and a `.git` directory inside a published image | explicit lists |

The UID matters: `07_KUBERNETES_MANIFEST_SPEC.md` sets
`runAsUser: 10001` on the api, indexer, chroma and redis pods and
`runAsUser: 101` on the ui pod. If the image's `USER` and the manifest's
`runAsUser` disagree, files the image created at build time become unreadable
at run time.

---

## Task list

### P02-T01 `[AGENT]` · `api/Dockerfile`

Transcribe `07_KUBERNETES_MANIFEST_SPEC.md` §19 exactly. Points to get right:

- `COPY requirements.txt ./` **before** `COPY app ./app`, so a code change does
  not invalidate the pip layer.
- `groupadd`/`useradd` with explicit `--uid 10001 --gid 10001` matching the
  manifest.
- `chown -R 10001:10001 /app` **before** `USER 10001`.
- No `--workers`: three replicas provide concurrency, and one process per pod
  keeps the default (non-multiprocess) Prometheus registry correct. A
  multi-worker uvicorn would give each worker its own counters and `/metrics`
  would report whichever worker answered.
- `EXPOSE 8000` is documentation only; the manifest's `containerPort` is what
  matters.

### P02-T02 `[AGENT]` · `indexer/Dockerfile`

Transcribe §20. The one thing this image has that the others do not:

```dockerfile
RUN apt-get update \
 && apt-get install --no-install-recommends -y \
      tesseract-ocr \
      poppler-utils \
 && rm -rf /var/lib/apt/lists/*
```

**`pytesseract` and `pdf2image` are Python wrappers around binaries.** Without
`tesseract-ocr` the OCR branch raises; without `poppler-utils` (`pdftoppm`)
`pdf2image` cannot rasterise a page. `extract.py` degrades to `""` with a
warning rather than crashing, but then corpus property 3 is unsatisfied and
failure mode A is not actually handled. Install both.

Try the version-pinned form first:

```dockerfile
      tesseract-ocr=5.3.0-2 \
      poppler-utils=22.12.0-2+deb12u1 \
```

If `apt-get` reports those versions are unavailable (Debian point releases move),
drop the `=version` suffixes, and record the change as a Decision Log entry. The
`FROM` pin is what the checker tests; the apt pin is good practice, not a gate.

Also:

```dockerfile
COPY corpus-baked/ /corpus-baked/
```

`indexer/corpus-baked/` is populated by `make images` (fixtures for CI,
`corpus/raw/` for a local real run) and is gitignored. Create it now so the
build does not fail on a missing path:

```bash
mkdir -p indexer/corpus-baked
printf '# populated by `make images`; never committed\n' > indexer/corpus-baked/.gitkeep
printf '\n# built artefact: populated by make images\nindexer/corpus-baked/*\n!indexer/corpus-baked/.gitkeep\n' >> .gitignore
```

### P02-T03 `[AGENT]` · `ui/Dockerfile`

Transcribe §21. Four facts drive it, all from `STARTER.md` and `ui/nginx.conf`:

1. `nginx.conf` sets `listen 8080` — a non-root process cannot bind below 1024.
2. It sets `pid /tmp/nginx.pid` and five `*_temp_path` directives under `/tmp` —
   so `readOnlyRootFilesystem: true` works provided the manifest mounts an
   `emptyDir` at `/tmp`, which it does.
3. It logs to `/dev/stdout` and `/dev/stderr` — never to a file (§4.8).
4. It does **not** proxy the API. The Ingress routes `/api` to the api Service.
   Do not add a `proxy_pass`.

`nginxinc/nginx-unprivileged` already runs as uid 101 and already expects a
config at `/etc/nginx/nginx.conf`, so the image is three `COPY`/`USER` lines.

**Single-stage is correct here.** `ui/index.html` is a finished static page with
no build step, so there is no Node toolchain to keep out of the final layer.
The checker's `multi_required` flag is `False` for all three images.

### P02-T04 `[AGENT]` · The two `.dockerignore` files

Transcribe §22. The checker requires `.git` and `__pycache__` in both and warns
unless `corpus` or a venv is excluded.

**One trap:** `indexer/.dockerignore` must **not** exclude `corpus-baked/`. The
build context is `indexer/`, so a `corpus` line would match `corpus-baked` by
prefix in some Docker versions. Write the exclusions as exact names:

```
corpus
corpus/
```

and never a bare `corpus*`. Verify after writing:

```bash
grep -n corpus indexer/.dockerignore     # must not match corpus-baked
```

`ui/` needs no `.dockerignore` (the checker only asks for two) but add one
anyway for a small context:

```
.git
Dockerfile
.dockerignore
*.md
```

### P02-T05 `[AGENT]` · Verify every assertion locally, without Docker

These checks need no daemon, so run them as an `[AGENT]` task:

```bash
# every FROM is tag-pinned, none is :latest
grep -hE '^\s*FROM' api/Dockerfile indexer/Dockerfile ui/Dockerfile
grep -hE '^\s*FROM' api/Dockerfile indexer/Dockerfile ui/Dockerfile | grep -c ':'   # 3
grep -hE '^\s*FROM' api/Dockerfile indexer/Dockerfile ui/Dockerfile | grep -c ':latest'  # 0

# a non-root USER in each
for f in api/Dockerfile indexer/Dockerfile ui/Dockerfile; do
  echo -n "$f: "; grep -E '^\s*USER\s+' "$f" || echo "MISSING"
done
grep -hE '^\s*USER\s+root\b' api/Dockerfile indexer/Dockerfile ui/Dockerfile   # empty

# exec-form CMD or ENTRYPOINT in each
for f in api/Dockerfile indexer/Dockerfile ui/Dockerfile; do
  echo -n "$f: "; grep -E '^\s*(CMD|ENTRYPOINT)\s*\[' "$f" || echo "MISSING or shell form"
done

# no credential
grep -nEi '(PASSWORD|SECRET|TOKEN|API_?KEY)\s*=\s*["'"'"']?\S{8,}' api/Dockerfile indexer/Dockerfile ui/Dockerfile   # empty

# dockerignore contents
for f in api/.dockerignore indexer/.dockerignore; do
  echo "=== $f"; grep -cx '.git' "$f"; grep -cx '__pycache__' "$f"
done

# the checker's own verdict
python3 scripts/check_submission.py 2>&1 | grep -A6 'I · api image'
python3 scripts/check_submission.py 2>&1 | grep -A6 'I · indexer image'
python3 scripts/check_submission.py 2>&1 | grep -A6 'I · ui image'
```

**Exit criterion: zero FAIL lines in all five `I ·` image sections.**

### P02-T06 `[HUMAN]` · Build the images

Write `scripts/evidence/P02-T06_images.sh`:

```bash
#!/usr/bin/env bash
# P02-T06 · the three images build and load into minikube
set -euo pipefail
OUT=docs/evidence/images_built.txt
mkdir -p "$(dirname "$OUT")" indexer/corpus-baked
{
  echo "# P02-T06 captured $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo; echo "# stage the fixture corpus into the indexer build context"
  cp eval/fixtures/*.md indexer/corpus-baked/ 2>&1
  ls -la indexer/corpus-baked/ 2>&1
  echo; echo "\$ docker build -t rahbar-api:dev api"
  docker build -t rahbar-api:dev api 2>&1 | tail -15
  echo; echo "\$ docker build -t rahbar-indexer:dev indexer"
  docker build -t rahbar-indexer:dev indexer 2>&1 | tail -15
  echo; echo "\$ docker build -t rahbar-ui:dev ui"
  docker build -t rahbar-ui:dev ui 2>&1 | tail -15
  echo; echo "\$ docker images | grep rahbar"
  docker images 2>&1 | grep rahbar
  echo; echo "# prove each image runs as a non-root user"
  for i in api indexer ui; do
    echo -n "rahbar-$i:dev id -u -> "
    docker run --rm --entrypoint sh "rahbar-$i:dev" -c 'id -u' 2>&1 || echo "(no shell: fine)"
  done
  echo; echo "# prove tesseract and pdftoppm are present in the indexer image"
  docker run --rm --entrypoint sh rahbar-indexer:dev -c 'tesseract --version 2>&1 | head -1; pdftoppm -v 2>&1 | head -1' 2>&1
  echo; echo "# prove the api image starts and answers /healthz"
  docker run -d --name rahbar-api-smoke -p 18000:8000 \
    -e RETRIEVER=stub -e LLM_PROVIDER=stub rahbar-api:dev >/dev/null 2>&1
  sleep 4
  curl -sf http://localhost:18000/healthz 2>&1; echo
  docker rm -f rahbar-api-smoke >/dev/null 2>&1
  echo; echo "\$ minikube image load (all three)"
  for i in api indexer ui; do minikube image load "rahbar-$i:dev" 2>&1; done
  echo "loaded"
} | tee "$OUT"
```

Register in the Pending-Human table:

```bash
bash scripts/evidence/P02-T06_images.sh
```

**Expected:** `id -u` prints `10001` for api and indexer, `101` for ui;
tesseract reports version 5.x; `/healthz` returns `{"status":"alive"}`.

Known trap: **`ImagePullBackOff` on an image you built locally** means minikube
cannot see your laptop's Docker images. `minikube image load` is the fix, and
`imagePullPolicy: IfNotPresent` in the manifests is what stops the kubelet
trying a registry. Both are already specified.

---

## Files created or modified

| Path | Action |
|---|---|
| `api/Dockerfile` | created |
| `indexer/Dockerfile` | created |
| `ui/Dockerfile` | created |
| `api/.dockerignore` | created |
| `indexer/.dockerignore` | created |
| `ui/.dockerignore` | created |
| `indexer/corpus-baked/.gitkeep` | created |
| `.gitignore` | `indexer/corpus-baked/*` appended |
| `scripts/evidence/P02-T06_images.sh` | created |

---

## Exit criteria

```bash
# 1. all six files exist
ls api/Dockerfile indexer/Dockerfile ui/Dockerfile api/.dockerignore indexer/.dockerignore ui/.dockerignore

# 2. zero image FAILs
python3 scripts/check_submission.py 2>&1 | grep -E '^\s+ FAIL ' | grep -i 'image\|dockerignore'
# EXPECT: no output

# 3. the overall failure count has not risen
make check 2>&1 | tail -3

# 4. nothing in the Python packages broke
make test 2>&1 | tail -3
make lint 2>&1 | tail -3

# 5. corpus-baked is ignored but its keep file is tracked
git check-ignore -v indexer/corpus-baked/academic-rules-2026.md || echo "not ignored - fix .gitignore"
git ls-files indexer/corpus-baked/
```

Plus P02-T06 done-and-verified, or registered as pending with the script written.

---

## Rollback

```bash
git checkout -- .gitignore
rm -f api/Dockerfile indexer/Dockerfile ui/Dockerfile \
      api/.dockerignore indexer/.dockerignore ui/.dockerignore
```

---

## Commits

```
build(api): add a pinned non-root api image
build(indexer): add the indexer image with tesseract and poppler
build(ui): add the unprivileged nginx ui image
build(repo): exclude the build contexts' heavy directories
```

---

## Before leaving

Tick P02-T01…T06. Paste every verification command's output in the Run Log.
Register P02-T06 in Pending-Human if Docker is not available to you. Advance
the pointer to `P03` /
`harness/phase_03_kubernetes_data_tier.md`.
