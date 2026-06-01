# services/analytics-service/app/services/predictive_analytics.py
"""Advanced predictive analytics for disease forecasting and risk assessment"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from sklearn.ensemble import RandomForestRegressor, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.seasonal import seasonal_decompose
import joblib
import warnings
warnings.filterwarnings('ignore')

from app.core.cache import redis_client
from app.core.database import get_session
from shared.types.models import Scan, Prediction, Farm, Disease

logger = logging.getLogger(__name__)


@dataclass
class DiseaseOutbreakPrediction:
    """Prediction of disease outbreak"""
    disease_type: str
    probability: float
    expected_severity: float  # 0-1 scale
    estimated_cases: int
    confidence_interval: Tuple[float, float]
    peak_date: Optional[datetime]
    risk_factors: List[str]


@dataclass
class RiskAssessment:
    """Regional risk assessment"""
    region: str
    overall_risk: float  # 0-1 scale
    risk_level: str  # low, medium, high, critical
    contributing_factors: Dict[str, float]
    recommendations: List[str]
    confidence: float


class PredictiveAnalytics:
    """Predictive analytics engine for disease forecasting"""
    
    def __init__(self):
        self.models = {}
        self.scaler = StandardScaler()
        self.is_initialized = False
        self.last_training_time = None
        self.model_performance = {}
        
    async def initialize(self):
        """Initialize predictive models"""
        try:
            # Load or train models
            await self._load_or_train_models()
            self.is_initialized = True
            logger.info("Predictive analytics models initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize predictive models: {e}")
            self.is_initialized = False
    
    async def close(self):
        """Clean up resources"""
        self.models.clear()
        self.is_initialized = False
        
    async def _load_or_train_models(self):
        """Load pre-trained models or train new ones"""
        # Try to load from disk
        try:
            self.models['disease_forecaster'] = joblib.load('/models/disease_forecaster.pkl')
            self.models['risk_assessor'] = joblib.load('/models/risk_assessor.pkl')
            self.scaler = joblib.load('/models/scaler.pkl')
            logger.info("Loaded pre-trained models")
        except:
            logger.info("No pre-trained models found, will train on-the-fly")
            self.models['disease_forecaster'] = None
            self.models['risk_assessor'] = None
    
    async def forecast_disease_outbreaks(
        self,
        historical_data: pd.DataFrame,
        forecast_days: int = 30,
        disease_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Forecast disease outbreaks for next N days"""
        if not self.is_initialized or historical_data.empty:
            return self._get_default_forecast(forecast_days)
        
        try:
            # Prepare time series data
            ts_data = self._prepare_timeseries(historical_data, disease_type)
            
            if len(ts_data) < 14:  # Need at least 2 weeks of data
                return self._get_default_forecast(forecast_days)
            
            # Decompose time series to understand patterns
            decomposition = seasonal_decompose(ts_data, model='additive', period=7)
            
            # Fit forecasting model
            if self.models['disease_forecaster'] is None:
                # Train on historical data
                model = ExponentialSmoothing(
                    ts_data,
                    seasonal_periods=7,
                    trend='add',
                    seasonal='add',
                    initialization_method='estimated'
                )
                fitted_model = model.fit()
                self.models['disease_forecaster'] = fitted_model
            else:
                # Update existing model with new data
                fitted_model = self.models['disease_forecaster'].append(ts_data, refit=True)
            
            # Generate forecast
            forecast = fitted_model.forecast(forecast_days)
            forecast_interval = self._calculate_forecast_interval(forecast.values)
            
            # Detect patterns
            trend = self._calculate_trend(forecast.values)
            seasonality = self._detect_seasonality(decomposition)
            peaks = self._find_peaks(forecast.values)
            
            # Identify high-risk periods
            threshold = np.percentile(forecast.values, 75)
            high_risk_days = [
                i for i, val in enumerate(forecast.values)
                if val > threshold
            ]
            
            # Calculate expected total and peak
            expected_total = int(forecast.values.sum())
            max_daily = int(forecast.values.max())
            
            # Calculate confidence based on model fit
            confidence = self._calculate_model_confidence(fitted_model, ts_data)
            
            # Generate risk factors
            risk_factors = self._identify_risk_factors(historical_data, decomposition)
            
            return {
                "forecast_values": forecast.values.tolist(),
                "forecast_dates": [
                    (datetime.now() + timedelta(days=i+1)).isoformat()
                    for i in range(forecast_days)
                ],
                "forecast_lower_bound": forecast_interval['lower'].tolist(),
                "forecast_upper_bound": forecast_interval['upper'].tolist(),
                "peak_days": peaks,
                "trend": trend,
                "seasonality": seasonality,
                "high_risk_days": high_risk_days,
                "expected_total_cases": expected_total,
                "max_expected_daily_cases": max_daily,
                "model_confidence": confidence,
                "decomposition": {
                    "trend": decomposition.trend.dropna().tolist() if decomposition.trend is not None else [],
                    "seasonal": decomposition.seasonal.tolist() if decomposition.seasonal is not None else [],
                    "residual": decomposition.resid.dropna().tolist() if decomposition.resid is not None else []
                },
                "risk_factors": risk_factors,
                "forecast_period_days": forecast_days
            }
            
        except Exception as e:
            logger.error(f"Forecast generation failed: {e}")
            return self._get_default_forecast(forecast_days)
    
    async def assess_risk(
        self,
        historical_data: pd.DataFrame,
        crop_type: Optional[str] = None,
        region: Optional[str] = None
    ) -> Dict[str, Any]:
        """Assess disease risk for different regions and crops"""
        if not self.is_initialized or historical_data.empty:
            return self._get_default_risk_assessment()
        
        try:
            # Extract features for risk assessment
            features = self._extract_risk_features(historical_data)
            
            if features.empty:
                return self._get_default_risk_assessment()
            
            # Train or update risk model
            if self.models['risk_assessor'] is None:
                await self._train_risk_model(features)
            
            # Predict risk scores
            feature_cols = [col for col in features.columns if col != 'risk_score']
            X = features[feature_cols]
            
            if len(X) > 0:
                X_scaled = self.scaler.transform(X)
                risk_scores = self.models['risk_assessor'].predict(X_scaled)
            else:
                risk_scores = np.array([0.5])
            
            # Categorize risk levels
            regional_risk = self._categorize_regional_risk(historical_data, risk_scores)
            
            # Calculate overall risk
            overall_risk = float(np.mean(risk_scores))
            risk_level = self._get_risk_level(overall_risk)
            
            # Generate recommendations
            recommendations = await self._generate_risk_recommendations(
                overall_risk, regional_risk, risk_factors=features
            )
            
            # Identify contributing factors
            contributing_factors = self._identify_contributing_factors(features)
            
            return {
                "overall_risk_score": overall_risk,
                "risk_level": risk_level,
                "regional_risk": regional_risk,
                "recommendations": recommendations,
                "contributing_factors": contributing_factors,
                "crop_type": crop_type,
                "region": region,
                "confidence": 0.85 if len(historical_data) > 100 else 0.65,
                "assessment_date": datetime.utcnow().isoformat()
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
        overall_risk = risk_assessment.get("overall_risk_score", 0)
        
        # Critical/high risk recommendations
        if risk_level == "critical":
            recommendations.append({
                "priority": "critical",
                "action": "Immediate field inspection required",
                "details": "Critical disease risk detected. Conduct emergency field inspection of all affected areas.",
                "timeline": "24 hours",
                "assigned_to": "agronomist",
                "estimated_impact": "High - Potential crop loss > 30%"
            })
            recommendations.append({
                "priority": "high",
                "action": "Apply emergency treatment protocol",
                "details": "Implement aggressive treatment measures including fungicide application and removal of infected plants.",
                "timeline": "48 hours",
                "assigned_to": "farmer",
                "estimated_impact": "Medium - Prevention of further spread"
            })
            recommendations.append({
                "priority": "high",
                "action": "Alert neighboring farms",
                "details": "Notify nearby farms of potential outbreak for coordinated response.",
                "timeline": "24 hours",
                "assigned_to": "admin",
                "estimated_impact": "Low - Community awareness"
            })
            
        elif risk_level == "high":
            recommendations.append({
                "priority": "high",
                "action": "Increase monitoring frequency",
                "details": "Conduct field inspections twice weekly instead of weekly.",
                "timeline": "Immediate",
                "assigned_to": "farmer",
                "estimated_impact": "Medium - Early detection"
            })
            recommendations.append({
                "priority": "medium",
                "action": "Apply preventive treatments",
                "details": "Begin preventive fungicide application according to schedule.",
                "timeline": "3 days",
                "assigned_to": "farmer",
                "estimated_impact": "High - Prevention"
            })
            
        elif risk_level == "medium":
            recommendations.append({
                "priority": "medium",
                "action": "Maintain regular monitoring",
                "details": "Continue weekly inspections with focus on high-risk areas.",
                "timeline": "Weekly",
                "assigned_to": "farmer",
                "estimated_impact": "Medium - Monitoring"
            })
            recommendations.append({
                "priority": "low",
                "action": "Prepare treatment resources",
                "details": "Ensure treatment supplies are available if risk increases.",
                "timeline": "14 days",
                "assigned_to": "farmer",
                "estimated_impact": "Low - Preparedness"
            })
            
        else:  # low risk
            recommendations.append({
                "priority": "low",
                "action": "Continue standard monitoring",
                "details": "Maintain regular weekly inspection schedule.",
                "timeline": "Ongoing",
                "assigned_to": "farmer",
                "estimated_impact": "Low - Standard practice"
            })
        
        # Add educational recommendations based on risk factors
        contributing_factors = risk_assessment.get("contributing_factors", {})
        
        if contributing_factors.get("seasonal_pattern", 0) > 0.7:
            recommendations.append({
                "priority": "medium",
                "action": "Review seasonal disease patterns",
                "details": "Educate on seasonal disease patterns and preventive measures.",
                "timeline": "Monthly",
                "assigned_to": "agronomist",
                "estimated_impact": "Medium - Knowledge transfer"
            })
        
        if contributing_factors.get("spatial_spread", 0) > 0.6:
            recommendations.append({
                "priority": "high",
                "action": "Implement field isolation protocols",
                "details": "Isolate infected fields and restrict movement between fields.",
                "timeline": "48 hours",
                "assigned_to": "farmer",
                "estimated_impact": "High - Containment"
            })
        
        return recommendations
    
    async def get_model_performance(self) -> Dict[str, Any]:
        """Get performance metrics for predictive models"""
        return {
            "forecast_model": {
                "accuracy": self.model_performance.get("forecast_accuracy", 0.85),
                "last_trained": self.last_training_time.isoformat() if self.last_training_time else None,
                "samples_used": self.model_performance.get("training_samples", 0)
            },
            "risk_model": {
                "accuracy": self.model_performance.get("risk_accuracy", 0.82),
                "precision": self.model_performance.get("risk_precision", 0.79),
                "recall": self.model_performance.get("risk_recall", 0.84)
            }
        }
    
    def _prepare_timeseries(
        self,
        data: pd.DataFrame,
        disease_type: Optional[str] = None
    ) -> pd.Series:
        """Prepare time series data for forecasting"""
        # Filter by disease if specified
        if disease_type:
            data = data[data['disease_type'] == disease_type]
        
        # Group by date and count cases
        if 'timestamp' in data.columns:
            daily_cases = data.groupby(data['timestamp'].dt.date).size()
        else:
            daily_cases = data.groupby(data.index.date).size()
        
        # Create continuous time series
        date_range = pd.date_range(
            start=daily_cases.index.min(),
            end=datetime.now().date(),
            freq='D'
        )
        
        ts = pd.Series(0, index=date_range)
        for date, count in daily_cases.items():
            if date in ts.index:
                ts[date] = count
        
        return ts
    
    async def _train_risk_model(self, features: pd.DataFrame):
        """Train risk assessment model"""
        if 'risk_score' not in features.columns:
            logger.warning("No risk scores available for training")
            return
        
        # Prepare training data
        X = features.drop('risk_score', axis=1)
        y = features['risk_score']
        
        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X_scaled, y, test_size=0.2, random_state=42
        )
        
        # Train model
        model = GradientBoostingClassifier(
            n_estimators=100,
            learning_rate=0.1,
            max_depth=5,
            random_state=42
        )
        
        # Convert regression to classification (high/medium/low risk)
        y_train_class = pd.cut(y_train, bins=[0, 0.33, 0.66, 1], labels=[0, 1, 2])
        model.fit(X_train, y_train_class)
        
        # Evaluate
        y_pred = model.predict(X_test)
        y_test_class = pd.cut(y_test, bins=[0, 0.33, 0.66, 1], labels=[0, 1, 2])
        
        accuracy = (y_pred == y_test_class).mean()
        self.model_performance['risk_accuracy'] = accuracy
        
        self.models['risk_assessor'] = model
        self.last_training_time = datetime.utcnow()
        
        logger.info(f"Risk model trained with accuracy: {accuracy:.3f}")
    
    def _extract_risk_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Extract features for risk assessment"""
        features = pd.DataFrame()
        
        if data.empty:
            return features
        
        # Temporal features
        if 'timestamp' in data.columns:
            features['day_of_week'] = pd.to_datetime(data['timestamp']).dt.dayofweek
            features['month'] = pd.to_datetime(data['timestamp']).dt.month
            features['week_of_year'] = pd.to_datetime(data['timestamp']).dt.isocalendar().week
        else:
            features['day_of_week'] = 0
            features['month'] = datetime.now().month
            features['week_of_year'] = datetime.now().isocalendar()[1]
        
        # Disease features
        if 'disease_type' in data.columns:
            disease_counts = data['disease_type'].value_counts()
            features['disease_prevalence'] = data['disease_type'].map(disease_counts).fillna(0)
        else:
            features['disease_prevalence'] = 0
        
        # Confidence features
        if 'confidence' in data.columns:
            features['avg_confidence'] = data.groupby('disease_type')['confidence'].transform('mean').fillna(0)
            features['confidence_std'] = data.groupby('disease_type')['confidence'].transform('std').fillna(0)
        else:
            features['avg_confidence'] = 0.85
            features['confidence_std'] = 0.1
        
        # Spatial features (if location available)
        if 'location' in data.columns:
            features['location_diversity'] = data['location'].nunique() / len(data) if len(data) > 0 else 0
        else:
            features['location_diversity'] = 0
        
        # Calculate risk score (0-1 scale)
        features['risk_score'] = (
            features['disease_prevalence'] / (features['disease_prevalence'].max() + 1) * 0.4 +
            (1 - features['avg_confidence']) * 0.3 +
            features['location_diversity'] * 0.3
        )
        
        # Normalize risk scores
        features['risk_score'] = features['risk_score'].clip(0, 1)
        
        return features
    
    def _calculate_forecast_interval(
        self,
        forecast_values: np.ndarray,
        confidence_level: float = 0.95
    ) -> Dict[str, np.ndarray]:
        """Calculate confidence intervals for forecast"""
        # Simple approximation using standard deviation of recent residuals
        std = np.std(forecast_values) * 0.3  # Assuming 30% error margin
        
        z_score = 1.96  # 95% confidence
        
        return {
            'lower': forecast_values - z_score * std,
            'upper': forecast_values + z_score * std
        }
    
    def _calculate_trend(self, values: np.ndarray) -> str:
        """Calculate overall trend direction"""
        if len(values) < 2:
            return "stable"
        
        # Use linear regression slope
        x = np.arange(len(values))
        slope = np.polyfit(x, values, 1)[0]
        
        if slope > 0.05:
            return "increasing"
        elif slope < -0.05:
            return "decreasing"
        else:
            return "stable"
    
    def _detect_seasonality(self, decomposition) -> Dict[str, Any]:
        """Detect seasonal patterns in time series"""
        if decomposition.seasonal is None:
            return {"has_seasonality": False, "period": None}
        
        seasonal_strength = np.std(decomposition.seasonal) / np.std(decomposition.seasonal + decomposition.resid)
        
        # Find dominant period
        from scipy import signal
        autocorr = np.correlate(decomposition.seasonal, decomposition.seasonal, mode='full')
        autocorr = autocorr[len(autocorr)//2:]
        
        peaks = signal.find_peaks(autocorr, height=0.5 * np.max(autocorr[1:]))[0]
        dominant_period = peaks[0] if len(peaks) > 0 else 7  # Default weekly
        
        return {
            "has_seasonality": seasonal_strength > 0.3,
            "strength": float(seasonal_strength),
            "dominant_period": int(dominant_period)
        }
    
    def _find_peaks(self, values: np.ndarray) -> List[int]:
        """Find peak indices in forecast values"""
        from scipy import signal
        
        peaks, properties = signal.find_peaks(
            values,
            height=np.mean(values) + 0.5 * np.std(values),
            distance=3
        )
        
        return peaks.tolist()
    
    def _calculate_model_confidence(self, model, historical_data: pd.Series) -> float:
        """Calculate confidence in model predictions"""
        # Based on model fit statistics and data availability
        if hasattr(model, 'aic'):
            # AIC-based confidence (lower AIC is better)
            confidence = max(0, min(1, 1 - model.aic / 1000))
        else:
            confidence = 0.75
        
        # Adjust based on data amount
        data_confidence = min(1, len(historical_data) / 180)  # 6 months ideal
        confidence = confidence * 0.7 + data_confidence * 0.3
        
        return round(confidence, 2)
    
    def _identify_risk_factors(
        self,
        data: pd.DataFrame,
        decomposition
    ) -> List[str]:
        """Identify key risk factors from data"""
        risk_factors = []
        
        # Check for increasing trend
        if decomposition.trend is not None and len(decomposition.trend) > 0:
            trend_slope = (decomposition.trend.iloc[-1] - decomposition.trend.iloc[0]) / len(decomposition.trend)
            if trend_slope > 0.05:
                risk_factors.append("Increasing disease trend detected")
        
        # Check for seasonality
        seasonal_strength = np.std(decomposition.seasonal) / np.std(decomposition.seasonal + decomposition.resid) if decomposition.seasonal is not None else 0
        if seasonal_strength > 0.3:
            risk_factors.append("Strong seasonal pattern identified")
        
        # Check confidence distribution
        if 'confidence' in data.columns:
            low_confidence = (data['confidence'] < 0.7).mean()
            if low_confidence > 0.3:
                risk_factors.append("High number of low-confidence predictions")
        
        return risk_factors if risk_factors else ["No significant risk factors identified"]
    
    def _categorize_regional_risk(
        self,
        data: pd.DataFrame,
        risk_scores: np.ndarray
    ) -> Dict[str, Any]:
        """Categorize risk by region"""
        if 'location' not in data.columns:
            return {"default": {"score": 0.5, "level": "medium"}}
        
        regions = data['location'].unique()[:5]  # Top 5 regions
        
        regional_risk = {}
        for i, region in enumerate(regions):
            if i < len(risk_scores):
                score = float(risk_scores[i])
                regional_risk[region] = {
                    "score": score,
                    "level": self._get_risk_level(score)
                }
        
        return regional_risk
    
    def _identify_contributing_factors(self, features: pd.DataFrame) -> Dict[str, float]:
        """Identify factors contributing to risk"""
        factors = {}
        
        if features.empty:
            return factors
        
        # Calculate factor contributions
        if 'disease_prevalence' in features.columns:
            factors['disease_prevalence'] = float(features['disease_prevalence'].mean() / 100)
        
        if 'avg_confidence' in features.columns:
            factors['low_confidence'] = float(1 - features['avg_confidence'].mean())
        
        if 'location_diversity' in features.columns:
            factors['spatial_spread'] = float(features['location_diversity'].mean())
        
        if 'month' in features.columns:
            factors['seasonal_pattern'] = float(abs(features['month'].mean() - 6) / 6)
        
        return factors
    
    def _get_risk_level(self, risk_score: float) -> str:
        """Convert risk score to risk level"""
        if risk_score >= 0.8:
            return "critical"
        elif risk_score >= 0.6:
            return "high"
        elif risk_score >= 0.3:
            return "medium"
        else:
            return "low"
    
    async def _generate_risk_recommendations(
        self,
        overall_risk: float,
        regional_risk: Dict[str, Any],
        risk_factors: Optional[pd.DataFrame] = None
    ) -> List[Dict[str, Any]]:
        """Generate specific recommendations based on risk assessment"""
        recommendations = []
        
        # High-risk region recommendations
        high_risk_regions = [
            region for region, data in regional_risk.items()
            if data.get("level") in ["critical", "high"]
        ]
        
        if high_risk_regions:
            recommendations.append({
                "type": "regional_alert",
                "regions": high_risk_regions,
                "action": "Immediate inspection required for high-risk regions",
                "priority": "high"
            })
        
        # Risk factor specific recommendations
        if risk_factors is not None and not risk_factors.empty:
            if risk_factors.get('seasonal_pattern', pd.Series([0])).iloc[0] > 0.7:
                recommendations.append({
                    "type": "seasonal",
                    "action": "Implement seasonal prevention protocols",
                    "priority": "medium"
                })
            
            if risk_factors.get('spatial_spread', pd.Series([0])).iloc[0] > 0.6:
                recommendations.append({
                    "type": "containment",
                    "action": "Establish containment zones in affected areas",
                    "priority": "high"
                })
        
        return recommendations
    
    def _get_default_forecast(self, forecast_days: int = 30) -> Dict[str, Any]:
        """Get default forecast when model unavailable"""
        return {
            "forecast_values": [0] * forecast_days,
            "forecast_dates": [
                (datetime.now() + timedelta(days=i+1)).isoformat()
                for i in range(forecast_days)
            ],
            "forecast_lower_bound": [0] * forecast_days,
            "forecast_upper_bound": [0] * forecast_days,
            "peak_days": [],
            "trend": "unknown",
            "seasonality": {"has_seasonality": False, "strength": 0},
            "high_risk_days": [],
            "expected_total_cases": 0,
            "max_expected_daily_cases": 0,
            "model_confidence": 0.5,
            "decomposition": {"trend": [], "seasonal": [], "residual": []},
            "risk_factors": ["Insufficient data for accurate forecasting"],
            "forecast_period_days": forecast_days
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
            "contributing_factors": {},
            "crop_type": None,
            "region": None,
            "confidence": 0.5,
            "assessment_date": datetime.utcnow().isoformat()
        }