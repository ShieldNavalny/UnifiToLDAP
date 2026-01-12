"""Главная точка входа - бесконечный цикл синхронизации."""
import logging
import time
import signal
import sys
from typing import Dict, Any
from pathlib import Path

from .config import load_config
from .unifi_client import UnifiClient
from .ldap_sync import sync_users_to_ldap

def signal_handler(sig, frame):
    """Graceful shutdown."""
    logger = logging.getLogger(__name__)  
    logger.info("Shutdown signal received")
    sys.exit(0)

def main():
    """Основной цикл синхронизации."""
    config = load_config()
    
    # Logging setup
    logging.basicConfig(
        level=config['logging']['level'],
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('/var/log/unifi-ldap-sync.log')
        ]
    )

    logger = logging.getLogger(__name__)  
    logger.info("Starting Unifi→LDAP sync")
    logger.info(f"Site: {config['sync']['site_name']}")
    logger.info(f"LDAP base: {config['ldap']['base_dn']}")
    
    # Graceful shutdown
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    client = UnifiClient(config)
    
    while True:
        try:
            # 1. Найти site_id
            site_id = client.get_site_id(config['sync']['site_name'])

            # 2. Получить активных пользователей
            users = client.get_all_active_users(site_id)
            
            # 3. Синхронизировать в LDAP
            sync_users_to_ldap(users, config)
            
            logger.info(f"Sync completed: {len(users)} users")
            
        except Exception as e:
            logger.error(f"Sync failed: {e}", exc_info=True)
        
        # Sleep
        logger.debug(f"Sleeping {config['sync']['interval_seconds']}s...")
        time.sleep(config['sync']['interval_seconds'])

if __name__ == '__main__':
    main()
