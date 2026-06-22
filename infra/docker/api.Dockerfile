FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml ./
COPY src/backend ./src/backend
RUN python -m pip install --no-cache-dir .
RUN useradd --create-home --uid 10001 cellxp && chown -R cellxp:cellxp /app
USER cellxp
EXPOSE 8000
CMD ["uvicorn", "cellxp.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
