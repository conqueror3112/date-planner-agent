"""
Integration tests for Date-Planner Agent system.
Tests the full Planner → Executor → Verifier flow with mocked APIs.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from agents import PlannerAgent, ExecutorAgent, VerifierAgent
from utils.schemas import (
    VenueResult,
    WeatherResult,
    ImageResult,
    PlannerOutput,
    ExecutorOutput,
    ExecutorStepResult
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def sample_user_request():
    """Sample user request for testing"""
    return {
        "city": "Mumbai",
        "budget_per_person": 1500,
        "date_time": "Saturday 7pm",
        "preferences": "vegetarian, romantic",
        "dietary_restrictions": ["vegetarian"],
        "accessibility_needs": None
    }


@pytest.fixture
def mock_venue_results():
    """Mock venue results from Places API"""
    return [
        VenueResult(
            name="Test Restaurant 1",
            address="123 Test Street, Mumbai",
            rating=4.5,
            price_level=2,
            open_now=True,
            opening_hours=["Monday: 11:00 AM – 11:00 PM", "Tuesday: 11:00 AM – 11:00 PM"],
            phone="+91-1234567890",
            website="https://test-restaurant.com",
            google_maps_url="https://maps.google.com/test",
            photos=["https://example.com/photo1.jpg"],
            cuisine_type="Indian",
            wheelchair_accessible=True
        ),
        VenueResult(
            name="Test Restaurant 2",
            address="456 Test Avenue, Mumbai",
            rating=4.2,
            price_level=2,
            open_now=True,
            opening_hours=None,
            phone=None,
            website=None,
            google_maps_url="https://maps.google.com/test2",
            photos=[],
            cuisine_type="Continental",
            wheelchair_accessible=False
        )
    ]


@pytest.fixture
def mock_weather_result():
    """Mock weather result from Weather API"""
    return WeatherResult(
        temperature=28.5,
        feels_like=30.0,
        condition="Clear",
        description="Clear sky",
        humidity=65,
        wind_speed=3.5,
        rain_probability=10.0,
        suggestion="Perfect weather for outdoor dining"
    )


@pytest.fixture
def mock_image_results():
    """Mock image results from Unsplash API"""
    return [
        ImageResult(
            url="https://images.unsplash.com/test1",
            photographer="Test Photographer 1",
            description="Romantic restaurant"
        ),
        ImageResult(
            url="https://images.unsplash.com/test2",
            photographer="Test Photographer 2",
            description="Dinner date"
        )
    ]


# ============================================================================
# PLANNER TESTS
# ============================================================================

@patch('agents.planner.OpenAI')
def test_planner_creates_valid_plan(mock_openai_class, sample_user_request):
    """Test that Planner creates a valid structured plan"""
    # Mock OpenAI response
    mock_client = Mock()
    mock_openai_class.return_value = mock_client

    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = '''
    {
        "user_intent": "Plan a romantic vegetarian date in Mumbai",
        "steps": [
            {
                "id": "step_1",
                "action": "get_weather",
                "params": {"latitude": 19.0760, "longitude": 72.8777, "target_datetime": null},
                "reasoning": "Check weather conditions"
            },
            {
                "id": "step_2",
                "action": "search_venues",
                "params": {
                    "query": "vegetarian romantic restaurant",
                    "latitude": 19.0760,
                    "longitude": 72.8777,
                    "radius": 3000,
                    "venue_type": "restaurant",
                    "max_results": 5
                },
                "reasoning": "Find suitable venues"
            },
            {
                "id": "step_3",
                "action": "get_images",
                "params": {"query": "romantic restaurant", "count": 3},
                "reasoning": "Get inspirational images"
            },
            {
                "id": "step_4",
                "action": "compose_final",
                "params": {"include_timeline": true, "include_backup_plan": true},
                "reasoning": "Compose final plan"
            }
        ],
        "estimated_budget": 3000,
        "safety_notes": ["Choose public venue", "Share location with friend"]
    }
    '''
    mock_client.chat.completions.create.return_value = mock_response

    # Test
    planner = PlannerAgent()
    plan = planner.plan(sample_user_request)

    # Assertions
    assert plan is not None
    assert plan.plan_id.startswith("plan_")
    assert len(plan.steps) == 4
    assert plan.steps[0].action == "get_weather"
    assert plan.steps[1].action == "search_venues"
    assert plan.estimated_budget == 3000
    assert len(plan.safety_notes) > 0


def test_planner_fallback_on_llm_failure(sample_user_request):
    """Test that Planner creates fallback plan if LLM fails"""
    with patch('agents.planner.OpenAI') as mock_openai_class:
        mock_client = Mock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("API Error")

        planner = PlannerAgent()
        plan = planner.plan(sample_user_request)

        # Should still return a plan (fallback)
        assert plan is not None
        assert len(plan.steps) > 0


# ============================================================================
# EXECUTOR TESTS
# ============================================================================

def test_executor_executes_all_steps(mock_venue_results, mock_weather_result, mock_image_results):
    """Test that Executor executes all plan steps"""
    # Create a mock plan
    from utils.schemas import PlanStep
    plan = PlannerOutput(
        plan_id="test_plan_123",
        user_intent="Test date plan",
        steps=[
            PlanStep(id="step_1", action="get_weather", params={"latitude": 19.0760, "longitude": 72.8777}),
            PlanStep(id="step_2", action="search_venues", params={
                "query": "restaurant", "latitude": 19.0760, "longitude": 72.8777,
                "radius": 3000, "venue_type": "restaurant", "max_results": 5
            }),
            PlanStep(id="step_3", action="get_images", params={"query": "restaurant", "count": 3})
        ],
        estimated_budget=1500,
        safety_notes=[]
    )

    # Mock API services
    with patch('services.places_api.PlacesAPIService') as mock_places, \
         patch('services.weather_api.WeatherAPIService') as mock_weather, \
         patch('services.unsplash_api.UnsplashAPIService') as mock_unsplash:

        # Setup mocks
        mock_places_instance = Mock()
        mock_places_instance.search_venues.return_value = mock_venue_results
        mock_places.return_value = mock_places_instance

        mock_weather_instance = Mock()
        mock_weather_instance.get_forecast.return_value = mock_weather_result
        mock_weather.return_value = mock_weather_instance

        mock_unsplash_instance = Mock()
        mock_unsplash_instance.search_images.return_value = mock_image_results
        mock_unsplash.return_value = mock_unsplash_instance

        # Execute
        executor = ExecutorAgent()
        result = executor.execute(plan)

        # Assertions
        assert result is not None
        assert result.plan_id == "test_plan_123"
        assert len(result.results) == 3
        assert result.overall_status in ["success", "partial_success"]


def test_executor_handles_api_failures():
    """Test that Executor handles API failures gracefully"""
    from utils.schemas import PlanStep
    plan = PlannerOutput(
        plan_id="test_plan_456",
        user_intent="Test failure handling",
        steps=[
            PlanStep(id="step_1", action="get_weather", params={"latitude": 0, "longitude": 0})
        ],
        estimated_budget=1000,
        safety_notes=[]
    )

    with patch('services.weather_api.WeatherAPIService') as mock_weather:
        mock_weather_instance = Mock()
        mock_weather_instance.get_forecast.return_value = None  # Simulate failure
        mock_weather.return_value = mock_weather_instance

        executor = ExecutorAgent()
        result = executor.execute(plan)

        assert result is not None
        assert result.results[0].status == "failed"


# ============================================================================
# VERIFIER TESTS
# ============================================================================

def test_verifier_approves_valid_plan(sample_user_request, mock_venue_results, mock_weather_result):
    """Test that Verifier approves a valid plan"""
    # Create mock plan and executor output
    from utils.schemas import PlanStep
    plan = PlannerOutput(
        plan_id="test_plan_789",
        user_intent="Test date plan",
        steps=[],
        estimated_budget=1500,
        safety_notes=["Safety note 1"]
    )

    executor_output = ExecutorOutput(
        plan_id="test_plan_789",
        results=[
            ExecutorStepResult(
                step_id="step_1",
                action="get_weather",
                status="success",
                payload=mock_weather_result.model_dump(),
                source="openweather"
            ),
            ExecutorStepResult(
                step_id="step_2",
                action="search_venues",
                status="success",
                payload={"venues": [v.model_dump() for v in mock_venue_results]},
                source="google_places"
            )
        ],
        overall_status="success",
        execution_time_seconds=2.5
    )

    # Verify
    verifier = VerifierAgent()
    result = verifier.verify(plan, executor_output, sample_user_request)

    # Assertions
    assert result is not None
    assert result.approved is True
    assert result.final_output is not None
    assert len(result.final_output.venues) > 0
    assert result.confidence_score > 0.5


def test_verifier_rejects_plan_without_venues(sample_user_request):
    """Test that Verifier rejects plan with no venues"""
    from utils.schemas import PlanStep
    plan = PlannerOutput(
        plan_id="test_plan_empty",
        user_intent="Test empty plan",
        steps=[],
        estimated_budget=1500,
        safety_notes=[]
    )

    executor_output = ExecutorOutput(
        plan_id="test_plan_empty",
        results=[
            ExecutorStepResult(
                step_id="step_1",
                action="search_venues",
                status="partial",
                payload={"venues": []},  # No venues
                source="google_places"
            )
        ],
        overall_status="partial_success",
        execution_time_seconds=1.0
    )

    verifier = VerifierAgent()
    result = verifier.verify(plan, executor_output, sample_user_request)

    # Should not be approved
    assert result.approved is False
    assert len(result.issues) > 0
    assert any(issue.severity == "critical" for issue in result.issues)


# ============================================================================
# INTEGRATION TEST
# ============================================================================

def test_full_pipeline_integration(
    sample_user_request,
    mock_venue_results,
    mock_weather_result,
    mock_image_results
):
    """Test the complete Planner → Executor → Verifier pipeline"""
    # Mock all external dependencies
    with patch('agents.planner.OpenAI') as mock_openai, \
         patch('services.places_api.PlacesAPIService') as mock_places, \
         patch('services.weather_api.WeatherAPIService') as mock_weather, \
         patch('services.unsplash_api.UnsplashAPIService') as mock_unsplash:

        # Setup OpenAI mock
        mock_openai_instance = Mock()
        mock_openai.return_value = mock_openai_instance
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''
        {
            "user_intent": "Plan a date in Mumbai",
            "steps": [
                {"id": "step_1", "action": "get_weather", "params": {"latitude": 19.0760, "longitude": 72.8777}, "reasoning": "Check weather"},
                {"id": "step_2", "action": "search_venues", "params": {"query": "restaurant", "latitude": 19.0760, "longitude": 72.8777, "radius": 3000, "venue_type": "restaurant", "max_results": 5}, "reasoning": "Find venues"},
                {"id": "step_3", "action": "get_images", "params": {"query": "restaurant", "count": 3}, "reasoning": "Get images"}
            ],
            "estimated_budget": 3000,
            "safety_notes": ["Safety first"]
        }
        '''
        mock_openai_instance.chat.completions.create.return_value = mock_response

        # Setup API service mocks
        mock_places_instance = Mock()
        mock_places_instance.search_venues.return_value = mock_venue_results
        mock_places.return_value = mock_places_instance

        mock_weather_instance = Mock()
        mock_weather_instance.get_forecast.return_value = mock_weather_result
        mock_weather.return_value = mock_weather_instance

        mock_unsplash_instance = Mock()
        mock_unsplash_instance.search_images.return_value = mock_image_results
        mock_unsplash.return_value = mock_unsplash_instance

        # Run full pipeline
        planner = PlannerAgent()
        executor = ExecutorAgent()
        verifier = VerifierAgent()

        # Step 1: Plan
        plan = planner.plan(sample_user_request)
        assert plan is not None

        # Step 2: Execute
        executor_output = executor.execute(plan)
        assert executor_output is not None

        # Step 3: Verify
        verifier_output = verifier.verify(plan, executor_output, sample_user_request)
        assert verifier_output is not None
        assert verifier_output.approved is True
        assert verifier_output.final_output is not None

        # Verify final output structure
        final_plan = verifier_output.final_output
        assert final_plan.city == "Mumbai"
        assert len(final_plan.venues) > 0
        assert final_plan.weather_forecast is not None
        assert len(final_plan.safety_checklist) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
