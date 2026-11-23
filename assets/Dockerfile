FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY scripts/creator_lead.py /app/scripts/creator_lead.py
COPY assets/campaign.example.json /app/assets/campaign.example.json

RUN mkdir -p /data && useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app /data
USER appuser

EXPOSE 8787
VOLUME ["/data"]
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8787/health', timeout=2)"

ENTRYPOINT ["python", "/app/scripts/creator_lead.py"]
CMD ["serve", "--config", "/app/assets/campaign.example.json", "--data-dir", "/data", "--host", "0.0.0.0", "--port", "8787"]
