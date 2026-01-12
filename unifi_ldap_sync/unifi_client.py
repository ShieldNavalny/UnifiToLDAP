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
        """Полная пагинация по pagination.total."""
        all_policies = []
        page_num = 1
        
        while True:
            params = {
                'page_num': page_num,
                'page_size': 200,
                'site_id': site_id,
            }
            
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
            pagination = data.get('pagination', {})
            
            # Логирование pagination
            total = pagination.get('total', 0)
            page_size = pagination.get('page_size', 0)
            logger.info(f"Page {page_num}: {len(policies)} policies, "
                    f"total={total}, page_size={page_size}")
            
            if not policies:
                break
            
            all_policies.extend(policies)
            page_num += 1
            
            # Если знаем total, можем оптимизировать
            if total and len(all_policies) >= total:
                break
        
        logger.info(f"Total policies fetched: {len(all_policies)} / {total}") # type: ignore
        return all_policies

    
    def extract_user_ids_from_policies(self, policies: List[Dict[str, Any]]) -> Set[str]:
        """2-3. Извлекает уникальные user IDs."""
        user_ids: Set[str] = set()
        
        for policy in policies:
            users = policy.get('users')
            if users is None or not isinstance(users, list):
                logger.debug(f"Policy {policy.get('name', 'unknown')} has no users")
                continue
                
            for user in users:
                if isinstance(user, dict):
                    user_type = user.get('type')
                    if user_type in ['user', 'user_of_group']:
                        user_ids.add(user['id'])
        
        logger.info(f"Unique user/group IDs from policies: {len(user_ids)}")
        return user_ids
    
    def get_user_profile(self, user_id: str) -> Dict[str, Any]:
        """1.3 Fetch User по ID."""
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
    
    def get_all_active_users(self, site_id: str) -> List[Dict[str, Any]]:
        """Полный цикл: policies → user_ids → profiles."""
        # 1. Все policies
        policies = self.get_all_access_policies(site_id)
        
        # 2-3. Уникальные IDs
        user_ids = self.extract_user_ids_from_policies(policies)
        
        # 4. Fetch профилей
        users = []
        for user_id in user_ids:
            try:
                profile = self.get_user_profile(user_id)
                users.append(profile)
                time.sleep(1.5)
            except Exception as e:
                logger.warning(f"Failed user {user_id}: {e}")
        
        logger.info(f"Total active users fetched: {len(users)}")
        return users
