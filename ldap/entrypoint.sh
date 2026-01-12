#!/bin/bash
set -e

# 1. Rootpw из секрета
if [ -f /run/secrets/ldap_rootpw ]; then
    ROOTPW=$(cat /run/secrets/ldap_rootpw)
    ROOTPW_HASH=$(slappasswd -s "$ROOTPW")
    
    # Полная замена строки rootpw
    sed -i '/rootpw /d' /etc/ldap/slapd.conf  # Удалить старую
    sed -i "/suffix/,/rootdn/i rootpw $ROOTPW_HASH" /etc/ldap/slapd.conf  # Добавить новую
    echo "Rootpw updated: $ROOTPW_HASH"
fi

# 2. Тест конфига
slaptest -f /etc/ldap/slapd.conf || echo "Config test failed!"

# 3. Init БД
if [ ! -f /var/lib/ldap/data.mdb ]; then
    echo "Initializing database..."
    slapadd -n 0 -l /etc/ldap/init.ldif -f /etc/ldap/slapd.conf -d /var/lib/ldap
fi

service slapd start

# 4. Тест авторизации
sleep 2
echo "$ROOTPW" | ldapwhoami -x -D "cn=admin,dc=navalny,dc=com" -w - || echo "Auth test failed!"
echo "LDAP ready"

exec "$@"
