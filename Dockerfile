# Thư viện cài TRƯỚC khi chép mã: sửa mã chỉ làm lại lớp mã, không làm lại lớp thư viện (S-023).
FROM python:3.13-slim@sha256:bf44cdfcb76cd3b41e879bc058fc37ec5872002ccfde7fcb765e218cde0cd79c
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
# Lớp thư viện chỉ phụ thuộc pyproject.toml: lấy danh sách phụ thuộc ra rồi cài.
COPY pyproject.toml ./
RUN python -c "import tomllib; print('\n'.join(tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']))" > /tmp/requirements.txt \
    && pip install -r /tmp/requirements.txt && rm /tmp/requirements.txt
# Lớp mã: cài gói của dịch vụ, không kéo lại phụ thuộc.
COPY src ./src
RUN pip install --no-deps .
RUN useradd --system --no-create-home ingest
USER ingest
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/healthz').status==200 else 1)"
CMD ["uvicorn", "ingest.main:build_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
