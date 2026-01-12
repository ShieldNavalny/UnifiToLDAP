"""Конфигурация из переменных окружения."""
import os
import logging
from pathlib import Path
from typing import Dict, Any

def load_config() -> Dict[str, Any]:
    """Загрузка конфигурации из ENV."""
    
    # Unifi Token из файла
    token_file = os.getenv('UNIFI_TOKEN_FILE', '/run/secrets/unifi_token')
    try:
        unifi_token = Path(token_file).read_text().strip()
    except FileNotFoundError:
        raise ValueError(f"Unifi token file not found: {token_file}")
    
    config = {
        'unifi': {
            'base_url': f"https://{os.getenv('UNIFI_DOMAIN')}.ui.com",
            'token': unifi_token,
        },
        'sync': {
            'site_name': os.getenv('SITE_NAME', 'HQ'),
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
        config['ldap']['base_dn'],
        config['ldap']['admin_dn'],
        config['ldap']['admin_password'],
        config['unifi']['token'],
    ]
    
    if not all(required):
        raise ValueError("Missing required environment variables")
    
    return config
