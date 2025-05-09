from pydantic import BaseModel, ValidationError, field_validator, Field
from typing import List, Optional, Literal, Set
from uuid import UUID
from enum import Enum
from dscc_tool.logger import logging
from datetime import datetime

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

class DetectionPlatform(str, Enum):
    linux = "linux"
    windows = "windows"
    macos = "macos"
    databricks = "databricks"
    azure = "azure"
    aws = "aws"
    kubernetes = "kubernetes"
    gcp = "gcp"
    other = "other"

class Feature(str, Enum):
    sql_warehouse = "sql_warehouse"
    jobs = "jobs"
    serverless_jobs = "serverless_jobs"
    unity_catalog = "unity_catalog"

class Category(str, Enum):
    detection = "DETECTION"
    malware = "MALWARE"
    threat = "THREAT"
    intrusion = "INTRUSION"
    anomaly = "ANOMALY"
    policy = "POLICY"
    special_event = "SPECIAL_EVENT"

class Fidelity(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"

class Severity(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"

class Taxonomy(str, Enum):
    mitre = "mitre"
    nist = "nist"
    none = "none"

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
    name: str = Field(..., description="A short, human-readable name for this detection.")
    description: str = Field(None, description="Describe what the detection does.")
    fidelity: Fidelity = Field(Fidelity.medium, description="Detection fidelity: high, medium, or low.")
    category: Category = Field(Category.policy, description="OCSF category for this detection.")
    objective: Optional[str] = Field(None, description="What is the detection's objective?")
    false_positives: Optional[str] = Field("unknown", description="Describe possible false positives for this detection.")
    severity: Severity = Field(Severity.medium, description="Severity level for this detection (low, medium, high).")
    #validation: Optional[str] = Field(None, description="Describe how this detection is validated.")
    #tests: Optional[List[str]] = Field(default_factory=list, description="List of test case names or descriptions for this detection.")
    taxonomy: Optional[List[Taxonomy]] = Field(default_factory=lambda: ["none"], description="Taxonomy tags (mitre, nist, none).")
    platform: List[DetectionPlatform] = Field(default_factory=list, description="Target platforms (e.g., linux, windows, databricks, etc.).")
    tactic: Optional[str] = Field(None, description="MITRE ATT&CK tactic (if applicable).")
    technique: Optional[str] = Field(None, description="MITRE ATT&CK technique (if applicable).")
    sub_technique: Optional[str] = Field(None, description="MITRE ATT&CK sub-technique (if applicable).")

# ─────────────────────────────────────
# Notebook Metadata (dscc: section)
# ─────────────────────────────────────

class DSCCNotebookMetadata(BaseModel):
    author: str = Field(..., description="Author")
    created: str = Field(..., description="Created date", json_schema_extra={"prompt": False})
    modified: str = Field(..., description="Modified date", json_schema_extra={"prompt": False})
    version: str = Field("1.0.0", description="Semantic version (e.g., 1.0.0)")
    content_type: List[ContentType] = Field(default_factory=list, description="Content type")
    uuid: str = Field(..., description="UUID", json_schema_extra={"prompt": False})
    detection: Optional[DSCCDetectionMetadata] = Field(default=None, description="Detection metadata")

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

class AppStructureSpec(BaseModel):
    allowed_dirs: Set[str] = Field(default_factory=lambda: {
        "sample_data", "metadata", "lib", "base", "README.md", "manifest.yaml"
    })
    required_metadata_files: Set[str] = {"meta.yaml"}

class Requirements(BaseModel):
    platform: List[Literal["classic", "serverless"]]
    features: List[Literal["sql_warehouse", "serverless_jobs", "jobs", "unity_catalog"]]

    @field_validator("platform", "features", mode="before")
    @classmethod
    def check_non_empty_lists(cls, v):
        if not v or not isinstance(v, list):
            raise ValueError("Must be a non-empty list")
        return v

    model_config = {
        "extra": "forbid"
    }

class AppMetadata(BaseModel):
    app_name: str
    app_friendly_name: str
    author: str
    user_email: str
    version: str
    release_notes: Optional[str] = None
    description: str
    content_type: List[Literal["etl", "detection", "dashboard"]]
    requirements: Requirements
    installation: str
    configuration: str
    submitted_at: Optional[datetime] = None  
    release_date: Optional[datetime] = None  
    tags: Optional[List[str]] = Field(default_factory=list)
    logo: Optional[str] = None
    screenshots: Optional[List[str]] = []

    @field_validator("content_type", mode="before")
    @classmethod
    def check_content_type(cls, v):
        if not v or not isinstance(v, list):
            raise ValueError("content_type must be a non-empty list")
        return v

    model_config = {
        "extra": "forbid"
    }
