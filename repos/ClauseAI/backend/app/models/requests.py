from pydantic import BaseModel, Field, model_validator
from typing import Optional, List, Dict, Any, Literal

class BillTextExtractionRequest(BaseModel):
    request_id: Optional[str] = Field(None, description="Client-provided request ID")
    file_content: Optional[str] = Field(None, description="Base64 encoded file content or raw text")
    file_type: Optional[str] = Field(None, description="File type: pdf, docx, or txt")
    storage_path: Optional[str] = Field(None, description="Supabase storage object path")
    bucket: Optional[str] = Field(None, description="Supabase storage bucket override")
    original_file_name: Optional[str] = Field(None, description="Original uploaded file name")
    mime_type: Optional[str] = Field(None, description="Uploaded file content type")
    size_bytes: Optional[int] = Field(None, description="Uploaded file size in bytes")

    @model_validator(mode="after")
    def validate_source(self):
        if not self.file_content and not self.storage_path:
            raise ValueError("Either file_content or storage_path must be provided")
        return self

class TitleDescSummaryRequest(BaseModel):
    request_id: Optional[str] = Field(None, description="Client-provided request ID")
    bill_text: str = Field(..., description="Extracted bill text")
    example_bill: Optional[str] = Field(None, description="Example bill text for few-shot learning")
    example_title: Optional[str] = Field(None, description="Example title")
    example_description: Optional[str] = Field(None, description="Example description")
    example_summary: Optional[str] = Field(None, description="Example summary")

class BillSimilarityRequest(BaseModel):
    request_id: Optional[str] = Field(None, description="Client-provided request ID")
    title: str = Field(..., description="Bill title")
    description: str = Field(..., description="Bill description")
    summary: str = Field(..., description="Bill summary")
    jurisdiction: Optional[str] = Field(None, description="Jurisdiction code (e.g., CA)")

class SimilarBillsLoadRequest(BaseModel):
    request_id: Optional[str] = Field(None, description="Client-provided request ID")
    similarity_matches: List[Dict[str, Any]] = Field(..., description="List of similarity match results from Step 2 Part 2")
    user_bill_text: str = Field(..., description="Raw text of the user's bill")
    user_bill_metadata: Optional[Dict[str, Any]] = Field(None, description="User bill title, description, summary")
    jurisdiction: Optional[str] = Field(None, description="Jurisdiction code (e.g., CA)")

class BillAnalysisRequest(BaseModel):
    request_id: Optional[str] = Field(None, description="Client-provided request ID")
    user_bill: Dict[str, Any] = Field(..., description="User bill with title, description, summary")
    user_bill_raw_text: str = Field(..., description="Raw text of the user's bill")
    passed_bills: List[Dict[str, Any]] = Field(..., description="List of passed similar bills")
    failed_bills: List[Dict[str, Any]] = Field(..., description="List of failed similar bills")
    policy_area: str = Field(..., description="Policy area description")
    jurisdiction: Optional[str] = Field(None, description="Jurisdiction code (e.g., CA)")
    phase: Literal["report", "fixes"] = Field("report", description="Analysis phase")
    report_context: Optional[Dict[str, Any]] = Field(
        None,
        description="Phase-1 report payload required for fixes generation"
    )

class ConflictAnalysisRequest(BaseModel):
    request_id: Optional[str] = Field(None, description="Client-provided request ID")
    bill_text: str = Field(..., description="Bill text to analyze for legal conflicts")
    phase: Literal["report", "fixes"] = Field("report", description="Analysis phase")
    report_context: Optional[Dict[str, Any]] = Field(
        None,
        description="Phase-1 report payload required for fixes generation"
    )

class StakeholderAnalysisRequest(BaseModel):
    request_id: Optional[str] = Field(None, description="Client-provided request ID")
    bill_text: str = Field(..., description="Bill text to analyze for stakeholder impact")
    phase: Literal["report", "fixes"] = Field("report", description="Analysis phase")
    report_context: Optional[Dict[str, Any]] = Field(
        None,
        description="Phase-1 report payload required for fixes generation"
    )

class BillInspectRequest(BaseModel):
    request_id: Optional[str] = Field(None, description="Client-provided request ID")
    bill_id: Optional[str] = Field(None, description="Bill identifier from corpus")
    bill_text: Optional[str] = Field(None, description="Raw bill text for on-demand inspection")
    jurisdiction: Optional[str] = Field(None, description="Jurisdiction code (e.g., CA)")
    source: Optional[str] = Field(None, description="Source label (user/similar/loaded)")
    title: Optional[str] = Field(None, description="Optional display title override")
    description: Optional[str] = Field(None, description="Optional display description override")