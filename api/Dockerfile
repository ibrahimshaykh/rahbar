# Pinned by minor version. Never bare `python`, never `:latest` - the checker
# fails an unpinned FROM.
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Requirements first: this layer is cached unless the pins change.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Non-root, matching runAsUser: 10001 in the manifests.
RUN groupadd --gid 10001 rahbar \
 && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin rahbar \
 && chown -R 10001:10001 /app
USER 10001

EXPOSE 8000

# Exec form: SIGTERM reaches uvicorn as PID 1, so preStop + graceful shutdown work.
# No --workers: three replicas provide concurrency, and one process per pod
# keeps the default (non-multiprocess) Prometheus registry correct.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
