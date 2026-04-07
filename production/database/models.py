"""
Pydantic base models for the production package.
"""
from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    """
    Base model that generates strict JSON schemas compatible with OpenAI Agents SDK.
    
    This model forbids extra fields by default to ensure schema compatibility
    with the function_tool decorator from OpenAI Agents SDK.
    """
    model_config = ConfigDict(extra="forbid")
