from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class BaseResponse(BaseModel):
    success: bool = Field(..., description="Whether the operation was successful")
    step: str = Field(..., description="Step name/identifier")
    processing_time: float = Field(..., description="Processing time in seconds")
    data: Optional[Any] = Field(None, description="Response data")
    request_id: Optional[str] = Field(None, description="Request identifier")
    status: Optional[str] = Field(None, description="Request status")

class HealthResponse(BaseModel):
    status: str = Field(..., description="Health status")
    version: str = Field(..., description="API version")

class BillTextExtractionResponse(BaseResponse):
    data: Optional[str] = Field(None, description="Extracted bill text")

class TitleDescSummaryData(BaseModel):
    Title: str = Field(..., description="Generated bill title")
    Description: str = Field(..., description="Generated bill description")
    Summary: str = Field(..., description="Generated bill summary")

class TitleDescSummaryResponse(BaseResponse):
    data: Optional[TitleDescSummaryData | Dict[str, Any]] = None

class SimilarityMatch(BaseModel):
    Bill_Text: str = Field(..., description="Reference to bill text")
    Bill_ID: str = Field(..., description="Bill identifier")
    Bill_Number: Optional[str] = Field(None, description="Human-readable bill number")
    Bill_Title: Optional[str] = Field(None, description="Bill title")
    Bill_Description: Optional[str] = Field(None, description="Bill description")
    Bill_URL: Optional[str] = Field(None, description="Bill URL")
    Date_Presented: Optional[str] = Field(None, description="Date presented")
    Date_Passed: Optional[str] = Field(None, description="Date passed")
    Votes: Optional[Dict[str, Any]] = Field(None, description="Vote breakdown")
    Stage_Passed: Optional[int] = Field(None, description="Stage passed indicator")
    Score: float = Field(..., description="Similarity score")
    Passed: bool = Field(..., description="Whether the bill passed")

class BillSimilarityResponse(BaseResponse):
    data: Optional[List[SimilarityMatch] | Dict[str, Any]] = None

class LoadedBillWithCategories(BaseModel):
    Bill_ID: str = Field(..., description="Bill identifier")
    Bill_Number: Optional[str] = Field(None, description="Human-readable bill number")
    Bill_Title: str = Field(..., description="Bill title")
    Bill_Description: str = Field(..., description="Bill description")
    Bill_Text: Optional[str] = Field(None, description="Normalized bill text")
    Bill_URL: Optional[str] = Field(None, description="Bill URL")
    Date_Presented: Optional[str] = Field(None, description="Date presented")
    Date_Passed: Optional[str] = Field(None, description="Date passed")
    Votes: Optional[Dict[str, Any]] = Field(None, description="Vote breakdown")
    Stage_Passed: Optional[int] = Field(None, description="Stage passed indicator")
    Categorized_Sentences: Dict[str, Any] = Field(..., description="Categorized sentences by type")
    Passed: bool = Field(..., description="Whether the bill passed")

class SimilarBillsData(BaseModel):
    User_Bill: Dict[str, Any] = Field(..., description="User's bill metadata")
    Passed_Bills: List[LoadedBillWithCategories] = Field(..., description="Loaded passed bills with categorized sentences")
    Failed_Bills: List[LoadedBillWithCategories] = Field(..., description="Loaded failed bills with categorized sentences")

class SimilarBillsLoadResponse(BaseResponse):
    data: Optional[SimilarBillsData | Dict[str, Any]] = None

class BillAnalysisResponse(BaseResponse):
    data: Optional[Dict[str, Any]] = Field(None, description="Analysis results with passages and insights")

class ConflictAnalysisResponse(BaseResponse):
    data: Optional[Dict[str, Any]] = Field(None, description="Conflict analysis with iterations and reasoning")

class StakeholderAnalysisData(BaseModel):
    structured_data: Dict[str, Any] = Field(..., description="Stakeholder analysis results")
    metadata: Dict[str, Any] = Field(..., description="Analysis metadata including search queries")

class StakeholderAnalysisResponse(BaseResponse):
    data: Optional[StakeholderAnalysisData | Dict[str, Any]] = None

class BillInspectData(BaseModel):
    bill_id: Optional[str] = Field(None, description="Bill identifier")
    bill_number: Optional[str] = Field(None, description="Bill number")
    source: Optional[str] = Field(None, description="Source type")
    title: Optional[str] = Field(None, description="Bill title")
    description: Optional[str] = Field(None, description="Bill description")
    bill_url: Optional[str] = Field(None, description="Bill URL")
    date_presented: Optional[str] = Field(None, description="Date presented")
    date_passed: Optional[str] = Field(None, description="Date passed")
    cleaned_text: str = Field(..., description="Normalized bill text")
    char_count: int = Field(..., description="Character count for cleaned text")
    line_count: int = Field(..., description="Line count for cleaned text")

class BillInspectResponse(BaseResponse):
    data: Optional[BillInspectData | Dict[str, Any]] = None
