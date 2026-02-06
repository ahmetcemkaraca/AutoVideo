#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Configuration validation module.

Provides JSON schema validation for all configuration types.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Tuple

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Schema Directory
# ═══════════════════════════════════════════════════════════════════════════════

SCHEMA_DIR = Path(__file__).parent / "schemas"


# ═══════════════════════════════════════════════════════════════════════════════
# JSON Schemas
# ═══════════════════════════════════════════════════════════════════════════════

RENDER_CONFIG_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Video Renderer Configuration",
    "type": "object",
    "properties": {
        "work_dir": {"type": "string"},
        "music_dir": {"type": ["string", "null"]},
        "tmp_dir": {"type": ["string", "null"]},
        "output_path": {"type": ["string", "null"]},
        "width": {"type": "integer", "minimum": 1},
        "height": {"type": "integer", "minimum": 1},
        "fps": {"type": "integer", "enum": [24, 25, 30, 50, 60]},
        "codec": {"type": "string", "enum": ["h264", "h265", "vp9", "av1"]},
        "duration_seconds": {"type": "integer", "minimum": 0},
        "use_hw_accel": {"type": "boolean"},
        "parallel_encode": {"type": "boolean"},
        "post_action": {"type": "string", "enum": ["keep", "archive", "delete"]},
    },
}


PIPELINE_CONFIG_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "VideoAutomation Pipeline Configuration",
    "type": "object",
    "required": ["work_dir", "styles", "genres"],
    "properties": {
        "version": {"type": "integer", "const": 2},
        "format_version": {"type": "string", "const": "2.0"},
        "work_dir": {"type": "string"},
        "intro_video": {"type": "string"},
        "loop_video": {"type": "string"},
        "continuous_mode": {"type": "boolean"},
        "delay_between_videos": {"type": "integer", "minimum": 0},
        "max_continuous_iterations": {
            "oneOf": [
                {"type": "null"},
                {"type": "integer", "minimum": 1}
            ]
        },
        "styles": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1
        },
        "genres": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1
        },
        "youtube": {
            "type": "object",
            "properties": {
                "client_secrets_file": {"type": "string"},
                "credentials_file": {"type": "string"},
                "default_category": {"type": "string"},
                "default_privacy": {"enum": ["public", "private", "unlisted"]},
                "max_uploads_per_day": {"type": "integer", "minimum": 1},
                "min_upload_interval": {"type": "integer", "minimum": 0}
            }
        },
        "render": {
            "type": "object",
            "properties": {
                "codec": {"enum": ["h264", "h265", "vp9", "av1"]},
                "width": {"type": "integer", "minimum": 1},
                "height": {"type": "integer", "minimum": 1},
                "fps": {"enum": [24, 25, 30, 50, 60]},
                "target_duration": {
                    "type": "string",
                    "pattern": "^\\d{1,2}:\\d{2}:\\d{2}$"
                }
            }
        },
        "log_level": {
            "enum": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        },
        "enable_metrics": {"type": "boolean"},
        "metrics_port": {"type": "integer", "minimum": 1, "maximum": 65535}
    }
}


LIVESTREAM_CONFIG_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "VideoLivestream Configuration",
    "type": "object",
    "properties": {
        "content_dir": {"type": "string"},
        "min_duration_minutes": {"type": "integer", "minimum": 1},
        "max_duration_minutes": {"type": "integer", "minimum": 1},
        "stream": {
            "type": "object",
            "properties": {
                "rtmp_url": {"type": "string"},
                "stream_key": {"type": "string"},
                "video_bitrate": {"type": "string"},
                "audio_bitrate": {"type": "string"},
                "resolution": {"type": "string"},
                "fps": {"type": "integer"},
                "preset": {"type": "string"},
            }
        },
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# Validation Functions
# ═══════════════════════════════════════════════════════════════════════════════

def validate_config(data: Dict[str, Any], schema_name: str) -> bool:
    """
    Validate config against JSON schema.

    Args:
        data: Configuration data dictionary
        schema_name: Name of schema ("render", "pipeline", "livestream")

    Returns:
        True if valid

    Raises:
        ConfigValidationError: If validation fails
    """
    try:
        import jsonschema
    except ImportError:
        logger.warning("jsonschema not installed, skipping schema validation")
        return True

    schemas = {
        "render": RENDER_CONFIG_SCHEMA,
        "pipeline": PIPELINE_CONFIG_SCHEMA,
        "livestream": LIVESTREAM_CONFIG_SCHEMA,
    }

    schema = schemas.get(schema_name)
    if schema is None:
        raise ValueError(f"Unknown schema: {schema_name}")

    try:
        from jsonschema import validate, ValidationError
        validate(instance=data, schema=schema)
        return True
    except ValidationError as e:
        from .base import ConfigValidationError
        raise ConfigValidationError(
            f"Invalid config: {e.message}",
            field=".".join(str(p) for p in e.path),
            value=e.instance
        )


def validate_with_schema(config_data: Dict[str, Any], schema: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate config data against provided JSON schema.

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    try:
        import jsonschema
    except ImportError:
        logger.warning("jsonschema not installed, skipping schema validation")
        return True, []

    validator = jsonschema.Draft7Validator(schema)

    errors = []
    for error in validator.iter_errors(config_data):
        path = " -> ".join(str(p) for p in error.path) if error.path else "root"
        errors.append(f"{path}: {error.message}")

    return len(errors) == 0, errors


def save_schema(schema_name: str, schema: Dict[str, Any]) -> None:
    """
    Save JSON schema to file.

    Args:
        schema_name: Name of schema file (without .json extension)
        schema: Schema dictionary
    """
    SCHEMA_DIR.mkdir(parents=True, exist_ok=True)
    schema_file = SCHEMA_DIR / f"{schema_name}.json"

    with open(schema_file, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)

    logger.info(f"Schema saved to {schema_file}")


# Save schemas on module import
def _init_schemas():
    """Initialize schema files."""
    save_schema("render_config", RENDER_CONFIG_SCHEMA)
    save_schema("pipeline_config", PIPELINE_CONFIG_SCHEMA)
    save_schema("livestream_config", LIVESTREAM_CONFIG_SCHEMA)


# Auto-initialize schemas on import
_init_schemas()


# Re-export for convenience
from .base import ConfigValidationError as ValidationError
