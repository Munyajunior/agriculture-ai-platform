# shared/types/agriculture_ai/types/enums.py
"""Enumeration types for Agriculture AI Platform"""

from enum import Enum, auto


class CropType(str, Enum):
    """Supported crop types"""
    TOMATO = "tomato"
    CASSAVA = "cassava"
    MAIZE = "maize"
    
    @classmethod
    def list_supported(cls) -> list[str]:
        return [crop.value for crop in cls]


class DiseaseType(str, Enum):
    """Plant disease types"""
    # Tomato Diseases
    TOMATO_EARLY_BLIGHT = "tomato_early_blight"
    TOMATO_LATE_BLIGHT = "tomato_late_blight"
    TOMATO_LEAF_MOLD = "tomato_leaf_mold"
    TOMATO_SEPTORIA_LEAF_SPOT = "tomato_septoria_leaf_spot"
    TOMATO_SPIDER_MITES = "tomato_spider_mites"
    TOMATO_TARGET_SPOT = "tomato_target_spot"
    TOMATO_YELLOW_CURL = "tomato_yellow_curl"
    
    # Cassava Diseases
    CASSAVA_MOSAIC = "cassava_mosaic"
    CASSAVA_BROWN_STREAK = "cassava_brown_streak"
    CASSAVA_GREEN_MITE = "cassava_green_mite"
    CASSAVA_BACTERIAL_BLIGHT = "cassava_bacterial_blight"
    
    # Maize Diseases
    MAIZE_RUST = "maize_rust"
    MAIZE_NORTHERN_LEAF_BLIGHT = "maize_northern_leaf_blight"
    MAIZE_GRAY_LEAF_SPOT = "maize_gray_leaf_spot"
    MAIZE_COMMON_RUST = "maize_common_rust"
    
    @classmethod
    def get_diseases_for_crop(cls, crop: CropType) -> list[str]:
        """Get all diseases for a specific crop"""
        mapping = {
            CropType.TOMATO: [
                cls.TOMATO_EARLY_BLIGHT,
                cls.TOMATO_LATE_BLIGHT,
                cls.TOMATO_LEAF_MOLD,
                cls.TOMATO_SEPTORIA_LEAF_SPOT,
                cls.TOMATO_SPIDER_MITES,
                cls.TOMATO_TARGET_SPOT,
                cls.TOMATO_YELLOW_CURL,
            ],
            CropType.CASSAVA: [
                cls.CASSAVA_MOSAIC,
                cls.CASSAVA_BROWN_STREAK,
                cls.CASSAVA_GREEN_MITE,
                cls.CASSAVA_BACTERIAL_BLIGHT,
            ],
            CropType.MAIZE: [
                cls.MAIZE_RUST,
                cls.MAIZE_NORTHERN_LEAF_BLIGHT,
                cls.MAIZE_GRAY_LEAF_SPOT,
                cls.MAIZE_COMMON_RUST,
            ],
        }
        return [d.value for d in mapping.get(crop, [])]


class PredictionStatus(str, Enum):
    """Prediction processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SYNCED = "synced"

class InferenceSource(str, Enum):
    """Inference source types"""
    EDGE = "edge"
    CLOUD = "cloud"
    HYBRID = "hybrid"

class DeviceType(str, Enum):
    """Device types supported"""
    MOBILE = "mobile"
    WEB = "web"
    DRONE = "drone"
    UAV = "uav"
    JETSON = "jetson"
    RASPBERRY_PI = "raspberry_pi"
    IOT_SENSOR = "iot_sensor"


class SyncStatus(str, Enum):
    """Synchronization status"""
    PENDING = "pending"
    SYNCING = "syncing"
    COMPLETED = "completed"
    FAILED = "failed"


class UserRole(str, Enum):
    """User role definitions"""
    FARMER = "farmer"
    AGRONOMIST = "agronomist"
    ADMIN = "admin"
    RESEARCHER = "researcher"

class TreatmentType(str, Enum):
    """Treatment types for diseases"""
    CHEMICAL = "chemical"
    BIOLOGICAL = "biological"
    CULTURAL = "cultural"
    INTEGRATED = "integrated"

class TelemetryType(str, Enum):
    """Types of telemetry data"""
    GPS= "gps"
    SENSOR = "sensor"
    STATUS = "status"
    DETECTION = "detection"

class ModelType(str, Enum):
    """Types of AI models used for inference"""
    MOBILENETV3 = "mobilenetv3"
    YOLOV8 = "yolov8"
    VIT = "vit"

class SyncLogStatus(str, Enum):
    """Status of synchronization logs"""
    PENDING = "pending"
    SYNCING = "syncing"
    COMPLETED = "completed"
    FAILED = "failed"

class SyncLogType(str, Enum):
    """Types of synchronization logs"""
    IMAGE = "image"
    PREDICTION = "prediction"
    TELEMETRY = "telemetry"