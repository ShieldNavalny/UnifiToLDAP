"""Конфигурация из переменных окружения."""
import os
import logging
from typing import Dict, Any


def load_config() -> Dict[str, Any]:
    """Загрузка конфигурации из ENV."""
    
    config = {
        'unifi': {
            'hostname': os.getenv('UNIFI_ACCESS_HOSTNAME'),
            'port': int(os.getenv('UNIFI_ACCESS_PORT', '12445')),
            'token': os.getenv('UNIFI_ACCESS_API_TOKEN'),
            'verify_ssl': os.getenv('UNIFI_ACCESS_VERIFY_SSL', 'false').lower() == 'true',
        },
        'sync': {
            'interval_seconds': int(os.getenv('SYNC_INTERVAL', '300')),
        },
        'ldap': {
            'host': os.getenv('LDAP_HOST', 'localhost'),
            'port': int(os.getenv('LDAP_PORT', '389')),
            'base_dn': os.getenv('LDAP_BASE_DN'),
            'admin_dn': os.getenv('LDAP_ADMIN_DN'),
            'admin_password': os.getenv('LDAP_ADMIN_PASSWORD'),
        },
        'logging': {
            'level': getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
        }
    }
    
    # Валидация обязательных полей
    required = [
        config['unifi']['hostname'],
        config['unifi']['token'],
        config['ldap']['base_dn'],
        config['ldap']['admin_dn'],
        config['ldap']['admin_password'],
    ]
    
    if not all(required):
        raise ValueError("Missing required environment variables")
    
    return config
