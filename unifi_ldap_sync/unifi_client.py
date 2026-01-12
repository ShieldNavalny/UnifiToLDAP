"""
UniFi Access Local API Client
Работает с локальным роутером через https://HOST:12445
"""

import logging
import requests
from typing import List, Dict, Any
from urllib3.exceptions import InsecureRequestWarning

# Отключаем предупреждения о самоподписанных сертификатах
requests.packages.urllib3.disable_warnings(InsecureRequestWarning) # type: ignore

logger = logging.getLogger(__name__)


class UniFiClient:
    
    def __init__(self, hostname: str, port: int, api_token: str, verify_ssl: bool = False):
        """
        Args:
            hostname: IP адрес или hostname роутера (например 192.168.1.100)
            port: Порт API (по умолчанию 12445)
            api_token: API токен из Settings > Advanced > API Token
            verify_ssl: Проверять SSL сертификат (False для самоподписанного)
        """
        self.base_url = f"https://{hostname}:{port}/api/v1/developer"
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {api_token}',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
        self.session.verify = verify_ssl
        
        logger.info(f"Initialized UniFi Access client: {self.base_url}")

    def should_skip_user(self, user_data: Dict[str, Any]) -> bool:
        """
        Проверяет, нужно ли пропустить пользователя ибо это техперсонал.
        Фильтр: в фамилии есть слово 'land' как отдельное слово.
        """
        lastname = user_data.get('last_name', '')
        
        if 'land' in lastname.lower():
            email = user_data.get('email', 'unknown')
            logger.info(
                f"Skipping technical account (lastname contains word 'land'): {email}"
            )
            return True
        
        return False

    def get_all_users(self) -> List[Dict[str, Any]]:
        """
        Получает всех пользователей.
        
        Endpoint: GET /api/v1/developer/users?expand=accesspolicy
        
        Returns:
            List[Dict]: Список пользователей с полями:
                - id: UUID пользователя
                - firstname, lastname: Имя
                - email: Email
                - employeenumber: идентификационный номер
                - status: ACTIVE/DEACTIVATED/SUSPENDED
                - nfccards: [{id, token}]
                - pincode: {token}
                - accesspolicies: [...]
        """
        all_users = []
        page_num = 1
        page_size = 100
        
        while True:
            params = {
                'pagenum': page_num,
                'pagesize': page_size,
                'expand': 'accesspolicy'
            }
            
            logger.debug(f"Fetching users page {page_num}")
            
            try:
                response = self.session.get(
                    f"{self.base_url}/users",
                    params=params,
                    timeout=30
                )
                response.raise_for_status()
                data = response.json()
                
                if data.get('code') != 'SUCCESS':
                    logger.error(f"API returned error: {data.get('msg')}")
                    break
                
                users = data.get('data', [])
                if not users:
                    break
                
                all_users.extend(users)
                logger.info(f"Fetched page {page_num}: {len(users)} users")
                
                # Проверяем есть ли еще страницы
                pagination = data.get('pagination', {})
                total = pagination.get('total', 0)
                if len(all_users) >= total:
                    break
                
                page_num += 1
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Request failed: {e}")
                raise
        
        logger.info(f"Total users fetched: {len(all_users)}")
        return all_users

    def get_active_users(self) -> List[Dict[str, Any]]:
        """
        Фильтрует только активных пользователей (исключая техперсонал).
        
        Returns:
            List[Dict]: Пользователи со статусом ACTIVE, без техперсонала
        """
        all_users = self.get_all_users()
        
        active_users = [
            user for user in all_users
            if user.get('status') == 'ACTIVE' 
            and not self.should_skip_user(user)
        ]
        
        logger.info(
            f"Filtered: {len(active_users)} active users "
            f"(from {len(all_users)} total)"
        )
        
        return active_users
