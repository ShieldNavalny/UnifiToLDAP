"""Главная точка входа - бесконечный цикл синхронизации."""
import logging
import time
import signal
import sys

from .config import load_config
from .unifi_client import UniFiClient
from .ldap_sync import LDAPSync


should_exit = False


def signal_handler(sig, frame):
    """Graceful shutdown."""
    global should_exit
    logger = logging.getLogger(__name__)
    logger.info("Shutdown signal received")
    should_exit = True


def main():
    """Основной цикл синхронизации."""
    config = load_config()
    
    # Logging setup
    logging.basicConfig(
        level=config['logging']['level'],
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[logging.StreamHandler()]
    )
    
    logger = logging.getLogger(__name__)
    logger.info("Starting UniFi Access → LDAP sync")
    logger.info(f"UniFi: {config['unifi']['hostname']}:{config['unifi']['port']}")
    logger.info(f"LDAP: {config['ldap']['host']}:{config['ldap']['port']}")
    logger.info(f"Base DN: {config['ldap']['base_dn']}")
    
    # Graceful shutdown
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Инициализация клиентов
    unifi_client = UniFiClient(
        hostname=config['unifi']['hostname'],
        port=config['unifi']['port'],
        api_token=config['unifi']['token'],
        verify_ssl=config['unifi']['verify_ssl']
    )
    ldap_sync = LDAPSync(config)
    
    # Инициализация LDAP структуры
    try:
        ldap_sync.initialize_structure()
    except Exception as e:
        logger.error(f"Failed to initialize LDAP: {e}")
        sys.exit(1)
    
    while not should_exit:
        try:
            # Получить активных пользователей из UniFi Access
            users = unifi_client.get_active_users()
            logger.info(f"Fetched {len(users)} users from UniFi Access")
            
            # Синхронизировать в LDAP
            ldap_sync.sync_users(users)
            
            logger.info(f"✅ Sync completed: {len(users)} users")
            
        except Exception as e:
            logger.error(f"❌ Sync failed: {e}", exc_info=True)
        
        # Sleep
        interval = config['sync']['interval_seconds']
        logger.info(f"Next sync in {interval}s...")
        
        for _ in range(interval):
            if should_exit:
                break
            time.sleep(1)
    
    logger.info("Exiting gracefully")


if __name__ == '__main__':
    main()
