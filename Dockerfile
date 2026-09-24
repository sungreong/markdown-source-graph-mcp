FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --create-home --uid 10001 app \
    && mkdir -p /data \
    && chown -R app:app /data

COPY --chown=app:app src ./src
COPY --chown=app:app examples/prompts ./examples/prompts

USER app

EXPOSE 8811

CMD ["python", "-m", "markdown_source_graph_mcp.server", "--host", "0.0.0.0", "--port", "8811"]
