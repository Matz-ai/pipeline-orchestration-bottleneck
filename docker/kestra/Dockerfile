# Image Kestra officielle + Python 3.11 (pandas, openpyxl, duckdb) et CLI DuckDB,
# pour exécuter les scripts du flow dans le conteneur sans installation au run.
ARG KESTRA_VERSION=v2.0.5
FROM kestra/kestra:${KESTRA_VERSION}

USER root

COPY --from=ghcr.io/astral-sh/uv:0.8.4 /uv /usr/local/bin/uv
COPY requirements.txt /tmp/requirements.txt

ENV UV_PYTHON_INSTALL_DIR=/opt/python
RUN uv venv --python 3.11 /opt/bottleneck-venv  && uv pip install --python /opt/bottleneck-venv/bin/python --no-cache       -r /tmp/requirements.txt  && chown -R kestra:kestra /opt/bottleneck-venv /opt/python  && rm /tmp/requirements.txt

# CLI DuckDB, même version que la librairie Python
ARG DUCKDB_CLI_VERSION=1.3.2
ARG TARGETARCH
RUN /opt/bottleneck-venv/bin/python -c "import io, urllib.request, zipfile; arch = {'amd64': 'amd64', 'arm64': 'arm64'}['${TARGETARCH:-amd64}']; url = f'https://github.com/duckdb/duckdb/releases/download/v${DUCKDB_CLI_VERSION}/duckdb_cli-linux-{arch}.zip'; zipfile.ZipFile(io.BytesIO(urllib.request.urlopen(url).read())).extract('duckdb', '/usr/local/bin')"  && chmod 755 /usr/local/bin/duckdb

# Dossiers des volumes, créés avec le bon propriétaire (sinon Kestra ne peut pas écrire sa base H2)
RUN mkdir -p /app/data /app/storage /tmp/kestra-wd  && chown kestra:kestra /app/data /app/storage /tmp/kestra-wd

ENV PATH="/opt/bottleneck-venv/bin:${PATH}"

USER kestra
