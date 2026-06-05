# services/sync-service/app/core/sync_engine.py
"""Core sync engine for offline-first synchronization"""

import asyncio
import json
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from uuid import uuid4
import logging

from sqlalchemy import select, and_, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import AsyncSessionLocal, SyncQueue, SyncLog, SyncConflict, DeviceSyncState, SyncStatus, EntityType
from ..config import settings
from .conflict_resolver import ConflictResolver

logger = logging.getLogger(__name__)


class SyncEngine:
    """Main sync engine handling data synchronization between devices and cloud"""
    
    def __init__(self):
        self.active_syncs = {}
        self.conflict_resolver = ConflictResolver()
        
    async def initialize(self):
        """Initialize sync engine"""
        logger.info("Sync engine initialized")
    
    async def enqueue_sync_item(
        self,
        device_id: str,
        user_id: str,
        entity_type: EntityType,
        entity_id: str,
        entity_data: Dict[str, Any],
        version: int = 1
    ) -> str:
        """Add item to sync queue"""
        
        async with AsyncSessionLocal() as session:
            sync_item = SyncQueue(
                device_id=device_id,
                user_id=user_id,
                entity_type=entity_type,
                entity_id=entity_id,
                entity_data=entity_data,
                version=version,
                last_modified=datetime.utcnow()
            )
            
            session.add(sync_item)
            await session.commit()
            
            logger.debug(f"Enqueued sync item {entity_id} for device {device_id}")
            return str(sync_item.id)
    
    async def sync_device(
        self,
        device_id: str,
        user_id: str,
        sync_token: Optional[str] = None,
        changes: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Perform full sync for a device"""
        
        sync_id = str(uuid4())
        self.active_syncs[sync_id] = {
            "device_id": device_id,
            "started_at": datetime.utcnow()
        }
        
        try:
            # Create sync log
            sync_log = SyncLog(
                sync_id=sync_id,
                device_id=device_id,
                user_id=user_id,
                status=SyncStatus.SYNCING,
                started_at=datetime.utcnow()
            )
            
            async with AsyncSessionLocal() as session:
                session.add(sync_log)
                await session.commit()
            
            # Process incoming changes from device
            synced_items = []
            failed_items = []
            
            if changes:
                for change in changes:
                    try:
                        result = await self._process_change(
                            device_id,
                            user_id,
                            change
                        )
                        if result:
                            synced_items.append(change.get('entity_id'))
                        else:
                            failed_items.append(change.get('entity_id'))
                    except Exception as e:
                        logger.error(f"Failed to process change: {e}")
                        failed_items.append(change.get('entity_id'))
            
            # Get pending items for device
            pending_items = await self._get_pending_items(device_id, user_id)
            
            # Update device sync state
            await self._update_device_sync_state(
                device_id,
                user_id,
                sync_token,
                len(synced_items),
                len(failed_items)
            )
            
            # Update sync log
            async with AsyncSessionLocal() as session:
                await session.execute(
                    update(SyncLog)
                    .where(SyncLog.sync_id == sync_id)
                    .values(
                        entities_synced=len(synced_items),
                        entities_failed=len(failed_items),
                        status=SyncStatus.COMPLETED if not failed_items else SyncStatus.COMPLETED,
                        completed_at=datetime.utcnow()
                    )
                )
                await session.commit()
            
            return {
                "sync_id": sync_id,
                "status": "success",
                "synced_items": synced_items,
                "failed_items": failed_items,
                "pending_items": pending_items,
                "new_sync_token": await self._generate_sync_token(device_id)
            }
            
        except Exception as e:
            logger.error(f"Sync failed for device {device_id}: {e}")
            
            # Update sync log with error
            async with AsyncSessionLocal() as session:
                await session.execute(
                    update(SyncLog)
                    .where(SyncLog.sync_id == sync_id)
                    .values(
                        status=SyncStatus.FAILED,
                        error_message=str(e),
                        completed_at=datetime.utcnow()
                    )
                )
                await session.commit()
            
            raise
        finally:
            if sync_id in self.active_syncs:
                del self.active_syncs[sync_id]
    
    async def _process_change(
        self,
        device_id: str,
        user_id: str,
        change: Dict[str, Any]
    ) -> bool:
        """Process a single change from device"""
        
        entity_type = EntityType(change.get('entity_type'))
        entity_id = change.get('entity_id')
        operation = change.get('operation')  # create, update, delete
        data = change.get('data', {})
        version = change.get('version', 1)
        
        async with AsyncSessionLocal() as session:
            # Check for conflicts
            existing = await self._get_existing_entity(session, entity_type, entity_id)
            
            if existing and existing.version > version:
                # Conflict detected
                conflict = await self.conflict_resolver.resolve(
                    entity_type=entity_type,
                    entity_id=entity_id,
                    client_version=data,
                    server_version=existing.entity_data,
                    client_version_num=version,
                    server_version_num=existing.version
                )
                
                if conflict['strategy'] == 'auto_resolved':
                    # Apply resolved version
                    await self._apply_resolution(
                        session,
                        entity_type,
                        entity_id,
                        conflict['resolved_data'],
                        version
                    )
                    return True
                else:
                    # Store conflict for manual resolution
                    await self._store_conflict(
                        session,
                        entity_type,
                        entity_id,
                        data,
                        existing.entity_data,
                        version,
                        existing.version
                    )
                    return False
            
            # No conflict, apply change
            if operation == 'delete':
                await self._delete_entity(session, entity_type, entity_id)
            else:
                await self._upsert_entity(
                    session,
                    entity_type,
                    entity_id,
                    data,
                    version,
                    user_id,
                    device_id
                )
            
            await session.commit()
            return True
    
    async def _get_pending_items(
        self,
        device_id: str,
        user_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get pending items for device"""
        
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(SyncQueue)
                .where(
                    and_(
                        SyncQueue.device_id == device_id,
                        SyncQueue.user_id == user_id,
                        SyncQueue.sync_status == SyncStatus.PENDING
                    )
                )
                .limit(limit)
            )
            
            items = result.scalars().all()
            
            return [
                {
                    "id": str(item.id),
                    "entity_type": item.entity_type.value,
                    "entity_id": item.entity_id,
                    "data": item.entity_data,
                    "version": item.version
                }
                for item in items
            ]
    
    async def mark_synced(self, sync_item_ids: List[str]) -> None:
        """Mark items as successfully synced"""
        
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(SyncQueue)
                .where(SyncQueue.id.in_(sync_item_ids))
                .values(
                    sync_status=SyncStatus.COMPLETED,
                    synced_at=datetime.utcnow()
                )
            )
            await session.commit()
    
    async def mark_failed(
        self,
        sync_item_ids: List[str],
        error_message: str,
        retry: bool = True
    ) -> None:
        """Mark items as failed"""
        
        async with AsyncSessionLocal() as session:
            if retry:
                await session.execute(
                    update(SyncQueue)
                    .where(SyncQueue.id.in_(sync_item_ids))
                    .values(
                        sync_status=SyncStatus.PENDING,
                        retry_count=SyncQueue.retry_count + 1,
                        error_message=error_message,
                        updated_at=datetime.utcnow()
                    )
                )
            else:
                await session.execute(
                    update(SyncQueue)
                    .where(SyncQueue.id.in_(sync_item_ids))
                    .values(
                        sync_status=SyncStatus.FAILED,
                        error_message=error_message,
                        updated_at=datetime.utcnow()
                    )
                )
            await session.commit()
    
    async def _update_device_sync_state(
        self,
        device_id: str,
        user_id: str,
        sync_token: Optional[str],
        synced_count: int,
        failed_count: int
    ) -> None:
        """Update device sync state"""
        
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(DeviceSyncState).where(DeviceSyncState.device_id == device_id)
            )
            state = result.scalar_one_or_none()
            
            if state:
                state.last_sync_at = datetime.utcnow()
                state.last_heartbeat = datetime.utcnow()
                state.total_syncs += 1
                if failed_count == 0:
                    state.successful_syncs += 1
                else:
                    state.failed_syncs += 1
            else:
                state = DeviceSyncState(
                    device_id=device_id,
                    user_id=user_id,
                    last_sync_at=datetime.utcnow(),
                    last_heartbeat=datetime.utcnow(),
                    total_syncs=1
                )
                session.add(state)
            
            await session.commit()
    
    async def _generate_sync_token(self, device_id: str) -> str:
        """Generate a sync token for incremental sync"""
        
        token_data = f"{device_id}:{datetime.utcnow().timestamp()}"
        return hashlib.sha256(token_data.encode()).hexdigest()
    
    async def _get_existing_entity(self, session: AsyncSession, entity_type: EntityType, entity_id: str):
        """Get existing entity from database"""
        # This would query the actual entity tables
        # For now, return None for demo
        return None
    
    async def _upsert_entity(self, session, entity_type, entity_id, data, version, user_id, device_id):
        """Upsert entity to database"""
        # This would update the actual entity tables
        pass
    
    async def _delete_entity(self, session, entity_type, entity_id):
        """Delete entity from database"""
        pass
    
    async def _store_conflict(self, session, entity_type, entity_id, client_data, server_data, client_version, server_version):
        """Store conflict for manual resolution"""
        
        conflict = SyncConflict(
            entity_type=entity_type,
            entity_id=entity_id,
            client_version=client_data,
            server_version=server_data,
            client_version_num=client_version,
            server_version_num=server_version,
            resolution_strategy=ConflictResolver.MANUAL
        )
        session.add(conflict)
        await session.commit()
    
    async def get_sync_status(self, device_id: str) -> Dict[str, Any]:
        """Get sync status for device"""
        
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(DeviceSyncState).where(DeviceSyncState.device_id == device_id)
            )
            state = result.scalar_one_or_none()
            
            if not state:
                return {
                    "device_id": device_id,
                    "is_registered": False,
                    "pending_syncs": 0
                }
            
            # Count pending items
            pending_result = await session.execute(
                select(SyncQueue)
                .where(
                    and_(
                        SyncQueue.device_id == device_id,
                        SyncQueue.sync_status == SyncStatus.PENDING
                    )
                )
            )
            pending_count = len(pending_result.scalars().all())
            
            return {
                "device_id": device_id,
                "is_registered": True,
                "last_sync_at": state.last_sync_at.isoformat() if state.last_sync_at else None,
                "last_heartbeat": state.last_heartbeat.isoformat() if state.last_heartbeat else None,
                "pending_syncs": pending_count,
                "total_syncs": state.total_syncs,
                "successful_syncs": state.successful_syncs,
                "failed_syncs": state.failed_syncs,
                "is_active": state.is_active
            }