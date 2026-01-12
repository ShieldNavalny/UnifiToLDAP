FROM ubuntu:24.04

# Установка пакетов
RUN apt-get update && apt-get install -y \
    python3 python3-pip \
    slapd ldap-utils \
    curl jq \
    && rm -rf /var/lib/apt/lists/*

# Python зависимости
WORKDIR /app
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

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

# Правильный CMD array format
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["python3", "/app/unifi_ldap_sync/main.py"]
