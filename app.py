"""
Streamlit UI for Date-Planner Agent.
Run with: streamlit run app.py
"""
import streamlit as st
import requests
import json
from datetime import datetime

# Page config
st.set_page_config(
    page_title="Date-Planner Agent",
    page_icon="💕",
    layout="wide"
)

# Title
st.title("💕 Date-Planner Agent")
st.markdown("**AI-powered date planning using real-time APIs**")
st.markdown("---")

# Sidebar for configuration
with st.sidebar:
    st.header("⚙️ Configuration")
    api_url = st.text_input(
        "API URL",
        value="http://localhost:8000",
        help="FastAPI backend URL"
    )
    st.markdown("---")
    st.markdown("### About")
    st.markdown("""
    This multi-agent system uses:
    - **Planner Agent**: Creates execution plan
    - **Executor Agent**: Calls real APIs
    - **Verifier Agent**: Validates results

    **APIs integrated:**
    - Google Places (venues)
    - OpenWeather (weather)
    - Unsplash (images)
    """)

# Main form
st.header("📝 Plan Your Date")

col1, col2 = st.columns(2)

with col1:
    city = st.text_input(
        "City *",
        value="Mumbai",
        help="City where you want to plan the date"
    )

    budget = st.number_input(
        "Budget per person (₹)",
        min_value=0,
        max_value=10000,
        value=1500,
        step=100,
        help="Optional: Budget per person in INR"
    )

    date_time = st.text_input(
        "Date & Time *",
        value="Saturday 7pm",
        help="e.g., 'Saturday 7pm' or '2024-02-10 19:00'"
    )

with col2:
    preferences = st.text_area(
        "Preferences",
        value="vegetarian, romantic, outdoor seating preferred",
        help="Cuisine type, ambience, special requirements"
    )

    dietary_restrictions = st.multiselect(
        "Dietary Restrictions",
        options=["Vegetarian", "Vegan", "Gluten-Free", "Halal", "Jain", "None"],
        default=["Vegetarian"]
    )

    accessibility_needs = st.text_input(
        "Accessibility Needs",
        value="",
        help="e.g., 'wheelchair accessible'"
    )

# Submit button
if st.button("🚀 Create Date Plan", type="primary"):
    if not city or not date_time:
        st.error("Please fill in required fields (City and Date & Time)")
    else:
        # Prepare request
        request_data = {
            "city": city,
            "budget_per_person": budget if budget > 0 else None,
            "date_time": date_time,
            "preferences": preferences,
            "dietary_restrictions": [d.lower() for d in dietary_restrictions if d != "None"],
            "accessibility_needs": accessibility_needs if accessibility_needs else None
        }

        # Show loading
        with st.spinner("🤖 AI agents working on your date plan..."):
            try:
                # Call API
                response = requests.post(
                    f"{api_url}/plan",
                    json=request_data,
                    timeout=60
                )

                if response.status_code == 200:
                    result = response.json()

                    if result["success"]:
                        st.success(f"✅ {result['message']} (Processing time: {result['processing_time_seconds']}s)")

                        plan = result["plan"]

                        # Display plan
                        st.markdown("---")
                        st.header(f"🎉 {plan['title']}")
                        st.markdown(f"**{plan['summary']}**")

                        st.markdown(f"📅 **Date & Time:** {plan['date_time']}")
                        st.markdown(f"📍 **City:** {plan['city']}")
                        st.markdown(f"💰 **Total Budget Estimate:** {plan['total_budget_estimate']}")

                        # Weather
                        if plan.get("weather_forecast"):
                            st.markdown("---")
                            st.subheader("🌤️ Weather Forecast")
                            weather = plan["weather_forecast"]
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("Temperature", f"{weather['temperature']}°C")
                            with col2:
                                st.metric("Condition", weather['condition'])
                            with col3:
                                st.metric("Humidity", f"{weather['humidity']}%")
                            st.info(f"💡 {weather['suggestion']}")

                        # Venues
                        st.markdown("---")
                        st.subheader("🍽️ Recommended Venues")

                        for idx, venue in enumerate(plan["venues"], 1):
                            with st.expander(f"{idx}. {venue['name']} {'⭐' * min(int(venue.get('rating', 0)), 5)}"):
                                col1, col2 = st.columns([2, 1])

                                with col1:
                                    st.markdown(f"**Address:** {venue['address']}")
                                    if venue.get('rating'):
                                        st.markdown(f"**Rating:** {venue['rating']} ⭐")
                                    if venue.get('price_level'):
                                        st.markdown(f"**Price Level:** {'₹' * venue['price_level']}")
                                    if venue.get('cuisine_type'):
                                        st.markdown(f"**Cuisine:** {venue['cuisine_type']}")
                                    if venue.get('phone'):
                                        st.markdown(f"**Phone:** {venue['phone']}")
                                    if venue.get('website'):
                                        st.markdown(f"[🌐 Website]({venue['website']})")
                                    if venue.get('google_maps_url'):
                                        st.markdown(f"[📍 View on Google Maps]({venue['google_maps_url']})")

                                with col2:
                                    if venue.get('open_now') is not None:
                                        status = "🟢 Open Now" if venue['open_now'] else "🔴 Closed"
                                        st.markdown(f"**Status:** {status}")
                                    if venue.get('wheelchair_accessible') is not None:
                                        accessible = "♿ Accessible" if venue['wheelchair_accessible'] else "Not confirmed"
                                        st.markdown(f"**Accessibility:** {accessible}")

                        # Timeline
                        if plan.get("timeline"):
                            st.markdown("---")
                            st.subheader("⏰ Suggested Timeline")
                            for item in plan["timeline"]:
                                st.markdown(f"**{item['time']}** - {item['activity']}")
                                if item.get('notes'):
                                    st.caption(f"   💡 {item['notes']}")

                        # Safety Checklist
                        if plan.get("safety_checklist"):
                            st.markdown("---")
                            st.subheader("🛡️ Safety Checklist")
                            for item in plan["safety_checklist"]:
                                st.markdown(f"- {item}")

                        # Transportation
                        if plan.get("transportation_suggestions"):
                            st.markdown("---")
                            st.subheader("🚗 Transportation Suggestions")
                            for item in plan["transportation_suggestions"]:
                                st.markdown(f"- {item}")

                        # Backup Plan
                        if plan.get("backup_plan"):
                            st.markdown("---")
                            st.warning(f"⚠️ **Backup Plan:** {plan['backup_plan']}")

                        # Images
                        if plan.get("venue_images"):
                            st.markdown("---")
                            st.subheader("📸 Venue Inspiration")
                            cols = st.columns(len(plan["venue_images"]))
                            for idx, img in enumerate(plan["venue_images"]):
                                with cols[idx]:
                                    st.image(img["url"], caption=f"Photo by {img['photographer']}")

                        # Debug info (collapsible)
                        with st.expander("🔍 Debug Info"):
                            st.json(result)

                    else:
                        st.error(f"❌ {result['message']}")
                        if result.get("errors"):
                            for error in result["errors"]:
                                st.error(f"- {error}")

                else:
                    st.error(f"API Error: {response.status_code} - {response.text}")

            except requests.exceptions.Timeout:
                st.error("⏱️ Request timed out. The API might be taking too long to respond.")
            except requests.exceptions.ConnectionError:
                st.error(f"🔌 Cannot connect to API at {api_url}. Make sure the FastAPI server is running.")
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")

# Example prompts
st.markdown("---")
st.subheader("💡 Example Prompts to Try")

examples = [
    {
        "city": "Pune",
        "budget": 800,
        "date_time": "Saturday 7pm",
        "preferences": "vegetarian, outdoor seating, casual",
        "dietary": ["Vegetarian"]
    },
    {
        "city": "Bangalore",
        "budget": 2500,
        "date_time": "Sunday afternoon",
        "preferences": "fancy date, romantic, fine dining",
        "dietary": []
    },
    {
        "city": "Mumbai",
        "budget": 1000,
        "date_time": "Friday evening",
        "preferences": "coffee date, quiet place, cozy",
        "dietary": ["Vegan"]
    }
]

cols = st.columns(len(examples))
for idx, example in enumerate(examples):
    with cols[idx]:
        st.code(f"""City: {example['city']}
Budget: ₹{example['budget']}
Time: {example['date_time']}
Preferences: {example['preferences']}""", language="text")
