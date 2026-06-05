# services/sync-service/app/core/conflict_resolver.py
"""Conflict resolution strategies for sync"""

import logging
from typing import Dict, Any, Tuple
from datetime import datetime

from ..database import ConflictStrategy

logger = logging.getLogger(__name__)


class ConflictResolver:
    """Resolve conflicts between client and server versions"""
    
    def __init__(self):
        self.strategies = {
            "last_write_wins": self._last_write_wins,
            "server_wins": self._server_wins,
            "client_wins": self._client_wins,
            "merge": self._merge,
            "manual": self._manual
        }
    
    async def resolve(
        self,
        entity_type: str,
        entity_id: str,
        client_version: Dict[str, Any],
        server_version: Dict[str, Any],
        client_version_num: int,
        server_version_num: int
    ) -> Dict[str, Any]:
        """Resolve conflict based on strategy"""
        
        # Default to last_write_wins
        strategy = ConflictStrategy.LAST_WRITE_WINS
        
        # Check timestamps for last_write_wins
        client_time = client_version.get('updated_at') or client_version.get('last_modified')
        server_time = server_version.get('updated_at') or server_version.get('last_modified')
        
        if client_time and server_time:
            if client_time > server_time:
                return {
                    "strategy": "auto_resolved",
                    "resolved_data": client_version,
                    "chosen": "client"
                }
            else:
                return {
                    "strategy": "auto_resolved",
                    "resolved_data": server_version,
                    "chosen": "server"
                }
        
        # Use version numbers as fallback
        if client_version_num > server_version_num:
            return {
                "strategy": "auto_resolved",
                "resolved_data": client_version,
                "chosen": "client"
            }
        elif server_version_num > client_version_num:
            return {
                "strategy": "auto_resolved",
                "resolved_data": server_version,
                "chosen": "server"
            }
        
        # If versions are equal, try to merge
        merged = self._merge_fields(client_version, server_version)
        if merged:
            return {
                "strategy": "auto_resolved",
                "resolved_data": merged,
                "chosen": "merged"
            }
        
        # No auto-resolution possible
        return {
            "strategy": "manual",
            "resolved_data": None,
            "chosen": None
        }
    
    async def auto_resolve(
        self,
        client_version: Dict[str, Any],
        server_version: Dict[str, Any],
        strategy: str
    ) -> Dict[str, Any]:
        """Automatically resolve using specified strategy"""
        
        resolver = self.strategies.get(strategy, self._last_write_wins)
        return resolver(client_version, server_version)
    
    def _last_write_wins(self, client: Dict, server: Dict) -> Dict:
        """Keep the version with the latest timestamp"""
        
        client_time = client.get('updated_at') or client.get('last_modified', 0)
        server_time = server.get('updated_at') or server.get('last_modified', 0)
        
        if isinstance(client_time, str):
            client_time = datetime.fromisoformat(client_time.replace('Z', '+00:00'))
        if isinstance(server_time, str):
            server_time = datetime.fromisoformat(server_time.replace('Z', '+00:00'))
        
        return client if client_time > server_time else server
    
    def _server_wins(self, client: Dict, server: Dict) -> Dict:
        """Always keep server version"""
        return server
    
    def _client_wins(self, client: Dict, server: Dict) -> Dict:
        """Always keep client version"""
        return client
    
    def _merge(self, client: Dict, server: Dict) -> Dict:
        """Merge non-conflicting fields"""
        return self._merge_fields(client, server)
    
    def _manual(self, client: Dict, server: Dict) -> Dict:
        """Manual resolution needed"""
        raise ValueError("Manual resolution required")
    
    def _merge_fields(self, client: Dict, server: Dict) -> Dict:
        """Merge non-conflicting fields from both versions"""
        
        merged = server.copy()
        conflicts = []
        
        for key, client_value in client.items():
            if key not in server:
                merged[key] = client_value
            elif client_value != server[key]:
                conflicts.append(key)
        
        # If there are conflicts, don't auto-merge
        if conflicts:
            return None
        
        return merged
    
    def _is_mergeable(self, client: Dict, server: Dict) -> bool:
        """Check if two versions can be merged"""
        
        for key in client:
            if key in server and client[key] != server[key]:
                # Check if it's a list field (can be merged)
                if isinstance(client[key], list) and isinstance(server[key], list):
                    continue
                # Check if it's a dict field (can be deep merged)
                elif isinstance(client[key], dict) and isinstance(server[key], dict):
                    continue
                else:
                    return False
        
        return True
    
    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """Deep merge two dictionaries"""
        
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result