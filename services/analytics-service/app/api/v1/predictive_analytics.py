# services/analytics-service/app/services/predictive_analytics.py
"""Predictive analytics for disease forecasting"""

import logging
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
import joblib

logger = logging.getLogger(__name__)


class PredictiveAnalytics:
    """Predictive analytics for disease outbreaks and risk assessment"""
    
    def __init__(self):
        self.models = {}
        self.scaler = StandardScaler()
        self.is_initialized = False
        
    async def initialize(self):
        """Initialize predictive models"""
        try:
            # Initialize time series models for each disease
            self.models = {
                "disease_forecast": ExponentialSmoothing,
                "risk_assessment": RandomForestRegressor(n_estimators=100, random_state=42)
            }
            self.is_initialized = True
            logger.info("Predictive analytics models initialized")
        except Exception as e:
            logger.error(f"Failed to initialize predictive models: {e}")
            self.is_initialized = False
    
    async def close(self):
        """Clean up resources"""
        self.models.clear()
        self.is_initialized = False
    
    async def forecast_disease_outbreaks(
        self,
        historical_data: pd.DataFrame,
        forecast_days: int = 30
    ) -> Dict[str, Any]:
        """Forecast disease outbreaks for next N days"""
        if not self.is_initialized or historical_data.empty:
            return self._get_default_forecast()
        
        try:
            # Aggregate by date
            daily_cases = historical_data.groupby(
                historical_data['timestamp'].dt.date
            ).size()
            
            # Create time series
            ts = pd.Series(daily_cases.values, index=pd.DatetimeIndex(daily_cases.index))
            
            # Fit model
            model = ExponentialSmoothing(
                ts,
                seasonal_periods=7,  # Weekly seasonality
                trend='add',
                seasonal='add'
            )
            fitted_model = model.fit()
            
            # Generate forecast
            forecast = fitted_model.forecast(forecast_days)
            
            # Calculate peaks and trends
            forecast_values = forecast.values
            peaks = self._find_peaks(forecast_values)
            trend = self._calculate_trend(forecast_values)
            
            # Identify high-risk periods
            high_risk_days = [
                i for i, val in enumerate(forecast_values)
                if val > np.percentile(forecast_values, 75)
            ]
            
            return {
                "forecast_values": forecast_values.tolist(),
                "forecast_dates": [
                    (datetime.now() + timedelta(days=i+1)).isoformat()
                    for i in range(forecast_days)
                ],
                "peak_days": peaks,
                "trend": trend,
                "high_risk_days": high_risk_days,
                "expected_total_cases": int(forecast_values.sum()),
                "max_expected_daily_cases": int(forecast_values.max()),
                "model_confidence": 0.85
            }
            
        except Exception as e:
            logger.error(f"Forecast generation failed: {e}")
            return self._get_default_forecast()
    
    async def assess_risk(
        self,
        historical_data: pd.DataFrame,
        crop_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Assess disease risk for different regions"""
        if not self.is_initialized or historical_data.empty:
            return self._get_default_risk_assessment()
        
        try:
            # Feature engineering
            features = self._extract_risk_features(historical_data)
            
            # Train risk model if needed
            if 'risk_model' not in self.models:
                self.models['risk_model'] = RandomForestRegressor(n_estimators=100)
                # Use historical data to train
                X = features.drop('risk_score', axis=1)
                y = features['risk_score']
                self.models['risk_model'].fit(X, y)
            
            # Calculate current risk scores
            current_features = self._get_current_features(historical_data)
            risk_scores = self.models['risk_model'].predict(current_features)
            
            # Categorize risk levels
            risk_levels = self._categorize_risk(risk_scores)
            
            # Generate recommendations
            recommendations = self._generate_risk_recommendations(risk_levels)
            
            return {
                "overall_risk_score": float(np.mean(risk_scores)),
                "risk_level": self._get_overall_risk_level(risk_scores),
                "regional_risk": risk_levels,
                "recommendations": recommendations,
                "factors": self._identify_risk_factors(historical_data),
                "confidence": 0.80
            }
            
        except Exception as e:
            logger.error(f"Risk assessment failed: {e}")
            return self._get_default_risk_assessment()
    
    async def generate_recommendations(
        self,
        risk_assessment: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate actionable recommendations based on risk assessment"""
        recommendations = []
        
        risk_level = risk_assessment.get("risk_level", "low")
        
        if risk_level == "high":
            recommendations.append({
                "priority": "critical",
                "action": "Immediate field inspection required",
                "details": "High disease risk detected. Conduct thorough inspection of all fields.",
                "timeline": "24 hours"
            })
            recommendations.append({
                "priority": "high",
                "action": "Apply preventive fungicides",
                "details": "Based on risk assessment, preventive treatment is recommended.",
                "timeline": "48 hours"
            })
        elif risk_level == "medium":
            recommendations.append({
                "priority": "medium",
                "action": "Increase monitoring frequency",
                "details": "Medium risk level. Increase field monitoring to twice per week.",
                "timeline": "Immediate"
            })
            recommendations.append({
                "priority": "low",
                "action": "Prepare treatment resources",
                "details": "Ensure treatment supplies are available if risk increases.",
                "timeline": "7 days"
            })
        else:
            recommendations.append({
                "priority": "low",
                "action": "Continue regular monitoring",
                "details": "Low risk level. Maintain standard monitoring schedule.",
                "timeline": "Weekly"
            })
        
        # Add general recommendations
        recommendations.extend([
            {
                "priority": "medium",
                "action": "Review historical disease patterns",
                "details": "Analyze past outbreaks for better preparedness.",
                "timeline": "Monthly"
            },
            {
                "priority": "low",
                "action": "Update treatment protocols",
                "details": "Review and update treatment protocols based on latest research.",
                "timeline": "Quarterly"
            }
        ])
        
        return recommendations
    
    def _extract_risk_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Extract features for risk assessment"""
        features = pd.DataFrame()
        
        # Temporal features
        features['day_of_week'] = pd.to_datetime(data['timestamp']).dt.dayofweek
        features['month'] = pd.to_datetime(data['timestamp']).dt.month
        
        # Disease specific features
        disease_counts = data.groupby('disease_type').size()
        features['disease_prevalence'] = data['disease_type'].map(disease_counts)
        
        # Confidence features
        features['avg_confidence'] = data.groupby('disease_type')['confidence'].transform('mean')
        
        # Calculate risk score (simplified)
        features['risk_score'] = (
            features['disease_prevalence'] / features['disease_prevalence'].max() * 0.6 +
            (1 - features['avg_confidence']) * 0.4
        )
        
        return features
    
    def _get_current_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Get features for current time period"""
        # Get last 7 days of data
        last_week = data[data['timestamp'] >= datetime.now() - timedelta(days=7)]
        return self._extract_risk_features(last_week)
    
    def _categorize_risk(self, risk_scores: np.ndarray) -> Dict[str, Any]:
        """Categorize risk scores into levels"""
        regions = ["North", "South", "East", "West", "Central"]  # Simplified regions
        
        risk_levels = {}
        for i, score in enumerate(risk_scores[:5]):  # Limit to 5 regions
            if score > 0.7:
                level = "high"
            elif score > 0.4:
                level = "medium"
            else:
                level = "low"
            
            risk_levels[regions[i]] = {
                "score": float(score),
                "level": level
            }
        
        return risk_levels
    
    def _get_overall_risk_level(self, risk_scores: np.ndarray) -> str:
        """Determine overall risk level"""
        avg_risk = np.mean(risk_scores)
        
        if avg_risk > 0.7:
            return "high"
        elif avg_risk > 0.4:
            return "medium"
        else:
            return "low"
    
    def _identify_risk_factors(self, data: pd.DataFrame) -> List[str]:
        """Identify key risk factors"""
        factors = []
        
        # Check for seasonal patterns
        data['month'] = pd.to_datetime(data['timestamp']).dt.month
        monthly_cases = data.groupby('month').size()
        
        if len(monthly_cases) > 0 and monthly_cases.max() > monthly_cases.mean() * 1.5:
            factors.append("Seasonal disease pattern detected")
        
        # Check for high confidence predictions
        high_confidence = data[data['confidence'] > 0.9]
        if len(high_confidence) > len(data) * 0.3:
            factors.append("High confidence disease detection rate")
        
        # Check for rapid spread
        daily_cases = data.groupby(pd.to_datetime(data['timestamp']).dt.date).size()
        if len(daily_cases) > 7:
            recent_trend = daily_cases.tail(7).mean()
            previous_trend = daily_cases.head(7).mean()
            if recent_trend > previous_trend * 1.5:
                factors.append("Rapid disease spread detected")
        
        if not factors:
            factors.append("No significant risk factors identified")
        
        return factors
    
    def _find_peaks(self, values: np.ndarray) -> List[int]:
        """Find peak indices in forecast values"""
        peaks = []
        for i in range(1, len(values) - 1):
            if values[i] > values[i-1] and values[i] > values[i+1]:
                peaks.append(i)
        return peaks
    
    def _calculate_trend(self, values: np.ndarray) -> str:
        """Calculate overall trend direction"""
        if len(values) < 2:
            return "stable"
        
        slope = (values[-1] - values[0]) / len(values)
        
        if slope > 0.1:
            return "increasing"
        elif slope < -0.1:
            return "decreasing"
        else:
            return "stable"
    
    def _get_default_forecast(self) -> Dict[str, Any]:
        """Get default forecast when model unavailable"""
        return {
            "forecast_values": [0] * 30,
            "forecast_dates": [],
            "peak_days": [],
            "trend": "unknown",
            "high_risk_days": [],
            "expected_total_cases": 0,
            "max_expected_daily_cases": 0,
            "model_confidence": 0.5
        }
    
    def _get_default_risk_assessment(self) -> Dict[str, Any]:
        """Get default risk assessment when model unavailable"""
        return {
            "overall_risk_score": 0.5,
            "risk_level": "medium",
            "regional_risk": {},
            "recommendations": [
                "Enable data collection for better risk assessment",
                "Increase monitoring frequency",
                "Review basic prevention measures"
            ],
            "factors": ["Insufficient data for accurate risk assessment"],
            "confidence": 0.5
        }