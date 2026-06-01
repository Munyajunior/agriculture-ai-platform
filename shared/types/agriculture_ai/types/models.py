# shared/types/agriculture_ai/types/models.py
"""Database models for Agriculture AI Platform"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any
from uuid import UUID, uuid4
from sqlalchemy import (
    Column, String, DateTime, Float, Integer, Boolean, 
    JSON, ForeignKey, Enum, Table, Index
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship


from .enums import (CropType, DiseaseType, DeviceType, SyncLogStatus, SyncStatus, PredictionStatus, UserRole,InferenceSource,
TreatmentType,TelemetryType, ModelType, SyncLogType, SyncLogStatus)

Base = declarative_base()


class User(Base):
    """User account model"""
    __tablename__ = "users"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    role = Column(Enum(UserRole), nullable=False)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    verification_token = Column(String(255), nullable=True)
    reset_password_token = Column(String(255), nullable=True)
    reset_password_expires = Column(DateTime, nullable=True)
    phone_number = Column(String(20))
    profile_picture_url = Column(String(500))
    preferences = Column(JSON, default={})
    last_login_ip = Column(String(45))
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    last_login = Column(DateTime)
    
    # Relationships
    farms = relationship("Farm", back_populates="owner")
    scans = relationship("Scan", back_populates="user")
    devices = relationship("Device", back_populates="user")
    
    __table_args__ = (
        Index("idx_users_email_active", "email", "is_active"),
        Index("idx_users_role_active", "role", "is_active"),
        Index("idx_users_reset_token", "reset_password_token"),
    )


class Farm(Base):
    """Farm/Field model"""
    __tablename__ = "farms"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    location = Column(String(255))
    latitude = Column(Float)
    longitude = Column(Float)
    crop_type = Column(Enum(CropType), nullable=False)
    area_hectares = Column(Float)
    soil_type = Column(String(50))
    irrigation_type = Column(String(50))
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    # Relationships
    owner = relationship("User", back_populates="farms")
    scans = relationship("Scan", back_populates="farm")
    
    __table_args__ = (
        Index("idx_farms_user_crop", "user_id", "crop_type"),
        Index("idx_farms_location", "latitude", "longitude"),
    )


class Scan(Base):
    """Image scan record"""
    __tablename__ = "scans"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    farm_id = Column(PGUUID(as_uuid=True), ForeignKey("farms.id", ondelete="SET NULL"))
    image_url = Column(String(500), nullable=False)
    thumbnail_url = Column(String(500))
    original_filename = Column(String(255))
    file_size_bytes = Column(Integer)
    image_width = Column(Integer)
    image_height = Column(Integer)
    captured_at = Column(DateTime, default=datetime.now(timezone.utc))
    device_type = Column(Enum(DeviceType), nullable=False)
    location_lat = Column(Float)
    location_lon = Column(Float)
    sync_status = Column(Enum(SyncStatus), default=SyncStatus.PENDING)
    is_offline = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    
    # Relationships
    user = relationship("User", back_populates="scans")
    farm = relationship("Farm", back_populates="scans")
    predictions = relationship("Prediction", back_populates="scan", cascade="all, delete-orphan")
    sync_logs = relationship("SyncLog", back_populates="scan")
    
    __table_args__ = (
        Index("idx_scans_user_created", "user_id", "created_at"),
        Index("idx_scans_farm_created", "farm_id", "created_at"),
        Index("idx_scans_sync_status", "sync_status"),
        Index("idx_scans_captured_location", "captured_at", "location_lat", "location_lon"),
    )


class Prediction(Base):
    """AI prediction result"""
    __tablename__ = "predictions"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    scan_id = Column(PGUUID(as_uuid=True), ForeignKey("scans.id", ondelete="CASCADE"), nullable=False)
    disease_type = Column(Enum(DiseaseType,
        name="disease_types"
    ), nullable=False)
    confidence_score = Column(Float, nullable=False)
    inference_source = Column(Enum(InferenceSource, name="inference_sources"), nullable=False)
    model_version_id = Column(PGUUID(as_uuid=True), ForeignKey("model_versions.id"))
    processing_time_ms = Column(Integer)
    is_verified = Column(Boolean, default=False)
    verified_by = Column(PGUUID(as_uuid=True), ForeignKey("users.id"))
    verified_at = Column(DateTime)
    status = Column(Enum(PredictionStatus, name="prediction_statuses"), default="pending")
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    
    # Relationships
    scan = relationship("Scan", back_populates="predictions")
    model_version = relationship("ModelVersion")
    treatments = relationship("Treatment", secondary="prediction_treatments")
    
    __table_args__ = (
        Index("idx_predictions_scan", "scan_id"),
        Index("idx_predictions_disease_confidence", "disease_type", "confidence_score"),
        Index("idx_predictions_verified", "is_verified", "verified_at"),
        Index("idx_predictions_status_created", "status", "created_at"),
    )


class Disease(Base):
    """Disease information catalog"""
    __tablename__ = "diseases"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(100), unique=True, nullable=False)
    scientific_name = Column(String(200))
    crop_type = Column(Enum("tomato", "cassava", "maize", name="crop_types"), nullable=False)
    description = Column(String(1000))
    symptoms = Column(JSON, default=list)  # List of symptoms
    causes = Column(JSON, default=list)    # List of causes
    severity_level = Column(Integer, default=1)  # 1-5
    transmission_methods = Column(JSON, default=list)
    environmental_factors = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    # Relationships
    treatments = relationship("Treatment", back_populates="disease")
    
    __table_args__ = (
        Index("idx_diseases_crop", "crop_type"),
        Index("idx_diseases_severity", "severity_level"),
    )


class Treatment(Base):
    """Treatment recommendation"""
    __tablename__ = "treatments"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    disease_id = Column(PGUUID(as_uuid=True), ForeignKey("diseases.id", ondelete="CASCADE"), nullable=False)
    treatment_type = Column(Enum(TreatmentType, name="treatment_types"))  
    product_name = Column(String(200))
    active_ingredients = Column(JSON, default=list)
    application_method = Column(String(100))
    dosage_instructions = Column(String(500))
    frequency_days = Column(Integer)
    precautions = Column(JSON, default=list)
    organic_option = Column(Boolean, default=False)
    effectiveness_rating = Column(Float, default=0.0)  # 0-1
    estimated_cost = Column(String(50))
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    # Relationships
    disease = relationship("Disease", back_populates="treatments")


# Association table for predictions and treatments
prediction_treatments = Table(
    "prediction_treatments",
    Base.metadata,
    Column("prediction_id", PGUUID(as_uuid=True), ForeignKey("predictions.id", ondelete="CASCADE")),
    Column("treatment_id", PGUUID(as_uuid=True), ForeignKey("treatments.id", ondelete="CASCADE")),
    Index("idx_pred_treat_pred", "prediction_id"),
    Index("idx_pred_treat_treat", "treatment_id"),
)


class Device(Base):
    """Device registry for edge/IoT devices"""
    __tablename__ = "devices"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    device_name = Column(String(100), nullable=False)
    device_type = Column(Enum(DeviceType, name="device_types"), nullable=False)
    device_id = Column(String(255), unique=True, nullable=False)
    firmware_version = Column(String(50))
    capabilities = Column(JSON, default=dict)  # Edge AI, sensors, etc.
    last_heartbeat = Column(DateTime)
    is_active = Column(Boolean, default=True)
    registered_at = Column(DateTime, default=datetime.now(timezone.utc))
    last_sync_at = Column(DateTime)
    
    # Relationships
    user = relationship("User", back_populates="devices")
    telemetry = relationship("Telemetry", back_populates="device")
    
    __table_args__ = (
        Index("idx_devices_user_type", "user_id", "device_type"),
        Index("idx_devices_active", "is_active", "last_heartbeat"),
        Index("idx_devices_unique_id", "device_id", unique=True),
    )


class Telemetry(Base):
    """Telemetry data from IoT devices and drones"""
    __tablename__ = "telemetry"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    device_id = Column(PGUUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False)
    timestamp = Column(DateTime, default=datetime.now(timezone.utc), nullable=False)
    telemetry_type = Column(Enum(TelemetryType, name="telemetry_types"))  # gps, sensor, status, detection
    data = Column(JSON, nullable=False)  # Flexible telemetry data
    battery_level = Column(Float)  # 0-100
    signal_strength = Column(Integer)  # dBm
    gps_latitude = Column(Float)
    gps_longitude = Column(Float)
    gps_altitude = Column(Float)
    speed_kph = Column(Float)
    
    # Relationships
    device = relationship("Device", back_populates="telemetry")
    
    __table_args__ = (
        Index("idx_telemetry_device_time", "device_id", "timestamp"),
        Index("idx_telemetry_type_time", "telemetry_type", "timestamp"),
        Index("idx_telemetry_gps", "gps_latitude", "gps_longitude"),
        Index("idx_telemetry_timestamp", "timestamp"),
    )


class ModelVersion(Base):
    """AI model version management"""
    __tablename__ = "model_versions"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    version = Column(String(20), nullable=False, unique=True)
    model_type = Column(Enum(ModelType, name="model_types"), nullable=False)  # mobilenetv3, yolov8, vit
    model_architecture = Column(String(100))
    model_url = Column(String(500))  # URL to download model
    onnx_url = Column(String(500))   # URL to ONNX version
    quantized_url = Column(String(500))  # URL to quantized version
    input_shape = Column(JSON, default=list)
    output_shape = Column(JSON, default=list)
    classes = Column(JSON, default=list)  # Disease classes
    accuracy = Column(Float)
    precision = Column(Float)
    recall = Column(Float)
    f1_score = Column(Float)
    model_size_mb = Column(Float)
    is_active = Column(Boolean, default=False)
    is_deployed = Column(Boolean, default=False)
    deployment_date = Column(DateTime)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    metadata = Column(JSON, default=dict)
    
    __table_args__ = (
        Index("idx_models_active", "is_active"),
        Index("idx_models_version", "version"),
        Index("idx_models_deployed", "is_deployed", "deployment_date"),
    )


class SyncLog(Base):
    """Offline sync logging"""
    __tablename__ = "sync_logs"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    scan_id = Column(PGUUID(as_uuid=True), ForeignKey("scans.id", ondelete="CASCADE"), nullable=False)
    device_id = Column(PGUUID(as_uuid=True), ForeignKey("devices.id", ondelete="SET NULL"))
    synced_at = Column(DateTime, default=datetime.now(timezone.utc))
    sync_duration_ms = Column(Integer)
    data_size_bytes = Column(Integer)
    sync_type = Column(Enum(SyncLogType, name="sync_types"), default="image")
    status = Column(Enum(SyncLogStatus, name="sync_statuses"), default="pending")
    error_message = Column(String(500))
    retry_count = Column(Integer, default=0)
    
    # Relationships
    scan = relationship("Scan", back_populates="sync_logs")
    
    __table_args__ = (
        Index("idx_sync_logs_scan", "scan_id"),
        Index("idx_sync_logs_status_retry", "status", "retry_count"),
        Index("idx_sync_logs_synced", "synced_at"),
    )