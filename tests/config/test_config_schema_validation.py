from pathlib import Path
import json

import jsonschema
import pytest


def _load_schema(schema_filename: str) -> dict:
    repo_root = Path(__file__).resolve().parents[2]
    schema_path = repo_root / "schemas" / schema_filename
    with schema_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def test_realized_volatility_config_schema():
    schema = _load_schema("realized_volatility_config.schema.json")
    validator = jsonschema.Draft202012Validator(schema)

    valid_config = {
        "window_definition": {
            "method": "simple",
            "parameters": {},
        }
    }
    validator.validate(valid_config)

    invalid_config = {
        "window_definition": {
            "method": "simple",
            # missing parameters
        }
    }
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(invalid_config)


def test_implied_volatility_config_schema():
    schema = _load_schema("implied_volatility_config.schema.json")
    validator = jsonschema.Draft202012Validator(schema)

    valid_config = {
        "surface_definition": {
            "method": "spline",
            "parameters": {},
        }
    }
    validator.validate(valid_config)

    invalid_config = {
        "surface_definition": {
            "parameters": {},
            # missing method
        }
    }
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(invalid_config)


def test_dealer_metrics_config_schema():
    schema = _load_schema("dealer_metrics_config.schema.json")
    validator = jsonschema.Draft202012Validator(schema)

    valid_config = {
        "aggregation_definition": {
            "method": "net_position",
            "parameters": {},
        }
    }
    validator.validate(valid_config)

    invalid_config = {
        "aggregation_definition": {
            "method": "net_position",
            "parameters": "not-an-object",
        }
    }
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(invalid_config)
