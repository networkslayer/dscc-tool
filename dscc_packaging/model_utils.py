from typing import get_args, get_origin, Type, Union
from pydantic import BaseModel
from enum import Enum

# Get a sensible default for a Pydantic field
def default_for_field(name, field):
    if field.default is not None:
        return field.default
    elif field.annotation == list or getattr(field.annotation, '__origin__', None) is list:
        return []
    elif field.annotation == str:
        return ""
    elif getattr(field.annotation, '__origin__', None) is not None and getattr(field.annotation, '__origin__', None).__name__ == 'Literal':
        # For Literal types, use the first allowed value as default
        return get_args(field.annotation)[0]
    elif isinstance(field.annotation, type) and issubclass(field.annotation, Enum):
        return list(field.annotation)[0]
    else:
        return f"<{name}>"

# Get options for fields with Enum or Literal types
def get_options_from_model(model_cls: Type[BaseModel]):
    options = {}
    for name, field in model_cls.model_fields.items():
        ann = field.annotation
        # Unwrap Optional/Union types
        if get_origin(ann) is Union:
            args = [a for a in get_args(ann) if a is not type(None)]
            if args:
                ann = args[0]
        if isinstance(ann, type) and issubclass(ann, Enum):
            options[name] = [e.value for e in ann]
        elif get_origin(ann) is not None and get_origin(ann).__name__ == 'Literal':
            options[name] = list(get_args(ann))
        elif get_origin(ann) is list:
            elem_type = get_args(ann)[0]
            # Unwrap Optional/Union for list element
            if get_origin(elem_type) is Union:
                elem_args = [a for a in get_args(elem_type) if a is not type(None)]
                if elem_args:
                    elem_type = elem_args[0]
            if isinstance(elem_type, type) and issubclass(elem_type, Enum):
                options[name] = [e.value for e in elem_type]
            elif get_origin(elem_type) is not None and get_origin(elem_type).__name__ == 'Literal':
                options[name] = list(get_args(elem_type))
    return options

# Get simple validators for fields
def get_validators_from_model(model_cls: Type[BaseModel]):
    validators = {}
    for name, field in model_cls.model_fields.items():
        ann = field.annotation
        if isinstance(ann, type) and issubclass(ann, Enum):
            allowed = set(ann)
            validators[name] = lambda v, allowed=allowed: v in allowed
        elif get_origin(ann) is not None and get_origin(ann).__name__ == 'Literal':
            allowed = set(get_args(ann))
            validators[name] = lambda v, allowed=allowed: v in allowed
        elif ann is int:
            validators[name] = lambda v: isinstance(v, int)
        elif ann is str:
            validators[name] = lambda v: isinstance(v, str) and v.strip() != ""
    return validators

# Get help/description text for each field
def get_help_from_model(model_cls: Type[BaseModel]):
    help_text = {}
    for name, field in model_cls.model_fields.items():
        if hasattr(field, 'description') and field.description:
            help_text[name] = field.description
        elif isinstance(field.annotation, type) and issubclass(field.annotation, Enum):
            help_text[name] = f"Allowed values: {', '.join([e.value for e in field.annotation])}"
        elif get_origin(field.annotation) is not None and get_origin(field.annotation).__name__ == 'Literal':
            help_text[name] = f"Allowed values: {', '.join(map(str, get_args(field.annotation)))}"
        else:
            help_text[name] = f"Type: {field.annotation}"
    return help_text 