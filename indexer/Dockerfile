FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# OCR needs system packages, not only pip packages:
#   tesseract-ocr   - the OCR engine pytesseract drives
#   poppler-utils   - pdftoppm, which pdf2image shells out to
# `upgrade` first: the base image lags Debian's security updates, and the CI
# trivy gate fails on any fixable HIGH/CRITICAL OS package.
RUN apt-get update \
 && apt-get upgrade -y \
 && apt-get install --no-install-recommends -y \
      tesseract-ocr \
      poppler-utils \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY pipeline ./pipeline

# The CI fixture corpus (or the real corpus/raw/) is baked in here by
# `make images`, so the Job needs no volume. CORPUS_DIR in the ConfigMap
# selects which path is used. This directory is populated at build time and
# is gitignored - see Makefile `images` target and docs/PIPELINE.md.
COPY corpus-baked/ /corpus-baked/

RUN groupadd --gid 10001 rahbar \
 && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin rahbar \
 && chown -R 10001:10001 /app /corpus-baked
USER 10001

# A Job, so it exits. Exec form.
CMD ["python", "-m", "pipeline.run"]
