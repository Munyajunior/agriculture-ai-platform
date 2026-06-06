# services/sync-service/app/api/v1/conflicts.py
"""Conflict resolution endpoints"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from uuid import UUID

from ...database import AsyncSessionLocal, SyncConflict
from ...core.conflict_resolver import ConflictResolver
from ...schemas import ConflictResponse, ConflictResolutionRequest
from .dependencies import verify_device

router = APIRouter()
conflict_resolver = ConflictResolver()


@router.get("/", response_model=List[ConflictResponse])
async def list_conflicts(
    status: Optional[str] = "pending",
    entity_type: Optional[str] = None,
    limit: int = 100
):
    """List sync conflicts"""
    
    from sqlalchemy import select, and_
    
    async with AsyncSessionLocal() as session:
        query = select(SyncConflict)
        
        conditions = []
        if status:
            conditions.append(SyncConflict.status == status)
        if entity_type:
            conditions.append(SyncConflict.entity_type == entity_type)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        query = query.limit(limit)
        
        result = await session.execute(query)
        conflicts = result.scalars().all()
        
        return [
            ConflictResponse(
                id=conflict.id,
                entity_type=conflict.entity_type.value,
                entity_id=conflict.entity_id,
                client_version=conflict.client_version,
                server_version=conflict.server_version,
                resolution_strategy=conflict.resolution_strategy.value,
                status=conflict.status,
                created_at=conflict.created_at
            )
            for conflict in conflicts
        ]


@router.get("/{conflict_id}", response_model=ConflictResponse)
async def get_conflict(conflict_id: UUID):
    """Get conflict details"""
    
    from sqlalchemy import select
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(SyncConflict).where(SyncConflict.id == conflict_id)
        )
        conflict = result.scalar_one_or_none()
        
        if not conflict:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conflict not found"
            )
        
        return ConflictResponse(
            id=conflict.id,
            entity_type=conflict.entity_type.value,
            entity_id=conflict.entity_id,
            client_version=conflict.client_version,
            server_version=conflict.server_version,
            resolution_strategy=conflict.resolution_strategy.value,
            status=conflict.status,
            created_at=conflict.created_at
        )


@router.post("/{conflict_id}/resolve")
async def resolve_conflict(
    conflict_id: UUID,
    resolution: ConflictResolutionRequest
):
    """Resolve a sync conflict"""
    
    from sqlalchemy import select, update
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(SyncConflict).where(SyncConflict.id == conflict_id)
        )
        conflict = result.scalar_one_or_none()
        
        if not conflict:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conflict not found"
            )
        
        if conflict.status != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Conflict already {conflict.status}"
            )
        
        # Apply resolution
        await session.execute(
            update(SyncConflict)
            .where(SyncConflict.id == conflict_id)
            .values(
                resolved_version=resolution.resolution,
                resolved_by=resolution.strategy,
                resolved_at=datetime.utcnow(),
                status="resolved"
            )
        )
        
        await session.commit()
        
        return {
            "conflict_id": str(conflict_id),
            "status": "resolved",
            "resolution": resolution.resolution,
            "strategy": resolution.strategy
        }


@router.post("/{conflict_id}/resolve/auto")
async def auto_resolve_conflict(
    conflict_id: UUID,
    strategy: str = "last_write_wins"
):
    """Automatically resolve a conflict using specified strategy"""
    
    from sqlalchemy import select, update
    from datetime import datetime
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(SyncConflict).where(SyncConflict.id == conflict_id)
        )
        conflict = result.scalar_one_or_none()
        
        if not conflict:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conflict not found"
            )
        
        # Resolve using strategy
        resolved_data = await conflict_resolver.auto_resolve(
            conflict.client_version,
            conflict.server_version,
            strategy
        )
        
        await session.execute(
            update(SyncConflict)
            .where(SyncConflict.id == conflict_id)
            .values(
                resolved_version=resolved_data,
                resolved_by=f"auto_{strategy}",
                resolved_at=datetime.utcnow(),
                status="resolved"
            )
        )
        
        await session.commit()
        
        return {
            "conflict_id": str(conflict_id),
            "status": "resolved",
            "resolution": resolved_data,
            "strategy": strategy,
            "method": "auto"
        }


@router.delete("/{conflict_id}")
async def ignore_conflict(conflict_id: UUID):
    """Ignore a conflict (keep server version)"""
    
    from sqlalchemy import select, update
    from datetime import datetime
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(SyncConflict).where(SyncConflict.id == conflict_id)
        )
        conflict = result.scalar_one_or_none()
        
        if not conflict:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conflict not found"
            )
        
        # Mark as resolved (keep server version)
        await session.execute(
            update(SyncConflict)
            .where(SyncConflict.id == conflict_id)
            .values(
                resolved_version=conflict.server_version,
                resolved_by="ignore",
                resolved_at=datetime.utcnow(),
                status="ignored"
            )
        )
        
        await session.commit()
        
        return {"message": f"Conflict {conflict_id} ignored, server version kept"}


@router.get("/stats")
async def get_conflict_stats():
    """Get conflict statistics"""
    
    from sqlalchemy import select, func
    
    async with AsyncSessionLocal() as session:
        # Count by status
        result = await session.execute(
            select(
                SyncConflict.status,
                func.count(SyncConflict.id).label('count')
            )
            .group_by(SyncConflict.status)
        )
        status_counts = {row[0]: row[1] for row in result.all()}
        
        # Count by entity type
        result = await session.execute(
            select(
                SyncConflict.entity_type,
                func.count(SyncConflict.id).label('count')
            )
            .where(SyncConflict.status == "pending")
            .group_by(SyncConflict.entity_type)
        )
        entity_counts = {row[0].value: row[1] for row in result.all()}
        
        return {
            "total_conflicts": sum(status_counts.values()),
            "by_status": status_counts,
            "pending_by_entity": entity_counts,
            "resolution_strategies": {
                "available": ["last_write_wins", "server_wins", "client_wins", "merge", "manual"],
                "default": "last_write_wins"
            }
        }
