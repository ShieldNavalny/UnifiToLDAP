#!/bin/bash
# /ldap/entrypoint.sh - генерит хеш из секрета при старте

set -e

LDAP_ROOTPW_FILE="/run/secrets/ldap_rootpw"
if [ -f "$LDAP_ROOTPW_FILE" ]; then
    ROOTPW_HASH=$(slappasswd -s "$(cat $LDAP_ROOTPW_FILE)")
    sed -i "s|rootpw .*|{SSHA}$ROOTPW_HASH|" /etc/ldap/slapd.conf
    echo "Rootpw hash generated from secret"
fi

# Инициализация БД если пустая
if [ ! -f /var/lib/ldap/data.mdb ]; then
    slapadd -n 0 -F /etc/ldap/slapd.d -l /etc/ldap/init.ldif
    echo "LDAP initialized"
fi

exec "$@"
