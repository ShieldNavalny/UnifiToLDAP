# UnifiToLDAP Sync

Автоматическая синхронизация пользователей UniFi Access (локальный API) с OpenLDAP.

## Назначение

Синхронизирует активных пользователей UniFi Access с OpenLDAP:
- Добавляет новых пользователей
- Обновляет данные существующих  
- Удаляет уволенных (обратная синхронизация)
- Фильтрует техперсонал по ключевому слову в фамилии (land)

## Быстрый старт

### 1. Docker Compose (рекомендуется)

```bash
git clone https://github.com/ShieldNavalny/UnifiToLDAP.git
cd UnifiToLDAP

cp .env.example .env
# Отредактируй .env с твоими данными

docker-compose up -d
```

### 2. Пример .env

```bash
# UniFi Access Local API (через роутер)
UNIFI_ACCESS_HOSTNAME=192.168.1.100
UNIFI_ACCESS_PORT=12445
UNIFI_ACCESS_API_TOKEN=your_api_token_here
UNIFI_ACCESS_VERIFY_SSL=false

# LDAP
LDAP_BASE_DN="dc=example,dc=com"
LDAP_ADMIN_DN="cn=admin,dc=example,dc=com"
LDAP_ADMIN_PASSWORD="secure_password"

# Приложение
LOG_LEVEL=INFO
SYNC_INTERVAL=300
```

### 3. Управление

```bash
docker-compose logs -f unifi-sync
docker-compose restart unifi-sync
docker-compose down
```

## Архитектура

```
UniFi Access API (локальный) ←→ Sync Service ←→ OpenLDAP
              ↓                           ↓
     /api/v1/developer/users     ou=users,dc=example,dc=com
```

## Основные файлы

| Файл | Описание |
|------|----------|
| `unifi_client.py` | Клиент локального UniFi Access API |
| `ldap_sync.py` | Логика синхронизации + удаление уволенных |
| `config.py` | Загрузка конфига из ENV |
| `main.py` | Бесконечный цикл синхронизации |

## Настройка UniFi Access API

1. Создай API Token:
   ```
   UniFi Console → Settings → Advanced → API Token → Create New
   ```
   - Key name: `LDAP Sync`
   - Validity: Permanent
   - Permissions: `viewuser`, `edituser`

2. Hostname: IP твоего UniFi Console (роутер с Access)
3. Port: `12445`

## Фильтры

### Исключение техперсонала
```python
def should_skip_user(self, user_data):
    lastname = user_data.get('last_name', '')
    if 'land' in lastname.lower():  # техподдержка
        return True
```

## Логи

```
2026-01-12 18:00:01 [INFO] Fetched 42 users from UniFi Access
2026-01-12 18:00:02 [INFO] Added: john.doe@company.com
2026-01-12 18:00:03 [INFO] Deleted obsolete user: ex-employee-uuid
2026-01-12 18:00:04 [INFO] Sync completed: 2 added, 40 updated, 0 errors
```

## Docker Compose переменные

| Переменная | Описание | Обязательная |
|------------|----------|-------------|
| `UNIFI_ACCESS_HOSTNAME` | IP UniFi Console | Да |
| `UNIFI_ACCESS_API_TOKEN` | API токен | Да |
| `LDAP_BASE_DN` | База LDAP | Да |
| `LDAP_ADMIN_DN` | Админ DN | Да |
| `LDAP_ADMIN_PASSWORD` | Админ пароль | Да |
| `SYNC_INTERVAL` | Интервал (сек) | Нет (300) |

## История версий

### v1.0 (локальный API)
- Полная синхронизация UniFi Access → OpenLDAP
- Добавление/обновление/удаление пользователей
- Фильтр техперсонала
- Docker Compose с OpenLDAP

### v0.x (облачный UID)
- Заморожено в ветке `UIDAPI`
- Не поддерживается

## Возможные проблемы

| Проблема | Решение |
|----------|---------|
| `SSL certificate verify failed` | `UNIFI_ACCESS_VERIFY_SSL=false` |
| `Missing required environment variables` | Проверь `.env` |
| `Connection refused` | Проверь IP/порт UniFi Console |

## TODO
- Telegram уведомления о синхронизации
- Healthcheck endpoint
- Prometheus метрики
- Graceful restart при смене токена

**Автор**: ShieldNavalny  
**Лицензия**: GNU Lesser General Public License v3.0  
**Репозиторий**: [github.com/ShieldNavalny/UnifiToLDAP](https://github.com/ShieldNavalny/UnifiToLDAP)

API reference можно найти в консоле Unifi или панели управления UID
