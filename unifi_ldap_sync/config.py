"""Конфигурация из environment variables и секретов."""
import os
import logging
from pathlib import Path
from typing import Dict, Any

def load_config() -> Dict[str, Any]:
    """Загружает конфигурацию с проверкой обязательных полей."""
    config = {
        'unifi': {
            'domain': os.getenv('UNIFI_DOMAIN'),
            'token': _get_token(),
            'base_url': None,  # Будет сформировано
        },
        'ldap': {
            'ldif_path': '/var/lib/ldap/unifi-users.ldif',
            'config_dir': '/etc/ldap/slapd.d',
            'base_dn': os.getenv('LDAP_BASE_DN', 'ou=users,dc=example,dc=com'),
        },
        'sync': {
            'site_name': os.getenv('SITE_NAME', 'ACF / HQ'),
            'interval_seconds': int(os.getenv('SYNC_INTERVAL', '300')),  # 5 минут
            'active_status': 'ACTIVED',  # Из API docs
        },
        'logging': {
            'level': getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
        },
    }
    
    # Формируем base_url
    if config['unifi']['domain']:
        config['unifi']['base_url'] = f"https://{config['unifi']['domain']}.ui.com"
    
    # Валидация
    _validate_config(config)
    
    return config

def _get_token() -> str:
    """Читает токен из env или секрета."""
    token = os.getenv('UNIFI_TOKEN')
    if token:
        return token
    
    token_file = os.getenv('UNIFI_TOKEN_FILE', '/run/secrets/unifi_token')
    if Path(token_file).exists():
        return Path(token_file).read_text().strip()
    
    raise ValueError("UNIFI_TOKEN или секрет unifi_token обязателен")

def _validate_config(config: Dict[str, Any]):
    """Проверяет обязательные параметры."""
    missing = []
    if not config['unifi']['domain']:
        missing.append('UNIFI_DOMAIN')
    if not config['unifi']['token']:
        missing.append('UNIFI_TOKEN')
    if not config['ldap']['base_dn']:
        missing.append('LDAP_BASE_DN')
    
    if missing:
        raise ValueError(f"Отсутствуют обязательные параметры: {', '.join(missing)}")
