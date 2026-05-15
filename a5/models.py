"""
Pydantic models for the API Endpoint Discovery Agent.
Used for form inputs, structured tool outputs, and data validation.
"""
from pydantic import BaseModel, Field


class DiscoveryRequest(BaseModel):
    """Form input model — rendered as a Prefab UI form."""
    api_doc_url: str = Field(
        ...,
        title="API Documentation URL",
        description="Full URL to the API reference documentation (e.g., https://pokeapi.co/docs/v2)",
    )
    question: str = Field(
        ...,
        title="Question",
        description="The question you want to answer using data from this API",
    )


class EndpointParam(BaseModel):
    """A single query parameter for an endpoint."""
    name: str
    type: str = "string"
    required: bool = False
    description: str = ""


class ResponseField(BaseModel):
    """A single field in the endpoint's response."""
    name: str
    type: str = "string"
    description: str = ""


class EndpointInfo(BaseModel):
    """A discovered API endpoint with its metadata."""
    method: str = "GET"
    path: str
    description: str = ""
    query_params: list[EndpointParam] = []
    response_fields: list[ResponseField] = []
    is_relevant: bool = False
    relevance_reason: str = ""


class PostgresColumn(BaseModel):
    """A column in the recommended PostgreSQL table."""
    name: str
    pg_type: str
    nullable: bool = True
    description: str = ""


class PostgresTableSpec(BaseModel):
    """Recommended PostgreSQL table schema."""
    table_name: str
    columns: list[PostgresColumn] = []
    primary_key: str = "id"
    indexes: list[str] = []
    create_table_ddl: str = ""


class TransformationStep(BaseModel):
    """A single data transformation step."""
    step_number: int
    description: str
    sql_or_code: str = ""


class DiscoveryResult(BaseModel):
    """Full output of the endpoint discovery process."""
    total_endpoints_found: int = 0
    relevant_endpoints: list[EndpointInfo] = []
    limitations: list[str] = []
    pg_table: PostgresTableSpec | None = None
    transformations: list[TransformationStep] = []
    query_strategy: str = ""
    final_sql: str = ""
