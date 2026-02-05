"""
Planner Agent: Analyzes user requests and creates structured execution plans.
Uses Google Gemini (FREE - no card required) for LLM reasoning.
"""
import json
from typing import Dict, Any
import google.generativeai as genai
from utils.helpers import get_env_variable, get_logger, generate_plan_id, parse_date_time, calculate_price_bracket, extract_city_coordinates
from utils.schemas import PlannerOutput, PlanStep

logger = get_logger("PlannerAgent")


class PlannerAgent:
    """
    Planner Agent: Converts user requests into structured execution plans.

    Uses Google Gemini (FREE!) instead of OpenAI.

    Responsibilities:
    - Parse user intent (city, budget, preferences, timing)
    - Determine required steps (weather check, venue search, events, etc.)
    - Generate structured plan with parameters for each step
    - Identify safety considerations
    """

    def __init__(self):
        api_key = get_env_variable("GEMINI_API_KEY", required=True)
        genai.configure(api_key=api_key)

        # Use Gemini 1.5 Flash (fastest free model)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        self.temperature = 0

    def plan(self, user_request: Dict[str, Any]) -> PlannerOutput:
        """
        Create a structured plan from user request.

        Args:
            user_request: Dictionary with keys:
                - city: str
                - budget_per_person: float (optional)
                - date_time: str
                - preferences: str (optional)
                - dietary_restrictions: list (optional)
                - accessibility_needs: str (optional)

        Returns:
            PlannerOutput with structured plan
        """
        logger.info(f"[Planner] Analyzing request for {user_request.get('city')}")

        # Generate plan ID
        plan_id = generate_plan_id()

        # Extract and enrich request data
        city = user_request.get("city", "")
        budget = user_request.get("budget_per_person")
        date_time = user_request.get("date_time", "")
        preferences = user_request.get("preferences", "")
        dietary = user_request.get("dietary_restrictions", [])
        accessibility = user_request.get("accessibility_needs", "")

        # Get city coordinates
        city_coords = extract_city_coordinates(city)
        lat, lon = city_coords["lat"], city_coords["lon"]

        # Parse date/time
        parsed_time = parse_date_time(date_time)

        # Calculate price bracket
        price_level = calculate_price_bracket(budget)

        # Build prompt for LLM
        prompt = self._build_prompt(
            city=city,
            latitude=lat,
            longitude=lon,
            budget=budget,
            price_level=price_level,
            date_time=date_time,
            parsed_time=parsed_time,
            preferences=preferences,
            dietary=dietary,
            accessibility=accessibility
        )

        # Call Gemini
        logger.info("[Planner] Calling Gemini to generate plan...")
        try:
            # Generate content with Gemini (no response_mime_type for Python 3.9 compatibility)
            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=self.temperature
                )
            )

            # Parse response - extract JSON from markdown if needed
            response_text = response.text.strip()

            # Remove markdown code blocks if present
            if response_text.startswith("```json"):
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif response_text.startswith("```"):
                response_text = response_text.split("```")[1].split("```")[0].strip()

            plan_data = json.loads(response_text)

            # Construct PlannerOutput
            planner_output = PlannerOutput(
                plan_id=plan_id,
                user_intent=plan_data.get("user_intent", f"Plan a date in {city}"),
                steps=[PlanStep(**step) for step in plan_data.get("steps", [])],
                estimated_budget=plan_data.get("estimated_budget", budget),
                safety_notes=plan_data.get("safety_notes", [])
            )

            logger.info(f"[Planner] ✓ Generated plan with {len(planner_output.steps)} steps")
            return planner_output

        except Exception as e:
            logger.error(f"[Planner] Error generating plan: {str(e)}")
            # Fallback to basic plan
            return self._create_fallback_plan(plan_id, city, lat, lon, budget, preferences)

    def _build_prompt(
        self,
        city: str,
        latitude: float,
        longitude: float,
        budget: float,
        price_level: int,
        date_time: str,
        parsed_time: dict,
        preferences: str,
        dietary: list,
        accessibility: str
    ) -> str:
        """Build prompt for LLM to generate structured plan"""

        dietary_str = ", ".join(dietary) if dietary else "none specified"

        prompt = f"""You are planning a date. Analyze the request and create a structured execution plan.

**User Request:**
- City: {city}
- Coordinates: {latitude}, {longitude}
- Budget per person: ₹{budget if budget else 'flexible'}
- Price level: {price_level}/4
- Date/Time: {date_time} ({parsed_time})
- Preferences: {preferences or 'casual, nice ambience'}
- Dietary restrictions: {dietary_str}
- Accessibility needs: {accessibility or 'none'}

**Your Task:**
Create a JSON plan with these exact keys:

1. "user_intent": A one-line summary of what the user wants
2. "steps": An array of step objects, each with:
   - "id": unique identifier (e.g., "step_1", "step_2")
   - "action": MUST be one of: "get_weather", "search_venues", "check_events", "get_images", "compose_final"
   - "params": object with action-specific parameters
   - "reasoning": why this step is needed

3. "estimated_budget": total estimated cost (float)
4. "safety_notes": array of safety considerations (strings)

**Action Parameter Requirements:**

- **get_weather**:
  {{"latitude": {latitude}, "longitude": {longitude}, "target_datetime": null}}

- **search_venues**:
  {{"query": "include cuisine/preferences", "latitude": {latitude}, "longitude": {longitude}, "radius": 3000, "venue_type": "restaurant", "max_results": 5}}

- **check_events** (optional):
  {{"city": "{city}", "date": "{date_time}", "keywords": "relevant keywords"}}

- **get_images**:
  {{"query": "describe scene/ambience", "count": 3}}

- **compose_final**:
  {{"include_timeline": true, "include_backup_plan": true}}

**Rules:**
- Always include: get_weather, search_venues, get_images, compose_final
- search_venues should incorporate dietary restrictions and preferences in the query
- Provide 2-3 venue search steps with different queries if budget allows
- Consider accessibility needs in venue search queries
- Safety notes should address public venues, timing, and transportation

**Return ONLY valid JSON, no additional text:**

{{
  "user_intent": "...",
  "steps": [...],
  "estimated_budget": {budget if budget else 1500},
  "safety_notes": [...]
}}
"""
        return prompt

    def _create_fallback_plan(
        self,
        plan_id: str,
        city: str,
        lat: float,
        lon: float,
        budget: float,
        preferences: str
    ) -> PlannerOutput:
        """Create a basic fallback plan if LLM fails"""
        logger.warning("[Planner] Using fallback plan")

        steps = [
            PlanStep(
                id="step_1",
                action="get_weather",
                params={"latitude": lat, "longitude": lon, "target_datetime": None},
                reasoning="Check weather conditions for the date"
            ),
            PlanStep(
                id="step_2",
                action="search_venues",
                params={
                    "query": f"{preferences} restaurant" if preferences else "restaurant",
                    "latitude": lat,
                    "longitude": lon,
                    "radius": 3000,
                    "venue_type": "restaurant",
                    "max_results": 5
                },
                reasoning="Find suitable dining venues"
            ),
            PlanStep(
                id="step_3",
                action="get_images",
                params={"query": "romantic restaurant dinner", "count": 3},
                reasoning="Get inspirational images"
            ),
            PlanStep(
                id="step_4",
                action="compose_final",
                params={"include_timeline": True, "include_backup_plan": True},
                reasoning="Compose final date plan"
            )
        ]

        return PlannerOutput(
            plan_id=plan_id,
            user_intent=f"Plan a date in {city}",
            steps=steps,
            estimated_budget=budget,
            safety_notes=[
                "Choose a public, well-lit venue",
                "Share location with a trusted friend",
                "Arrange your own transportation"
            ]
        )
