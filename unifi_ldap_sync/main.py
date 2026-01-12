"""Главная точка входа - бесконечный цикл синхронизации."""
import logging
import time
import signal
import sys

from .config import load_config
from .unifi_client import UnifiClient
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
    logger.info("Starting Unifi→LDAP sync")
    logger.info(f"Unifi Site: {config['sync']['site_name']}")
    logger.info(f"LDAP: {config['ldap']['host']}:{config['ldap']['port']}")
    logger.info(f"Base DN: {config['ldap']['base_dn']}")
    
    # Graceful shutdown
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    unifi_client = UnifiClient(config)
    ldap_sync = LDAPSync(config)
    
    def initialize_ldap_structure(config):
        """Создать базовую структуру LDAP."""
        import subprocess
        logger = logging.getLogger(__name__)
        
        try:
            subprocess.run([
                'ldapadd', '-x',
                '-H', f"ldap://{config['ldap']['host']}:{config['ldap']['port']}",
                '-D', config['ldap']['admin_dn'],
                '-w', config['ldap']['admin_password']
            ], input=f"""
    dn: ou=users,{config['ldap']['base_dn']}
    objectClass: organizationalUnit
    ou: users
    description: Unifi Identity Users
    """.encode(), check=False, capture_output=True)
            logger.info("LDAP structure initialized")
        except Exception as e:
            logger.debug(f"LDAP init (probably already exists): {e}")

    initialize_ldap_structure(config)

    try:
        ldap_sync.initialize_structure()
    except Exception as e:
        logger.error(f"Failed to initialize LDAP: {e}")
        sys.exit(1)
    
    while not should_exit:
        try:
            # 1. Найти site_id
            site_id = unifi_client.get_site_id(config['sync']['site_name'])
            
            # 2. Получить активных пользователей
            users = unifi_client.get_all_active_users(site_id)
            logger.info(f"Fetched {len(users)} users from Unifi")
            
            # 3. Синхронизировать в LDAP
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
