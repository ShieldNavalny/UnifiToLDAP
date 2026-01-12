FROM ubuntu:24.04

# Установка пакетов
RUN apt-get update && apt-get install -y \
    python3 python3-pip python3-full \
    slapd ldap-utils \
    curl jq \
    && rm -rf /var/lib/apt/lists/*

# Создаем virtualenv для обхода externally-managed
WORKDIR /app
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Python зависимости в venv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# OpenLDAP подготовка
RUN mkdir -p /var/lib/ldap /var/run/slapd /etc/ldap/slapd.d && \
    chown -R openldap:openldap /var/lib/ldap /var/run/slapd /etc/ldap/slapd.d

# Код приложения
COPY unifi_ldap_sync/ ./unifi_ldap_sync/
RUN chmod +x ./unifi_ldap_sync/main.py

# LDAP конфигурация
COPY ldap/ /etc/ldap/
COPY ldap/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

VOLUME ["/etc/ldap/slapd.d", "/var/lib/ldap"]

EXPOSE 389 636

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["python", "-m", "unifi_ldap_sync.main"]
