"""
Executor Agent: Executes planned steps by calling third-party APIs.
Handles API calls, error recovery, and result aggregation.
"""
import time
from typing import List, Dict, Any
from datetime import datetime
from utils.helpers import get_logger
from utils.schemas import PlannerOutput, ExecutorStepResult, ExecutorOutput
from services import PlacesAPIService, WeatherAPIService, UnsplashAPIService

logger = get_logger("ExecutorAgent")


class ExecutorAgent:
    """
    Executor Agent: Executes planned steps by calling APIs.

    Responsibilities:
    - Execute each step in the plan sequentially
    - Call appropriate API services
    - Handle errors gracefully
    - Aggregate results in structured format
    - Support retry logic for failed steps
    """

    def __init__(self):
        # Initialize API services
        self.places_service = PlacesAPIService()
        self.weather_service = WeatherAPIService()
        self.unsplash_service = UnsplashAPIService()

    def execute(self, plan: PlannerOutput, retry_steps: List[str] = None) -> ExecutorOutput:
        """
        Execute all steps in the plan.

        Args:
            plan: PlannerOutput from Planner agent
            retry_steps: List of step IDs to retry (if any)

        Returns:
            ExecutorOutput with results from all steps
        """
        logger.info(f"[Executor] Executing plan {plan.plan_id} with {len(plan.steps)} steps")
        start_time = time.time()

        results = []
        steps_to_execute = plan.steps

        # Filter to retry steps if specified
        if retry_steps:
            steps_to_execute = [s for s in plan.steps if s.id in retry_steps]
            logger.info(f"[Executor] Retrying {len(steps_to_execute)} steps")

        # Execute each step
        for step in steps_to_execute:
            logger.info(f"[Executor] Executing step: {step.id} - {step.action}")
            result = self._execute_step(step)
            results.append(result)

            # Log step result
            if result.status == "success":
                logger.info(f"[Executor] ✓ Step {step.id} completed successfully")
            else:
                logger.warning(f"[Executor] ✗ Step {step.id} failed: {result.error_message}")

        # Determine overall status
        success_count = sum(1 for r in results if r.status == "success")
        if success_count == len(results):
            overall_status = "success"
        elif success_count > 0:
            overall_status = "partial_success"
        else:
            overall_status = "failed"

        execution_time = time.time() - start_time

        executor_output = ExecutorOutput(
            plan_id=plan.plan_id,
            results=results,
            overall_status=overall_status,
            execution_time_seconds=round(execution_time, 2)
        )

        logger.info(f"[Executor] Execution complete: {overall_status} in {execution_time:.2f}s")
        return executor_output

    def _execute_step(self, step) -> ExecutorStepResult:
        """Execute a single step based on action type"""
        try:
            if step.action == "get_weather":
                return self._get_weather(step)
            elif step.action == "search_venues":
                return self._search_venues(step)
            elif step.action == "check_events":
                return self._check_events(step)
            elif step.action == "get_images":
                return self._get_images(step)
            elif step.action == "compose_final":
                return self._compose_final(step)
            else:
                return ExecutorStepResult(
                    step_id=step.id,
                    action=step.action,
                    status="failed",
                    payload={},
                    source="executor",
                    error_message=f"Unknown action: {step.action}"
                )

        except Exception as e:
            logger.error(f"[Executor] Error in step {step.id}: {str(e)}")
            return ExecutorStepResult(
                step_id=step.id,
                action=step.action,
                status="failed",
                payload={},
                source="executor",
                error_message=str(e)
            )

    def _get_weather(self, step) -> ExecutorStepResult:
        """Execute weather check"""
        params = step.params
        latitude = params.get("latitude", 0)
        longitude = params.get("longitude", 0)
        target_datetime = params.get("target_datetime")

        weather_result = self.weather_service.get_forecast(
            latitude=latitude,
            longitude=longitude,
            target_datetime=target_datetime
        )

        if weather_result:
            return ExecutorStepResult(
                step_id=step.id,
                action=step.action,
                status="success",
                payload=weather_result.model_dump(),
                source="openweather"
            )
        else:
            return ExecutorStepResult(
                step_id=step.id,
                action=step.action,
                status="failed",
                payload={},
                source="openweather",
                error_message="Failed to fetch weather data"
            )

    def _search_venues(self, step) -> ExecutorStepResult:
        """Execute venue search"""
        params = step.params
        query = params.get("query", "restaurant")
        latitude = params.get("latitude", 0)
        longitude = params.get("longitude", 0)
        radius = params.get("radius", 3000)
        venue_type = params.get("venue_type", "restaurant")
        max_results = params.get("max_results", 5)

        venues = self.places_service.search_venues(
            query=query,
            latitude=latitude,
            longitude=longitude,
            radius=radius,
            venue_type=venue_type,
            max_results=max_results
        )

        if venues:
            return ExecutorStepResult(
                step_id=step.id,
                action=step.action,
                status="success",
                payload={"venues": [v.model_dump() for v in venues]},
                source="google_places"
            )
        else:
            return ExecutorStepResult(
                step_id=step.id,
                action=step.action,
                status="partial",
                payload={"venues": []},
                source="google_places",
                error_message="No venues found matching criteria"
            )

    def _check_events(self, step) -> ExecutorStepResult:
        """Execute events check (placeholder - can integrate Eventbrite/Ticketmaster)"""
        # This is a placeholder - in production, integrate with Eventbrite or similar API
        logger.info("[Executor] Events check - using placeholder (no API integrated)")

        return ExecutorStepResult(
            step_id=step.id,
            action=step.action,
            status="success",
            payload={"events": []},  # Empty for now
            source="events_placeholder",
            error_message="Events API not integrated (placeholder)"
        )

    def _get_images(self, step) -> ExecutorStepResult:
        """Execute image search"""
        params = step.params
        query = params.get("query", "romantic date")
        count = params.get("count", 3)

        images = self.unsplash_service.search_images(
            query=query,
            count=count
        )

        if images:
            return ExecutorStepResult(
                step_id=step.id,
                action=step.action,
                status="success",
                payload={"images": [img.model_dump() for img in images]},
                source="unsplash"
            )
        else:
            return ExecutorStepResult(
                step_id=step.id,
                action=step.action,
                status="partial",
                payload={"images": []},
                source="unsplash",
                error_message="No images found"
            )

    def _compose_final(self, step) -> ExecutorStepResult:
        """Compose final plan (metadata step)"""
        return ExecutorStepResult(
            step_id=step.id,
            action=step.action,
            status="success",
            payload={"ready_for_composition": True},
            source="executor"
        )
