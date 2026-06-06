# services/analytics-service/app/services/analytics_engine.py
"""Core analytics engine for data processing and aggregation"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
import pandas as pd
import numpy as np
from sqlalchemy import select, func, and_, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.cache import redis_client, cached
from agriculture_ai.types.models import Scan, Prediction, User, Farm
from app.services.predictive_analytics import PredictiveAnalytics

logger = logging.getLogger(__name__)


class AnalyticsEngine:
    """Main analytics engine for processing platform data"""
    
    def __init__(self):
        self.predictive = PredictiveAnalytics()
        self._cache_ttl = 3600  # 1 hour
        
    async def initialize(self):
        """Initialize analytics engine"""
        await self.predictive.initialize()
        logger.info("Analytics engine initialized")
    
    async def close(self):
        """Clean up resources"""
        await self.predictive.close()
        logger.info("Analytics engine closed")
    
    @cached(ttl=300)  # 5 minutes cache
    async def get_dashboard_summary(
        self,
        days: int = 30,
        crop_type: Optional[str] = None,
        region: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get main dashboard summary statistics"""
        async with get_session() as session:
            # Calculate date range
            start_date = datetime.utcnow() - timedelta(days=days)
            
            # Base queries
            scans_query = select(func.count(Scan.id)).where(
                Scan.created_at >= start_date
            )
            predictions_query = select(func.count(Prediction.id)).where(
                Prediction.created_at >= start_date
            )
            
            # Apply filters
            if crop_type:
                scans_query = scans_query.join(Farm).where(Farm.crop_type == crop_type)
                predictions_query = predictions_query.join(Scan).join(Farm).where(Farm.crop_type == crop_type)
            
            if region:
                scans_query = scans_query.where(Farm.location.ilike(f"%{region}%"))
                predictions_query = predictions_query.where(Farm.location.ilike(f"%{region}%"))
            
            # Execute queries
            total_scans = (await session.execute(scans_query)).scalar() or 0
            total_predictions = (await session.execute(predictions_query)).scalar() or 0
            
            # Average confidence
            avg_confidence_query = select(func.avg(Prediction.confidence_score)).where(
                Prediction.created_at >= start_date
            )
            avg_confidence = (await session.execute(avg_confidence_query)).scalar() or 0.0
            
            # Unique users
            unique_users_query = select(func.count(func.distinct(Scan.user_id))).where(
                Scan.created_at >= start_date
            )
            active_users = (await session.execute(unique_users_query)).scalar() or 0
            
            # Edge vs Cloud distribution
            inference_distribution = await self._get_inference_distribution(session, start_date)
            
            # Top diseases
            top_diseases = await self._get_top_diseases(session, start_date, limit=5)
            
            # Daily trends
            daily_trends = await self._get_daily_trends(session, start_date, days)
            
            return {
                "total_scans": total_scans,
                "total_predictions": total_predictions,
                "avg_confidence": round(float(avg_confidence), 3),
                "active_users": active_users,
                "inference_distribution": inference_distribution,
                "top_diseases": top_diseases,
                "daily_trends": daily_trends,
                "period_days": days,
                "start_date": start_date.isoformat(),
                "end_date": datetime.utcnow().isoformat()
            }
    
    async def get_timeseries(
        self,
        metric: str,
        days: int,
        interval: str,
        crop_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get time series data for specified metric"""
        async with get_session() as session:
            start_date = datetime.utcnow() - timedelta(days=days)
            
            # Build time series query based on interval
            if interval == "hour":
                date_trunc = func.date_trunc('hour', Scan.created_at)
                group_by = date_trunc
            elif interval == "day":
                date_trunc = func.date_trunc('day', Scan.created_at)
                group_by = date_trunc
            elif interval == "week":
                date_trunc = func.date_trunc('week', Scan.created_at)
                group_by = date_trunc
            else:  # month
                date_trunc = func.date_trunc('month', Scan.created_at)
                group_by = date_trunc
            
            if metric == "scans":
                query = select(
                    group_by.label("time_bucket"),
                    func.count(Scan.id).label("value")
                ).where(Scan.created_at >= start_date)
                
                if crop_type:
                    query = query.join(Farm).where(Farm.crop_type == crop_type)
                
                query = query.group_by(group_by).order_by(group_by)
                
            elif metric == "predictions":
                query = select(
                    group_by.label("time_bucket"),
                    func.count(Prediction.id).label("value")
                ).join(Scan, Prediction.scan_id == Scan.id).where(
                    Prediction.created_at >= start_date
                )
                
                if crop_type:
                    query = query.join(Farm).where(Farm.crop_type == crop_type)
                
                query = query.group_by(group_by).order_by(group_by)
                
            elif metric == "confidence":
                query = select(
                    group_by.label("time_bucket"),
                    func.avg(Prediction.confidence_score).label("value")
                ).join(Scan, Prediction.scan_id == Scan.id).where(
                    Prediction.created_at >= start_date
                )
                
                if crop_type:
                    query = query.join(Farm).where(Farm.crop_type == crop_type)
                
                query = query.group_by(group_by).order_by(group_by)
                
            else:
                raise ValueError(f"Unsupported metric: {metric}")
            
            results = await session.execute(query)
            rows = results.all()
            
            # Format results
            timeseries = []
            for row in rows:
                timeseries.append({
                    "timestamp": row.time_bucket.isoformat(),
                    "value": float(row.value)
                })
            
            return timeseries
    
    async def get_disease_distribution(
        self,
        days: int = 30,
        crop_type: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get distribution of diseases"""
        async with get_session() as session:
            start_date = datetime.utcnow() - timedelta(days=days)
            
            query = select(
                Prediction.disease_type,
                func.count(Prediction.id).label("count"),
                func.avg(Prediction.confidence_score).label("avg_confidence")
            ).where(Prediction.created_at >= start_date)
            
            if crop_type:
                query = query.join(Scan).join(Farm).where(Farm.crop_type == crop_type)
            
            query = query.group_by(Prediction.disease_type).order_by(
                func.count(Prediction.id).desc()
            ).limit(limit)
            
            results = await session.execute(query)
            
            distribution = []
            total = sum(row.count for row in results)
            
            # Execute again to get data with percentages
            results = await session.execute(query)
            for row in results:
                distribution.append({
                    "disease_type": row.disease_type,
                    "count": row.count,
                    "percentage": round((row.count / total) * 100, 2) if total > 0 else 0,
                    "avg_confidence": round(float(row.avg_confidence), 3),
                    "severity": self._calculate_severity(row.count, total)
                })
            
            return distribution
    
    async def get_performance_metrics(self, time_range: str) -> Dict[str, Any]:
        """Get system performance metrics"""
        async with get_session() as session:
            # Parse time range
            if time_range == "1h":
                start_time = datetime.utcnow() - timedelta(hours=1)
            elif time_range == "24h":
                start_time = datetime.utcnow() - timedelta(hours=24)
            elif time_range == "7d":
                start_time = datetime.utcnow() - timedelta(days=7)
            else:  # 30d
                start_time = datetime.utcnow() - timedelta(days=30)
            
            # Average processing time
            avg_processing = await session.execute(
                select(func.avg(Prediction.processing_time_ms)).where(
                    Prediction.created_at >= start_time,
                    Prediction.processing_time_ms.isnot(None)
                )
            )
            
            # Success rate (predictions with confidence > 0.5)
            total_predictions = await session.execute(
                select(func.count(Prediction.id)).where(Prediction.created_at >= start_time)
            )
            successful = await session.execute(
                select(func.count(Prediction.id)).where(
                    Prediction.created_at >= start_time,
                    Prediction.confidence_score > 0.5
                )
            )
            
            total = total_predictions.scalar() or 1
            success_rate = (successful.scalar() or 0) / total
            
            # Confidence score distribution
            confidence_buckets = await self._get_confidence_distribution(session, start_time)
            
            # Inference speed by source
            inference_speed = await self._get_inference_speed_by_source(session, start_time)
            
            return {
                "average_processing_time_ms": round(float(avg_processing.scalar() or 0), 2),
                "success_rate": round(success_rate, 3),
                "confidence_distribution": confidence_buckets,
                "inference_speed_by_source": inference_speed,
                "time_range": time_range,
                "total_predictions": total
            }
    
    async def get_geospatial_analytics(
        self,
        days: int = 30,
        crop_type: Optional[str] = None,
        disease_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get geospatial distribution of diseases"""
        async with get_session() as session:
            start_date = datetime.utcnow() - timedelta(days=days)
            
            query = select(
                Farm.latitude,
                Farm.longitude,
                Farm.location,
                Prediction.disease_type,
                Prediction.confidence_score,
                Scan.created_at
            ).join(Scan, Farm.id == Scan.farm_id).join(
                Prediction, Scan.id == Prediction.scan_id
            ).where(
                Scan.created_at >= start_date,
                Farm.latitude.isnot(None),
                Farm.longitude.isnot(None)
            )
            
            if crop_type:
                query = query.where(Farm.crop_type == crop_type)
            
            if disease_type:
                query = query.where(Prediction.disease_type == disease_type)
            
            results = await session.execute(query)
            rows = results.all()
            
            # Group by location
            locations = defaultdict(lambda: {
                "count": 0,
                "diseases": defaultdict(int),
                "avg_confidence": 0
            })
            
            for row in rows:
                key = f"{row.latitude},{row.longitude}"
                locations[key]["count"] += 1
                locations[key]["diseases"][row.disease_type] += 1
                locations[key]["avg_confidence"] += row.confidence_score
            
            # Calculate averages
            for loc in locations.values():
                loc["avg_confidence"] /= loc["count"]
            
            # Format for GeoJSON
            features = []
            for key, data in locations.items():
                lat, lon = map(float, key.split(','))
                features.append({
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [lon, lat]
                    },
                    "properties": {
                        "count": data["count"],
                        "avg_confidence": round(data["avg_confidence"], 3),
                        "top_disease": max(data["diseases"], key=data["diseases"].get),
                        "diseases": dict(data["diseases"])
                    }
                })
            
            return {
                "type": "FeatureCollection",
                "features": features,
                "metadata": {
                    "total_locations": len(features),
                    "total_detections": sum(f["properties"]["count"] for f in features),
                    "date_range": {
                        "start": start_date.isoformat(),
                        "end": datetime.utcnow().isoformat()
                    }
                }
            }
    
    async def get_predictive_analytics(
        self,
        crop_type: Optional[str] = None,
        forecast_days: int = 30
    ) -> Dict[str, Any]:
        """Get predictive analytics and forecasts"""
        # Get historical data
        historical_data = await self._get_historical_data(crop_type)
        
        # Generate forecasts
        disease_forecast = await self.predictive.forecast_disease_outbreaks(
            historical_data, forecast_days
        )
        
        # Risk assessment
        risk_assessment = await self.predictive.assess_risk(
            historical_data, crop_type
        )
        
        # Recommendations
        recommendations = await self.predictive.generate_recommendations(
            risk_assessment
        )
        
        return {
            "forecast": disease_forecast,
            "risk_assessment": risk_assessment,
            "recommendations": recommendations,
            "confidence_level": 0.85,  # Model confidence
            "forecast_period_days": forecast_days
        }
    
    async def _get_inference_distribution(
        self,
        session: AsyncSession,
        start_date: datetime
    ) -> Dict[str, int]:
        """Get distribution of inference sources"""
        query = select(
            Prediction.inference_source,
            func.count(Prediction.id)
        ).where(Prediction.created_at >= start_date).group_by(Prediction.inference_source)
        
        results = await session.execute(query)
        return {row[0]: row[1] for row in results.all()}
    
    async def _get_top_diseases(
        self,
        session: AsyncSession,
        start_date: datetime,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get top diseases by occurrence"""
        query = select(
            Prediction.disease_type,
            func.count(Prediction.id).label("count")
        ).where(Prediction.created_at >= start_date).group_by(
            Prediction.disease_type
        ).order_by(func.count(Prediction.id).desc()).limit(limit)
        
        results = await session.execute(query)
        
        top_diseases = []
        for row in results:
            top_diseases.append({
                "disease": row.disease_type,
                "count": row.count,
                "percentage": 0  # Will be calculated in dashboard summary
            })
        
        return top_diseases
    
    async def _get_daily_trends(
        self,
        session: AsyncSession,
        start_date: datetime,
        days: int
    ) -> List[Dict[str, Any]]:
        """Get daily trends for key metrics"""
        query = select(
            func.date(Scan.created_at).label("date"),
            func.count(Scan.id).label("scans"),
            func.avg(Prediction.confidence_score).label("avg_confidence")
        ).join(Prediction, Scan.id == Prediction.scan_id).where(
            Scan.created_at >= start_date
        ).group_by(func.date(Scan.created_at)).order_by(func.date(Scan.created_at))
        
        results = await session.execute(query)
        
        trends = []
        for row in results:
            trends.append({
                "date": row.date.isoformat(),
                "scans": row.scans,
                "avg_confidence": round(float(row.avg_confidence), 3) if row.avg_confidence else 0
            })
        
        return trends
    
    async def _get_confidence_distribution(
        self,
        session: AsyncSession,
        start_date: datetime
    ) -> Dict[str, float]:
        """Get confidence score distribution buckets"""
        buckets = {
            "high": (0.8, 1.0),
            "medium": (0.5, 0.8),
            "low": (0.0, 0.5)
        }
        
        distribution = {}
        for bucket_name, (low, high) in buckets.items():
            query = select(func.count(Prediction.id)).where(
                Prediction.created_at >= start_date,
                Prediction.confidence_score >= low,
                Prediction.confidence_score < high
            )
            count = (await session.execute(query)).scalar() or 0
            distribution[bucket_name] = count
        
        return distribution
    
    async def _get_inference_speed_by_source(
        self,
        session: AsyncSession,
        start_date: datetime
    ) -> Dict[str, float]:
        """Get average inference speed by source"""
        query = select(
            Prediction.inference_source,
            func.avg(Prediction.processing_time_ms)
        ).where(
            Prediction.created_at >= start_date,
            Prediction.processing_time_ms.isnot(None)
        ).group_by(Prediction.inference_source)
        
        results = await session.execute(query)
        return {row[0]: round(float(row[1]), 2) for row in results.all()}
    
    async def _get_historical_data(
        self,
        crop_type: Optional[str] = None
    ) -> pd.DataFrame:
        """Get historical data for predictive analytics"""
        async with get_session() as session:
            query = select(
                Scan.created_at,
                Farm.crop_type,
                Farm.location,
                Prediction.disease_type,
                Prediction.confidence_score,
                Prediction.processing_time_ms
            ).join(Farm, Scan.farm_id == Farm.id).join(
                Prediction, Scan.id == Prediction.scan_id
            )
            
            if crop_type:
                query = query.where(Farm.crop_type == crop_type)
            
            results = await session.execute(query)
            rows = results.all()
            
            # Convert to pandas DataFrame for analysis
            data = []
            for row in rows:
                data.append({
                    "timestamp": row.created_at,
                    "crop_type": row.crop_type,
                    "location": row.location,
                    "disease_type": row.disease_type,
                    "confidence": row.confidence_score,
                    "processing_time": row.processing_time_ms
                })
            
            return pd.DataFrame(data)
    
    def _calculate_severity(self, count: int, total: int) -> str:
        """Calculate severity level based on occurrence"""
        ratio = count / total if total > 0 else 0
        if ratio > 0.3:
            return "high"
        elif ratio > 0.1:
            return "medium"
        else:
            return "low"


analytics_engine = AnalyticsEngine()
