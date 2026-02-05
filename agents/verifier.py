"""
Verifier Agent: Validates execution results and composes final date plan.
Implements feedback loop to request retries from Executor when needed.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from utils.helpers import get_logger, generate_safety_checklist, is_venue_open
from utils.schemas import (
    PlannerOutput,
    ExecutorOutput,
    VerifierOutput,
    ValidationIssue,
    SafetyCheck,
    FinalDatePlan,
    VenueResult,
    WeatherResult,
    EventResult,
    ImageResult,
    DatePlanTimeline
)

logger = get_logger("VerifierAgent")


class VerifierAgent:
    """
    Verifier Agent: Validates results and creates final date plan.

    Responsibilities:
    - Validate executor results (completeness, quality)
    - Check venue availability (opening hours, budget)
    - Perform safety checks
    - Compose final human-readable date plan
    - Request retries if issues found
    """

    def __init__(self):
        pass

    def verify(
        self,
        plan: PlannerOutput,
        executor_output: ExecutorOutput,
        user_request: Dict[str, Any]
    ) -> VerifierOutput:
        """
        Verify execution results and compose final plan.

        Args:
            plan: Original planner output
            executor_output: Results from executor
            user_request: Original user request

        Returns:
            VerifierOutput with validation results and final plan
        """
        logger.info(f"[Verifier] Validating results for plan {plan.plan_id}")

        # Extract results from executor
        venues = self._extract_venues(executor_output)
        weather = self._extract_weather(executor_output)
        events = self._extract_events(executor_output)
        images = self._extract_images(executor_output)

        # Perform validations
        issues = []
        issues.extend(self._validate_venues(venues, user_request))
        issues.extend(self._validate_weather(weather))
        issues.extend(self._validate_budget(venues, user_request.get("budget_per_person")))

        # Perform safety check
        safety_check = self._perform_safety_check(venues, user_request)

        # Determine if plan is approved
        critical_issues = [i for i in issues if i.severity == "critical"]
        approved = len(critical_issues) == 0 and len(venues) > 0

        # Calculate confidence score
        confidence_score = self._calculate_confidence(venues, weather, issues)

        # Compose final plan if approved
        final_plan = None
        retry_recommendations = []

        if approved:
            logger.info("[Verifier] ✓ Plan approved - composing final output")
            final_plan = self._compose_final_plan(
                plan=plan,
                user_request=user_request,
                venues=venues,
                weather=weather,
                events=events,
                images=images,
                safety_check=safety_check
            )
        else:
            logger.warning(f"[Verifier] ✗ Plan not approved - {len(critical_issues)} critical issues")
            retry_recommendations = self._generate_retry_recommendations(issues, executor_output)

        return VerifierOutput(
            plan_id=plan.plan_id,
            approved=approved,
            confidence_score=confidence_score,
            issues=issues,
            safety_check=safety_check,
            final_output=final_plan,
            retry_recommendations=retry_recommendations
        )

    def _extract_venues(self, executor_output: ExecutorOutput) -> List[VenueResult]:
        """Extract venue results from executor output"""
        venues = []
        for result in executor_output.results:
            if result.action == "search_venues" and result.status == "success":
                venue_data = result.payload.get("venues", [])
                for v in venue_data:
                    try:
                        venues.append(VenueResult(**v))
                    except Exception as e:
                        logger.warning(f"[Verifier] Error parsing venue: {str(e)}")
        return venues

    def _extract_weather(self, executor_output: ExecutorOutput) -> Optional[WeatherResult]:
        """Extract weather result from executor output"""
        for result in executor_output.results:
            if result.action == "get_weather" and result.status == "success":
                try:
                    return WeatherResult(**result.payload)
                except Exception as e:
                    logger.warning(f"[Verifier] Error parsing weather: {str(e)}")
        return None

    def _extract_events(self, executor_output: ExecutorOutput) -> List[EventResult]:
        """Extract event results from executor output"""
        events = []
        for result in executor_output.results:
            if result.action == "check_events" and result.status == "success":
                event_data = result.payload.get("events", [])
                for e in event_data:
                    try:
                        events.append(EventResult(**e))
                    except Exception as e:
                        logger.warning(f"[Verifier] Error parsing event: {str(e)}")
        return events

    def _extract_images(self, executor_output: ExecutorOutput) -> List[ImageResult]:
        """Extract image results from executor output"""
        images = []
        for result in executor_output.results:
            if result.action == "get_images" and result.status == "success":
                image_data = result.payload.get("images", [])
                for img in image_data:
                    try:
                        images.append(ImageResult(**img))
                    except Exception as e:
                        logger.warning(f"[Verifier] Error parsing image: {str(e)}")
        return images

    def _validate_venues(self, venues: List[VenueResult], user_request: Dict) -> List[ValidationIssue]:
        """Validate venue results"""
        issues = []

        if len(venues) == 0:
            issues.append(ValidationIssue(
                severity="critical",
                category="venues",
                message="No venues found matching criteria",
                suggestion="Try broadening search criteria or increasing search radius"
            ))
        elif len(venues) < 3:
            issues.append(ValidationIssue(
                severity="warning",
                category="venues",
                message=f"Only {len(venues)} venues found - limited options",
                suggestion="Consider alternative cuisines or venue types"
            ))

        # Check for venues with ratings
        rated_venues = [v for v in venues if v.rating and v.rating > 0]
        if len(rated_venues) < len(venues) * 0.5:
            issues.append(ValidationIssue(
                severity="info",
                category="venues",
                message="Some venues missing rating information",
                suggestion="Verify venue quality through other sources"
            ))

        # Check accessibility if needed
        accessibility_needs = user_request.get("accessibility_needs")
        if accessibility_needs:
            accessible_venues = [v for v in venues if v.wheelchair_accessible is True]
            if len(accessible_venues) == 0:
                issues.append(ValidationIssue(
                    severity="warning",
                    category="accessibility",
                    message="No confirmed wheelchair-accessible venues found",
                    suggestion="Call venues directly to confirm accessibility"
                ))

        return issues

    def _validate_weather(self, weather: Optional[WeatherResult]) -> List[ValidationIssue]:
        """Validate weather results"""
        issues = []

        if not weather:
            issues.append(ValidationIssue(
                severity="warning",
                category="weather",
                message="Weather data unavailable",
                suggestion="Check weather manually before the date"
            ))
            return issues

        # Check for rain
        if weather.rain_probability and weather.rain_probability > 70:
            issues.append(ValidationIssue(
                severity="warning",
                category="weather",
                message=f"High chance of rain ({weather.rain_probability}%)",
                suggestion="Choose indoor venues or carry umbrellas"
            ))

        # Check for extreme temperatures
        if weather.temperature > 35:
            issues.append(ValidationIssue(
                severity="info",
                category="weather",
                message="Very hot weather expected",
                suggestion="Choose air-conditioned venues and stay hydrated"
            ))
        elif weather.temperature < 10:
            issues.append(ValidationIssue(
                severity="info",
                category="weather",
                message="Cold weather expected",
                suggestion="Dress warmly and consider indoor venues"
            ))

        return issues

    def _validate_budget(self, venues: List[VenueResult], budget: Optional[float]) -> List[ValidationIssue]:
        """Validate budget constraints"""
        issues = []

        if not budget:
            return issues

        # Check if venues match budget
        over_budget_count = 0
        for venue in venues:
            if venue.price_level and venue.price_level > 0:
                # Simple heuristic: price_level 1=<500, 2=500-1500, 3=1500-3000, 4=>3000
                estimated_cost = venue.price_level * 750
                if estimated_cost > budget:
                    over_budget_count += 1

        if over_budget_count == len(venues):
            issues.append(ValidationIssue(
                severity="warning",
                category="budget",
                message="All suggested venues may exceed budget",
                suggestion="Consider lower-priced alternatives or adjust budget"
            ))
        elif over_budget_count > 0:
            issues.append(ValidationIssue(
                severity="info",
                category="budget",
                message=f"{over_budget_count} venues may be above budget",
                suggestion="Review menu prices before booking"
            ))

        return issues

    def _perform_safety_check(self, venues: List[VenueResult], user_request: Dict) -> SafetyCheck:
        """Perform safety validation"""
        # Check if venues are in public areas (heuristic based on rating and type)
        public_venue = len(venues) > 0  # If venues found, assume public

        # Check operating hours (simplified)
        operating_hours_valid = True
        for venue in venues:
            if venue.open_now is False:
                operating_hours_valid = False
                break

        # Generate emergency info
        city = user_request.get("city", "")
        emergency_info = [
            "Emergency: 112 (India)",
            f"Local police: Search '{city} police station'",
            "Women's helpline: 1091",
            "Ambulance: 108"
        ]

        # Calculate safety score (0-10)
        safety_score = 8  # Base score
        if not operating_hours_valid:
            safety_score -= 1
        if len(venues) == 0:
            safety_score -= 2

        return SafetyCheck(
            public_venue=public_venue,
            operating_hours_valid=operating_hours_valid,
            crowd_rating="Moderate",  # Could be enhanced with real data
            emergency_info=emergency_info,
            safety_score=max(0, safety_score)
        )

    def _calculate_confidence(
        self,
        venues: List[VenueResult],
        weather: Optional[WeatherResult],
        issues: List[ValidationIssue]
    ) -> float:
        """Calculate confidence score (0-1)"""
        score = 1.0

        # Deduct for missing data
        if len(venues) == 0:
            score -= 0.5
        elif len(venues) < 3:
            score -= 0.2

        if not weather:
            score -= 0.1

        # Deduct for issues
        for issue in issues:
            if issue.severity == "critical":
                score -= 0.3
            elif issue.severity == "warning":
                score -= 0.1
            else:
                score -= 0.05

        return max(0.0, min(1.0, score))

    def _generate_retry_recommendations(
        self,
        issues: List[ValidationIssue],
        executor_output: ExecutorOutput
    ) -> List[str]:
        """Generate recommendations for retry"""
        recommendations = []

        for issue in issues:
            if issue.severity == "critical":
                if issue.category == "venues":
                    recommendations.append("Retry venue search with broader criteria")
                    recommendations.append("Increase search radius to 5000m")

        return recommendations

    def _compose_final_plan(
        self,
        plan: PlannerOutput,
        user_request: Dict,
        venues: List[VenueResult],
        weather: Optional[WeatherResult],
        events: List[EventResult],
        images: List[ImageResult],
        safety_check: SafetyCheck
    ) -> FinalDatePlan:
        """Compose the final date plan"""
        city = user_request.get("city", "")
        date_time = user_request.get("date_time", "")
        budget = user_request.get("budget_per_person")

        # Generate title and summary
        title = f"Date Night in {city}"
        summary = f"{plan.user_intent}. We've found {len(venues)} great venue options for you!"

        # Create timeline
        timeline = self._generate_timeline(date_time, venues)

        # Generate safety checklist
        safety_checklist = generate_safety_checklist(
            venue_name=venues[0].name if venues else "",
            time=date_time
        )

        # Transportation suggestions
        transportation = [
            "Book a cab through Uber/Ola for convenience",
            "Share ride details with a friend",
            "Metro is a safe and affordable option for major cities",
            "Arrive 10-15 minutes early"
        ]

        # Backup plan
        backup_plan = None
        if weather and weather.rain_probability and weather.rain_probability > 50:
            backup_plan = "If it rains heavily, consider rescheduling or choosing a fully indoor venue with covered parking."

        return FinalDatePlan(
            title=title,
            summary=summary,
            date_time=date_time,
            city=city,
            total_budget_estimate=f"₹{budget * 2:,.0f}" if budget else "Flexible",
            venues=venues[:5],  # Top 5 venues
            weather_forecast=weather,
            nearby_events=events,
            timeline=timeline,
            safety_checklist=safety_checklist,
            transportation_suggestions=transportation,
            backup_plan=backup_plan,
            venue_images=images
        )

    def _generate_timeline(self, date_time: str, venues: List[VenueResult]) -> List[DatePlanTimeline]:
        """Generate a suggested timeline for the date"""
        timeline = []

        # Simple timeline (can be enhanced)
        if venues:
            venue_name = venues[0].name

            timeline = [
                DatePlanTimeline(
                    time="6:30 PM",
                    activity="Meet at venue",
                    location=venue_name,
                    duration_minutes=15,
                    notes="Arrive a bit early to get a good table"
                ),
                DatePlanTimeline(
                    time="6:45 PM",
                    activity="Order drinks/appetizers",
                    location=venue_name,
                    duration_minutes=30,
                    notes="Start with light conversation"
                ),
                DatePlanTimeline(
                    time="7:15 PM",
                    activity="Main course",
                    location=venue_name,
                    duration_minutes=60,
                    notes="Enjoy your meal together"
                ),
                DatePlanTimeline(
                    time="8:30 PM",
                    activity="Dessert/wrap up",
                    location=venue_name,
                    duration_minutes=30,
                    notes="Optional: Explore nearby for a walk"
                ),
                DatePlanTimeline(
                    time="9:00 PM",
                    activity="Head home",
                    location="Safe return journey",
                    duration_minutes=None,
                    notes="Share your ride details with someone"
                )
            ]

        return timeline
