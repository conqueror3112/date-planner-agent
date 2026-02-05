"""
Pydantic schemas for structured outputs across the Date-Planner Agent system.
These ensure type safety and structured communication between agents.
"""
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field
from datetime import datetime


# ============================================================================
# PLANNER SCHEMAS
# ============================================================================

class PlanStep(BaseModel):
    """Individual step in the execution plan"""
    id: str = Field(..., description="Unique step identifier")
    action: Literal["get_weather", "search_venues", "check_events", "get_images", "compose_final"] = Field(
        ..., description="Action to execute"
    )
    params: Dict[str, Any] = Field(..., description="Parameters for the action")
    reasoning: Optional[str] = Field(None, description="Why this step is needed")


class PlannerOutput(BaseModel):
    """Structured output from the Planner agent"""
    plan_id: str = Field(..., description="Unique plan identifier")
    user_intent: str = Field(..., description="Parsed user intent summary")
    steps: List[PlanStep] = Field(..., description="Ordered list of execution steps")
    estimated_budget: Optional[float] = Field(None, description="Estimated total budget")
    safety_notes: List[str] = Field(default_factory=list, description="Safety considerations")


# ============================================================================
# EXECUTOR SCHEMAS
# ============================================================================

class VenueResult(BaseModel):
    """Individual venue information"""
    name: str
    address: str
    rating: Optional[float] = None
    price_level: Optional[int] = Field(None, description="1-4 scale (1=cheap, 4=expensive)")
    open_now: Optional[bool] = None
    opening_hours: Optional[List[str]] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    google_maps_url: Optional[str] = None
    photos: List[str] = Field(default_factory=list, description="Photo URLs")
    cuisine_type: Optional[str] = None
    wheelchair_accessible: Optional[bool] = None


class WeatherResult(BaseModel):
    """Weather forecast information"""
    temperature: float = Field(..., description="Temperature in Celsius")
    feels_like: float = Field(..., description="Feels like temperature")
    condition: str = Field(..., description="Weather condition (e.g., Clear, Rain)")
    description: str = Field(..., description="Detailed description")
    humidity: int
    wind_speed: float
    rain_probability: Optional[float] = Field(None, description="Chance of rain (0-100)")
    suggestion: str = Field(..., description="Weather-based suggestion for the date")


class EventResult(BaseModel):
    """Event information"""
    name: str
    description: Optional[str] = None
    start_time: str
    end_time: Optional[str] = None
    venue: str
    ticket_url: Optional[str] = None
    price: Optional[str] = None
    category: Optional[str] = None


class ImageResult(BaseModel):
    """Image information from Unsplash"""
    url: str
    photographer: str
    description: Optional[str] = None


class ExecutorStepResult(BaseModel):
    """Result from executing a single step"""
    step_id: str
    action: str
    status: Literal["success", "failed", "partial"]
    payload: Dict[str, Any] = Field(..., description="Action-specific result data")
    source: str = Field(..., description="API source (e.g., 'google_places', 'openweather')")
    error_message: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class ExecutorOutput(BaseModel):
    """Complete output from Executor agent"""
    plan_id: str
    results: List[ExecutorStepResult]
    overall_status: Literal["success", "partial_success", "failed"]
    execution_time_seconds: float


# ============================================================================
# VERIFIER SCHEMAS
# ============================================================================

class ValidationIssue(BaseModel):
    """Individual validation issue"""
    severity: Literal["critical", "warning", "info"]
    category: str = Field(..., description="Issue category (e.g., 'budget', 'timing', 'safety')")
    message: str
    affected_step: Optional[str] = None
    suggestion: Optional[str] = None


class SafetyCheck(BaseModel):
    """Safety validation result"""
    public_venue: bool = Field(..., description="Is venue in public area")
    operating_hours_valid: bool = Field(..., description="Venue open during planned time")
    crowd_rating: Optional[str] = Field(None, description="Expected crowd level")
    emergency_info: List[str] = Field(default_factory=list, description="Emergency contacts/info")
    safety_score: int = Field(..., ge=0, le=10, description="Overall safety score (0-10)")


class DatePlanTimeline(BaseModel):
    """Timeline item for the date"""
    time: str
    activity: str
    location: Optional[str] = None
    duration_minutes: Optional[int] = None
    notes: Optional[str] = None


class FinalDatePlan(BaseModel):
    """Complete date plan output"""
    title: str
    summary: str
    date_time: str
    city: str
    total_budget_estimate: str

    # Main components
    venues: List[VenueResult]
    weather_forecast: Optional[WeatherResult] = None
    nearby_events: List[EventResult] = Field(default_factory=list)
    timeline: List[DatePlanTimeline]

    # Safety & logistics
    safety_checklist: List[str]
    transportation_suggestions: List[str]
    backup_plan: Optional[str] = None

    # Visual elements
    venue_images: List[ImageResult] = Field(default_factory=list)

    # Metadata
    created_at: datetime = Field(default_factory=datetime.now)


class VerifierOutput(BaseModel):
    """Output from Verifier agent"""
    plan_id: str
    approved: bool
    confidence_score: float = Field(..., ge=0, le=1, description="Confidence in plan quality (0-1)")
    issues: List[ValidationIssue] = Field(default_factory=list)
    safety_check: Optional[SafetyCheck] = None
    final_output: Optional[FinalDatePlan] = None
    retry_recommendations: List[str] = Field(
        default_factory=list,
        description="Suggestions for Executor if retry needed"
    )
    verified_at: datetime = Field(default_factory=datetime.now)


# ============================================================================
# API REQUEST/RESPONSE SCHEMAS
# ============================================================================

class DatePlanRequest(BaseModel):
    """User request for date planning"""
    city: str = Field(..., description="City for the date")
    budget_per_person: Optional[float] = Field(None, description="Budget per person in local currency")
    date_time: str = Field(..., description="Date and time (e.g., 'Saturday 7pm' or '2024-02-10 19:00')")
    preferences: Optional[str] = Field(None, description="Additional preferences (cuisine, vibe, dietary, etc.)")
    dietary_restrictions: Optional[List[str]] = Field(None, description="Dietary restrictions")
    accessibility_needs: Optional[str] = Field(None, description="Accessibility requirements")

    class Config:
        json_schema_extra = {
            "example": {
                "city": "Mumbai",
                "budget_per_person": 1500,
                "date_time": "Saturday 7pm",
                "preferences": "vegetarian, romantic, outdoor seating preferred",
                "dietary_restrictions": ["vegetarian"],
                "accessibility_needs": None
            }
        }


class DatePlanResponse(BaseModel):
    """API response containing the complete date plan"""
    success: bool
    plan_id: str
    message: str
    plan: Optional[FinalDatePlan] = None
    errors: List[str] = Field(default_factory=list)
    processing_time_seconds: float
