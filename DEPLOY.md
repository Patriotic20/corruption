# Деплой

Стек: два Telegram-бота (long polling), Celery worker, PostgreSQL, Redis.
HTTP-портов нет — наружу ничего не публикуется, nginx не нужен.

## Изоляция от соседнего проекта

На сервере уже заняты порты `80, 3000, 5050, 5436, 6379, 8000`.
Этот стек **не публикует ни одного порта** и живёт в собственной сети
`corruption_corruption_net` с собственными Postgres и Redis. Пересечений с
`nusmt_backend / nusmt_frontend / database / redis_cache / pgadmin / nginx_proxy`
нет ни по портам, ни по именам контейнеров (`corruption_*`), ни по томам.

## Первый запуск

```bash
git clone <repo> /opt/corruption
cd /opt/corruption

cp .env.example .env
openssl rand -hex 24          # сгенерировать POSTGRES_PASSWORD
nano .env                     # токены ботов, ADMIN_IDS, пароль в POSTGRES_PASSWORD и POSTGRES_DSN
chmod 600 .env

docker compose up -d --build
docker compose ps
docker compose logs -f
```

`POSTGRES_PASSWORD` должен совпадать с паролем внутри `POSTGRES_DSN` — это одна и та же
база, просто compose и приложение читают её из разных переменных.

## Обновление

```bash
cd /opt/corruption
git pull
docker compose up -d --build
```

Сервис `migrate` прогоняет `alembic upgrade head` до старта ботов и воркера,
так что миграции применяются сами.

## Эксплуатация

```bash
docker compose ps                          # статус и healthcheck
docker compose logs -f admin-bot           # логи одного сервиса
docker compose restart worker
docker compose exec postgres psql -U corruption -d corruption
docker compose down                        # остановить (данные в томах остаются)
```

Бэкап базы:

```bash
docker compose exec -T postgres pg_dump -U corruption corruption | gzip > backup-$(date +%F).sql.gz
```

Восстановление:

```bash
gunzip -c backup-2026-09-04.sql.gz | docker compose exec -T postgres psql -U corruption -d corruption
```

## Локальная разработка

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

Оверлей публикует Postgres на `127.0.0.1:5433`, Redis на `127.0.0.1:6380`
и монтирует исходники в контейнеры.

## Что заложено в прод-конфиг

- Multi-stage образ: зависимости ставятся в `/opt/venv` отдельным слоем, правка кода
  не пересобирает их заново.
- Запуск от непривилегированного пользователя `app`, `tini` как PID 1 — корректная
  обработка SIGTERM при `docker compose stop`.
- Healthcheck у Postgres, Redis и Celery worker; боты и воркер стартуют только после
  `service_healthy` и успешного завершения `migrate`.
- Ротация логов (10 МБ × 3 файла на контейнер) и лимиты памяти — стек не может
  забить диск или вытеснить соседний проект.
- FSM-состояние aiogram хранится в Redis (`fsm:client` / `fsm:admin`), поэтому
  недозаполненная форма переживает рестарт контейнера.
- Redis с `appendonly yes` и `maxmemory-policy noeviction` — очередь Celery не
  теряется и задачи не вытесняются.
