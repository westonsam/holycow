FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
COPY backend/requirements.lock /app/backend/requirements.lock
RUN pip install --no-cache-dir -r backend/requirements.lock \
    && groupadd --gid 10001 holycow \
    && useradd --uid 10001 --gid holycow --no-create-home holycow \
    && mkdir -p /data && chown holycow:holycow /data
COPY --chown=holycow:holycow backend /app/backend
USER holycow
EXPOSE 8870
CMD ["uvicorn", "backend.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8870", "--workers", "1", "--no-access-log"]
