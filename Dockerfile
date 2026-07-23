FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
COPY config ./config
COPY sql ./sql
RUN pip install --no-cache-dir . && pip install --no-cache-dir "uvicorn[standard]"

ENV LOC_CONTRACTS_DIR=/app/config/contracts \
    LOC_SCHEMA_DDL=/app/sql/schema.sql \
    LOC_AUDIT_DB=/data/audit.db
VOLUME ["/data"]
EXPOSE 8000

CMD ["uvicorn", "llm_output_contract.api:app", "--host", "0.0.0.0", "--port", "8000"]
