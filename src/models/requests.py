from pydantic import BaseModel, Field


class AnalyzePdfRequest(BaseModel):
	file_data: str = Field(description="File content in base64 format")
