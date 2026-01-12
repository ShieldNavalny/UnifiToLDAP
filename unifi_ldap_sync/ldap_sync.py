"""Синхронизация пользователей Unifi → OpenLDAP LDIF."""
import logging
import os
import tempfile
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
import subprocess
from .config import load_config

logger = logging.getLogger(__name__)

def transform_users_to_ldif(users: List[Dict[str, Any]], base_dn: str) -> str:
    """Правильный парсинг snake_case полей."""
    ldif_lines = []
    
    for user in users:
        profile = user.get('profile', {})
        
        # Реальные имена полей из API
        email = profile.get('email')
        firstname = profile.get('first_name') or 'Unknown'
        lastname = profile.get('last_name') or 'User'
        full_name = f"{firstname} {lastname}".strip() or 'Unifi User'

        # Если учетка службеная (Land) то она не нужна в LDAP        
        if 'land' in lastname.lower():
            logger.info(f"Skipped user (Land filter): {profile.get('email')} - {lastname}")
            continue
        
        # Телефон
        area_code = profile.get('area_code', '')
        mobile_phone = profile.get('mobile_phone', '')
        phone = f"{area_code}{mobile_phone}".strip() if area_code or mobile_phone else ''
        
        alias = profile.get('alias') or full_name
        
        # DN по email или ID
        if email:
            dn = f"mail={email},{base_dn}"
        else:
            dn = f"uid={user['id'][:8]},{base_dn}"
        
        ldif = f"""dn: {dn}
objectClass: inetOrgPerson
cn: {full_name}
sn: {lastname}
givenName: {firstname}
mail: {email or f"user_{user['id'][:8]}@fallback.com"}
displayName: {alias}
telephoneNumber: {phone}
uid: {user['id']}
description: Unifi status={user.get('status')} id={user['id']}
"""
        ldif_lines.append(ldif)
    
    return '\n\n'.join(ldif_lines)


def backup_ldap(config: Dict[str, Any]) -> Path:
    """Бэкап текущей LDAP БД."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = Path(config['ldap']['config_dir']) / f"backup_{timestamp}"
    
    subprocess.run([
        'slapcat', '-n', '0', '-l', str(backup_path.with_suffix('.ldif'))
    ], check=True)
    
    logger.info(f"Backup created: {backup_path}.ldif")
    return backup_path

import tempfile

def sync_users_to_ldap(users: List[Dict[str, Any]], config: Dict[str, Any]):
    base_dn = config['ldap']['base_dn']
    
    ldif_content = transform_users_to_ldif(users, base_dn)
    logger.info(f"Transformed {len(users)} users")
    
    backup_path = backup_ldap(config)
    
    temp_ldif = Path('/tmp') / 'unifi-users.ldif'
    temp_ldif.write_text(ldif_content)
    
    # Temp пароль
    pw_file = tempfile.NamedTemporaryFile(mode='w', delete=False)
    pw_file.write(open('/run/secrets/ldap_rootpw').read().strip())
    pw_file.close()
    
    try:
        cmd = [
            'ldapmodify',
            '-x', '-D', 'cn=admin,dc=navalny,dc=com',
            '-y', pw_file.name,  # Пароль из файла!
            '-f', str(temp_ldif),
            '-c'  # Continue
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0 or result.returncode == 68:  # 68=some changes skipped OK
            logger.info("✅ LDAP modified successfully!")
        else:
            logger.error(f"ldapmodify failed: {result.stderr}")
            raise subprocess.CalledProcessError(result.returncode, cmd)
    
    finally:
        temp_ldif.unlink(missing_ok=True)
        os.unlink(pw_file.name)
