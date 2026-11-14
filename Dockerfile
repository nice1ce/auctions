# Образ приложения Auction System (Lab 4).
#
# Воспроизводимость сборки:
#   * базовый образ зафиксирован точной версией (никаких latest / «плавающих» тегов);
#     для полной фиксации допишите digest — `make pin-digest` покажет строку FROM;
#   * зависимости ставятся из requirements.lock — полный список пакетов
#     (включая транзитивные) с точными версиями, только готовые wheel-пакеты,
#     --no-deps: pip не может «дотянуть» непредусмотренную версию;
#   * в контекст сборки попадают только нужные файлы (.dockerignore — белый список),
#     поэтому .env, бэкапы и .git в образ попасть не могут.

# ---- 1. Сборка зависимостей в отдельном venv -----------------------------------
FROM python:3.12.14-slim-bookworm AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.lock /tmp/requirements.lock
RUN pip install --no-deps --only-binary=:all: -r /tmp/requirements.lock \
 && pip check

# ---- 2. Итоговый образ ------------------------------------------------------------
FROM python:3.12.14-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# Непривилегированный системный пользователь: без домашнего каталога и без shell.
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --no-create-home \
            --home-dir /nonexistent --shell /usr/sbin/nologin app

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
# Код принадлежит root и доступен приложению только на чтение.
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY static ./static

# Метки — в конце, чтобы смена версии не пересобирала слои выше.
ARG APP_VERSION=0.0.0
LABEL org.opencontainers.image.title="auction-system" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.source="https://github.com/nice1ce/auctions"

USER 10001:10001
EXPOSE 8000

# Uvicorn запускается напрямую (exec-форма, PID 1): получает SIGTERM от
# `docker stop`, перестаёт принимать соединения, дожидается текущих запросов
# (не дольше --timeout-graceful-shutdown), выполняет shutdown приложения и
# завершается с кодом 0.
STOPSIGNAL SIGTERM

HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=2)"]

CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*", \
     "--timeout-graceful-shutdown", "20", \
     "--no-server-header"]
