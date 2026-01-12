FROM python:3.11-slim

WORKDIR /app

# Установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода
COPY unifi_ldap_sync/ ./unifi_ldap_sync/

CMD ["python", "-m", "unifi_ldap_sync.main"]
