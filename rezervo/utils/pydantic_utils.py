from pydantic import ValidationError


def hashable_validation_errors(err: ValidationError):
    return [(e.get("loc"), e.get("type")) for e in (err.errors())]
