# services/model-registry/app/api/v1/deployments.py
"""Deployment management endpoints"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from uuid import UUID

from ...core.registry import ModelRegistry
from ...database import ModelDeployment, ModelVersion, ModelStatus
from ...schemas import DeploymentCreate, DeploymentResponse
from .dependencies import verify_api_key

router = APIRouter()
registry = ModelRegistry()


@router.post("/{model_id}/deploy", response_model=DeploymentResponse)
async def deploy_model(
    model_id: UUID,
    deployment: DeploymentCreate,
    api_key: str = Depends(verify_api_key)
):
    """Deploy a model to an environment"""
    
    # Check if model exists
    model = await registry.get_model(model_id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found"
        )
    
    # Check if model is ready for deployment
    if model.status not in [ModelStatus.STAGING, ModelStatus.PRODUCTION]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Model status {model.status} not ready for deployment"
        )
    
    try:
        # Record deployment
        deployment_record = await registry.record_deployment(
            model_id=model_id,
            environment=deployment.environment,
            deployed_by=deployment.deployed_by,
            metadata=deployment.metadata
        )
        
        # If deploying to production, promote model
        if deployment.environment == "production":
            await registry.promote_to_production(model_id)
        
        return deployment_record
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Deployment failed: {str(e)}"
        )


@router.get("/{model_id}/deployments", response_model=List[DeploymentResponse])
async def get_model_deployments(
    model_id: UUID,
    limit: int = 50,
    offset: int = 0
):
    """Get deployment history for a model"""
    
    from sqlalchemy import select, desc
    from ...database import AsyncSessionLocal
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ModelDeployment)
            .where(ModelDeployment.model_id == model_id)
            .order_by(desc(ModelDeployment.deployed_at))
            .limit(limit)
            .offset(offset)
        )
        deployments = result.scalars().all()
        
        return deployments


@router.get("/deployments/active")
async def get_active_deployments(
    environment: Optional[str] = None
):
    """Get currently active deployments"""
    
    from sqlalchemy import select
    from ...database import AsyncSessionLocal
    
    async with AsyncSessionLocal() as session:
        query = select(ModelDeployment).where(ModelDeployment.status == "success")
        
        if environment:
            query = query.where(ModelDeployment.environment == environment)
        
        result = await session.execute(query.order_by(ModelDeployment.deployed_at.desc()))
        deployments = result.scalars().all()
        
        # Group by environment to get latest
        active = {}
        for deployment in deployments:
            if deployment.environment not in active:
                active[deployment.environment] = deployment
        
        return {
            "deployments": [
                {
                    "environment": env,
                    "model_id": str(dep.model_id),
                    "deployed_at": dep.deployed_at.isoformat(),
                    "deployed_by": dep.deployed_by
                }
                for env, dep in active.items()
            ]
        }


@router.post("/deployments/{deployment_id}/rollback")
async def rollback_deployment(
    deployment_id: UUID,
    api_key: str = Depends(verify_api_key)
):
    """Rollback a deployment"""
    
    from sqlalchemy import select, update
    from ...database import AsyncSessionLocal
    
    async with AsyncSessionLocal() as session:
        # Get deployment to rollback
        result = await session.execute(
            select(ModelDeployment).where(ModelDeployment.id == deployment_id)
        )
        deployment = result.scalar_one_or_none()
        
        if not deployment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Deployment not found"
            )
        
        # Get previous deployment
        prev_result = await session.execute(
            select(ModelDeployment)
            .where(
                ModelDeployment.model_id != deployment.model_id,
                ModelDeployment.environment == deployment.environment,
                ModelDeployment.status == "success"
            )
            .order_by(ModelDeployment.deployed_at.desc())
            .limit(1)
        )
        previous = prev_result.scalar_one_or_none()
        
        if not previous:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No previous deployment found to rollback to"
            )
        
        # Mark current deployment as rolled back
        await session.execute(
            update(ModelDeployment)
            .where(ModelDeployment.id == deployment_id)
            .values(status="rolled_back")
        )
        
        # Record rollback
        rollback_deployment = ModelDeployment(
            model_id=previous.model_id,
            environment=deployment.environment,
            deployed_by="rollback_system",
            status="success",
            rollback_from=deployment_id,
            metadata={"rolled_back_from": str(deployment.model_id)}
        )
        session.add(rollback_deployment)
        
        await session.commit()
        
        return {
            "message": f"Rolled back to model {previous.model_id}",
            "previous_deployment_id": str(previous.id),
            "new_deployment_id": str(rollback_deployment.id)
        }
