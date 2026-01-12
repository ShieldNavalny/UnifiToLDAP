"""Синхронизация пользователей UniFi → OpenLDAP через ldap3."""
import logging
from typing import List, Dict, Any, Set
from ldap3 import Server, Connection, ALL, SUBTREE, MODIFY_REPLACE


logger = logging.getLogger(__name__)


class LDAPSync:
    def __init__(self, config: Dict[str, Any]):
        self.host = config['ldap']['host']
        self.port = config['ldap']['port']
        self.admin_dn = config['ldap']['admin_dn']
        self.admin_pw = config['ldap']['admin_password']
        self.base_dn = config['ldap']['base_dn']
        self.conn = None
    
    def connect(self):
        """Подключение к LDAP серверу."""
        server = Server(f'{self.host}:{self.port}', get_info=ALL)
        self.conn = Connection(
            server,
            user=self.admin_dn,
            password=self.admin_pw,
            auto_bind=True
        )
        logger.info(f"✅ Connected to LDAP: {self.host}:{self.port}")
    
    def disconnect(self):
        """Отключение от LDAP."""
        if self.conn:
            self.conn.unbind()
    
    def initialize_structure(self):
        """Создать OU=users если не существует."""
        self.connect()
        try:
            ou_dn = f"ou=users,{self.base_dn}"
            
            # Проверяем существование
            self.conn.search(ou_dn, '(objectClass=*)', search_scope='BASE')
            if self.conn.entries:
                logger.info("OU=users already exists")
                return
            
            # Создаем OU
            self.conn.add(
                ou_dn,
                ['organizationalUnit'],
                {
                    'ou': 'users',
                    'description': 'UniFi Access Users'
                }
            )
            
            if self.conn.result['result'] == 0:
                logger.info(f"✅ Created OU: {ou_dn}")
            else:
                logger.warning(f"Failed to create OU: {self.conn.result}")
            
        except Exception as e:
            logger.error(f"Failed to initialize LDAP structure: {e}")
            raise
        finally:
            self.disconnect()
    
    def get_existing_users(self) -> Dict[str, str]:
        """
        Получить существующих пользователей из LDAP.
        
        Returns:
            Dict[uid, dn]: Словарь {uid: dn} для всех пользователей
        """
        try:
            self.conn.search(
                f"ou=users,{self.base_dn}",
                '(objectClass=inetOrgPerson)',
                search_scope=SUBTREE,
                attributes=['uid']
            )
            return {
                entry.uid.value: entry.entry_dn 
                for entry in self.conn.entries 
                if hasattr(entry, 'uid')
            }
        except Exception as e:
            logger.warning(f"Error getting existing users: {e}")
            return {}
    
    def delete_obsolete_users(self, current_uids: Set[str], existing_users: Dict[str, str]):
        """
        Удалить пользователей из LDAP, которых нет в UniFi.
        
        Args:
            current_uids: SetUID пользователей из UniFi
            existing_users: Dict {uid: dn} пользователей из LDAP
        """
        obsolete_uids = set(existing_users.keys()) - current_uids
        
        if not obsolete_uids:
            logger.info("No obsolete users to delete")
            return
        
        deleted = 0
        errors = 0
        
        for uid in obsolete_uids:
            dn = existing_users[uid]
            try:
                self.conn.delete(dn)
                if self.conn.result['result'] == 0:
                    logger.info(f"🗑️  Deleted obsolete user: {uid}")
                    deleted += 1
                else:
                    logger.warning(f"Delete failed {uid}: {self.conn.result}")
                    errors += 1
            except Exception as e:
                logger.warning(f"Delete exception {uid}: {e}")
                errors += 1
        
        logger.info(f"🗑️  Deleted {deleted} obsolete users ({errors} errors)")
    
    def sync_users(self, users: List[Dict[str, Any]]):
        """Синхронизация списка пользователей."""
        self.connect()
        try:
            existing_users = self.get_existing_users()
            added = 0
            updated = 0
            errors = 0
            
            # Множество текущих UID из UniFi
            current_uids = set()
            
            for user in users:
                # Для локального API структура другая - нет вложенного profile
                uid = user['id']
                current_uids.add(uid)
                
                email = user.get('useremail', f'user_{uid[:8]}@fallback.com')
                firstname = user.get('firstname', 'Unknown')
                lastname = user.get('lastname', 'User')
                cn = f"{firstname} {lastname}".strip()
                
                dn = f"uid={uid},ou=users,{self.base_dn}"
                
                attrs = {
                    'cn': cn,
                    'sn': lastname,
                    'givenName': firstname,
                    'mail': email,
                    'uid': uid
                }
                
                # Добавить телефон если есть
                phone = user.get('phone', '').strip()
                if phone:
                    attrs['telephoneNumber'] = phone
                
                if uid in existing_users:
                    # Обновление существующего
                    try:
                        changes = {k: [(MODIFY_REPLACE, [v])] for k, v in attrs.items()}
                        self.conn.modify(dn, changes)
                        
                        if self.conn.result['result'] == 0:
                            logger.debug(f"Updated: {email}")
                            updated += 1
                        else:
                            logger.warning(f"Update failed {email}: {self.conn.result}")
                            errors += 1
                    except Exception as e:
                        logger.warning(f"Update exception {email}: {e}")
                        errors += 1
                else:
                    # Создание нового
                    try:
                        self.conn.add(
                            dn,
                            ['inetOrgPerson'],
                            attrs
                        )
                        
                        if self.conn.result['result'] == 0:
                            logger.info(f"✅ Added: {email}")
                            added += 1
                        else:
                            logger.warning(f"Add failed {email}: {self.conn.result}")
                            errors += 1
                    except Exception as e:
                        logger.warning(f"Add exception {email}: {e}")
                        errors += 1
            
            # Удаляем устаревших пользователей
            self.delete_obsolete_users(current_uids, existing_users)
            
            logger.info(f"🔄 Sync completed: {added} added, {updated} updated, {errors} errors")
        finally:
            self.disconnect()
