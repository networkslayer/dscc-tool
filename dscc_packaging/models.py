from pydantic import BaseModel, ValidationError, field_validator, Field
from typing import List, Optional, Literal
from uuid import UUID
from enum import Enum
from dscc_tool.logger import logging

logger = logging.getLogger(__name__)

# ─────────────────────────────────────
# Enums
# ─────────────────────────────────────

class ContentType(str, Enum):
    detections = "detection"
    dashboards = "dashboard"
    enrichments = "enrichment"
    models = "model"
    pipelines = "pipeline"
    notebooks = "notebook"

class Platform(str, Enum):
    classic = "classic"
    serverless = "serverless"

class Feature(str, Enum):
    sql_warehouse = "sql_warehouse"
    jobs = "jobs"
    serverless_jobs = "serverless_jobs"
    unity_catalog = "unity_catalog"

# ─────────────────────────────────────
# App-Level Requirements
# ─────────────────────────────────────

class DSCCRequirements(BaseModel):
    platform: List[Platform]
    features: List[Feature]

    @field_validator("platform", "features", mode="before")
    @classmethod
    def normalize_strings(cls, v):
        return [item.lower() if isinstance(item, str) else item for item in v]

# ─────────────────────────────────────
# Detection Metadata (Optional, Nested)
# ─────────────────────────────────────

class DSCCDetectionMetadata(BaseModel):
    name: str
    description: str
    fidelity: Literal["high", "medium", "low"]
    category: Optional[str] = None
    objective: Optional[List[str]] = None
    false_positives: Optional[List[str]] = None
    severity: Optional[str] = None
    validation: Optional[List[str]] = None
    tests: Optional[List[str]] = None

# ─────────────────────────────────────
# Notebook Metadata (dscc: section)
# ─────────────────────────────────────

class DSCCNotebookMetadata(BaseModel):
    author: str
    created: str
    modified: str
    version: str
    content_type: str
    uuid: str
    platform: Optional[str] = None
    detection: Optional[DSCCDetectionMetadata] = None

    @field_validator("uuid")
    @classmethod
    def validate_uuid(cls, v: str):
        try:
            UUID(v)
        except Exception:
            raise ValueError("Invalid UUID format")
        return v

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str):
        if v.count(".") != 2:
            raise ValueError("version must be semantic format: MAJOR.MINOR.PATCH")
        return v

    @field_validator("content_type")
    @classmethod
    def validate_content_type(cls, v: str):
        valid = {e.value for e in ContentType}
        if v not in valid:
            raise ValueError(f"content_type must be one of {valid}")
        return v

# ─────────────────────────────────────
# Notebook Wrapper
# ─────────────────────────────────────

class DSCCNotebook(BaseModel):
    path: str
    dscc: DSCCNotebookMetadata

# ─────────────────────────────────────
# App Manifest
# ─────────────────────────────────────

class DSCCManifest(BaseModel):
    app: str
    notebooks: List[DSCCNotebook]

    # Optional app-level metadata
    app_friendly_name: Optional[str] = None
    author: Optional[str] = None
    version: Optional[str] = None
    release_notes: Optional[str] = None
    description: Optional[str] = None
    content_type: Optional[List[str]] = None
    installation: Optional[str] = None
    configuration: Optional[str] = None
    logo: Optional[str] = None
    screenshots: Optional[List[str]] = None

    requirements: DSCCRequirements

    @field_validator("version")
    @classmethod
    def validate_app_version(cls, v: str):
        if v and v.count(".") != 2:
            raise ValueError("App version must follow semantic format MAJOR.MINOR.PATCH")
        return v
