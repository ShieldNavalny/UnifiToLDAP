"""Клиент Unifi Identity Enterprise API через Access Policies."""
import logging
import time
from typing import List, Dict, Any, Set
import requests
from .config import load_config


logger = logging.getLogger(__name__)


class UnifiClient:
    def __init__(self, config: Dict[str, Any]):
        self.base_url = config['unifi']['base_url']
        self.token = config['unifi']['token']
        self.headers = {
            'Authorization': f'Bearer {self.token}',
            'Accept': 'application/json',
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
        # Rate limiting configuration
        self.max_retries = 3
    
    def get_sites(self) -> List[Dict[str, Any]]:
        """Получает сайты."""
        response = self.session.get(f"{self.base_url}/gw/door-access/api/developer/sites")
        response.raise_for_status()
        data = response.json()
        return data.get('data', []) if data.get('code') == 'SUCCESS' else []
    
    def get_site_id(self, site_name: str) -> str:
        """Находит site_id по имени."""
        sites = self.get_sites()
        for site in sites:
            if site.get('name') == site_name:
                logger.info(f"Found site '{site_name}': {site['id']}")
                return site['id']
        raise ValueError(f"Site '{site_name}' not found")
    
    def get_all_access_policies(self, site_id: str) -> List[Dict[str, Any]]:
        """1. Получает ВСЕ access policies с пагинацией."""
        all_policies = []
        page_num = 1
        
        while True:
            params = {
                'page_num': page_num,
                'page_size': 200,
                'site_id': site_id,
            }
            logger.debug(f"Fetching policies page {page_num}: {params}")
            
            response = self.session.get(
                f"{self.base_url}/gw/permission/api/developer/access_policies",
                params=params
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get('code') != 'SUCCESS':
                logger.warning(f"Policies page {page_num} failed: {data}")
                break
            
            policies = data.get('data', [])
            if not policies:
                break
                
            all_policies.extend(policies)
            logger.info(f"Policies page {page_num}: {len(policies)}")
            
            page_num += 1
        
        logger.info(f"Total policies for site {site_id}: {len(all_policies)}")
        return all_policies
    
    def extract_user_ids_from_policies(self, policies: List[Dict[str, Any]]) -> Set[str]:
        """
        2-3. Извлекает уникальные user IDs.
        FIX: Фильтруем только type='user', исключаем type='user_of_group' (группы).
        """
        user_ids: Set[str] = set()
        group_count = 0
        
        for policy in policies:
            users = policy.get('users')
            if users is None or not isinstance(users, list):
                logger.debug(f"Policy {policy.get('name', 'unknown')} has no users")
                continue
                
            for user in users:
                if isinstance(user, dict):
                    user_type = user.get('type')
                    user_id = user.get('id')
                    
                    if user_type == 'user':
                        # Только пользователи
                        user_ids.add(user_id) # type: ignore
                    elif user_type == 'user_of_group':
                        # Это группа, не пользователь
                        group_count += 1
                        logger.debug(f"Skipping group ID: {user_id}")
                    else:
                        logger.warning(f"Unknown user type: {user_type}")
        
        logger.info(
            f"Unique user IDs from policies: {len(user_ids)} "
            f"(excluded {group_count} groups)"
        )
        return user_ids
    
    def should_skip_user(self, user_data: Dict[str, Any]) -> bool:
        """
        Проверяет, нужно ли пропустить пользователя ибо это техперсонал.
        Фильтр: в фамилии есть слово 'land' как отдельное слово.
        """
        profile = user_data.get('profile', {})
        lastname = profile.get('last_name') or ''
        
        if 'land' in lastname.lower():
            email = profile.get('email', 'unknown')
            logger.info(
                f"Skipping technical account (lastname contains word 'land'): {email}"
            )
            return True
        
        return False

    
    def get_user_profile(self, user_id: str) -> Dict[str, Any]: # type: ignore
        """
        1.3 Fetch User по ID.
        FIX: Добавлен retry с exponential backoff для 429 ошибок.
        """
        for attempt in range(self.max_retries):
            try:
                response = self.session.get(
                    f"{self.base_url}/gw/directory/api/developer/users/{user_id}"
                )
                response.raise_for_status()
                data = response.json()
                
                if data.get('code') != 'SUCCESS':
                    raise ValueError(f"User {user_id} fetch failed: {data}")
                
                user_data = data['data']
                if user_data.get('status') != 'ACTIVE':
                    raise ValueError(f"User {user_id} inactive")
                
                logger.debug(f"Fetched user {user_id}: {user_data['profile']['email']}")
                return user_data
                
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:
                    # Rate limit - exponential backoff
                    wait_time = (2 ** attempt) * 1  # 1s, 2s, 4s
                    logger.warning(
                        f"Rate limited (429) for user {user_id}, "
                        f"waiting {wait_time}s (attempt {attempt + 1}/{self.max_retries})"
                    )
                    time.sleep(wait_time)
                    
                    if attempt == self.max_retries - 1:
                        # Последняя попытка провалилась
                        raise
                else:
                    # Другая HTTP ошибка
                    raise
    
    def get_all_active_users(self, site_id: str) -> List[Dict[str, Any]]:
        """
        Полный цикл: policies → user_ids → profiles.
        FIX: Добавлена фильтрация пропускаемых пользователей.
        """
        # 1. Все policies
        policies = self.get_all_access_policies(site_id)
        
        # 2-3. Уникальные IDs (без групп)
        user_ids = self.extract_user_ids_from_policies(policies)
        
        # 4. Fetch профилей
        users = []
        failed_count = 0
        skipped_count = 0
        
        for user_id in user_ids:
            try:
                profile = self.get_user_profile(user_id)
                
                # Проверяем фильтры
                if self.should_skip_user(profile):
                    skipped_count += 1
                    continue
                
                users.append(profile)
                time.sleep(0.2)  # 200ms между запросами для rate limiting
                
            except Exception as e:
                logger.warning(f"Failed user {user_id}: {e}")
                failed_count += 1
        
        logger.info(
            f"Total active users fetched: {len(users)}, "
            f"failed: {failed_count}, skipped: {skipped_count}"
        )
        return users
