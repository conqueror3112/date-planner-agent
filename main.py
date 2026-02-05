"""
FastAPI main application for Date-Planner Agent.
Run with: uvicorn main:app --reload
"""
import time
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from agents import PlannerAgent, ExecutorAgent, VerifierAgent
from utils.schemas import DatePlanRequest, DatePlanResponse
from utils.helpers import get_logger

# Initialize logger
logger = get_logger("MainApp")

# Create FastAPI app
app = FastAPI(
    title="Date-Planner Agent",
    description="Multi-agent GenAI system for planning dates using real-time APIs",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize agents
planner = PlannerAgent()
executor = ExecutorAgent()
verifier = VerifierAgent()


@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Date-Planner Agent API",
        "version": "1.0.0",
        "endpoints": {
            "POST /plan": "Create a date plan",
            "GET /health": "Health check"
        },
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "agents": {
            "planner": "active",
            "executor": "active",
            "verifier": "active"
        }
    }


@app.post("/plan", response_model=DatePlanResponse)
async def create_date_plan(request: DatePlanRequest):
    """
    Create a complete date plan based on user requirements.

    This endpoint orchestrates the multi-agent workflow:
    1. Planner analyzes request and creates execution plan
    2. Executor calls APIs to gather data
    3. Verifier validates results and composes final plan
    4. If issues found, may retry with adjusted parameters

    Args:
        request: DatePlanRequest with city, budget, preferences, etc.

    Returns:
        DatePlanResponse with complete date plan or error details
    """
    logger.info(f"[API] Received date plan request for {request.city}")
    start_time = time.time()

    try:
        # Convert request to dict for agents
        user_request = request.model_dump()

        # ============================================================
        # STEP 1: PLANNER - Create structured plan
        # ============================================================
        logger.info("[API] Step 1: Planner creating execution plan...")
        plan = planner.plan(user_request)

        if not plan or len(plan.steps) == 0:
            raise HTTPException(
                status_code=500,
                detail="Planner failed to create a valid plan"
            )

        logger.info(f"[API] ✓ Plan created with {len(plan.steps)} steps")

        # ============================================================
        # STEP 2: EXECUTOR - Execute plan steps
        # ============================================================
        logger.info("[API] Step 2: Executor executing plan steps...")
        executor_output = executor.execute(plan)

        logger.info(f"[API] ✓ Execution complete: {executor_output.overall_status}")

        # ============================================================
        # STEP 3: VERIFIER - Validate and compose final plan
        # ============================================================
        logger.info("[API] Step 3: Verifier validating results...")
        verifier_output = verifier.verify(plan, executor_output, user_request)

        # ============================================================
        # STEP 4: RETRY LOGIC (if needed)
        # ============================================================
        max_retries = 1
        retry_count = 0

        while not verifier_output.approved and retry_count < max_retries:
            retry_count += 1
            logger.warning(f"[API] Plan not approved, attempting retry {retry_count}/{max_retries}")

            if verifier_output.retry_recommendations:
                logger.info(f"[API] Retry recommendations: {verifier_output.retry_recommendations}")

            # Retry execution (in production, could adjust parameters)
            executor_output = executor.execute(plan)
            verifier_output = verifier.verify(plan, executor_output, user_request)

        # ============================================================
        # STEP 5: Return response
        # ============================================================
        processing_time = time.time() - start_time

        if verifier_output.approved and verifier_output.final_output:
            logger.info(f"[API] ✓ Date plan created successfully in {processing_time:.2f}s")
            return DatePlanResponse(
                success=True,
                plan_id=plan.plan_id,
                message="Date plan created successfully!",
                plan=verifier_output.final_output,
                processing_time_seconds=round(processing_time, 2)
            )
        else:
            # Plan not approved even after retries
            error_messages = [issue.message for issue in verifier_output.issues if issue.severity == "critical"]
            logger.error(f"[API] ✗ Failed to create approved plan: {error_messages}")

            return DatePlanResponse(
                success=False,
                plan_id=plan.plan_id,
                message="Could not create a suitable date plan",
                errors=error_messages or ["Unable to find suitable venues or data"],
                processing_time_seconds=round(processing_time, 2)
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API] Unexpected error: {str(e)}", exc_info=True)
        processing_time = time.time() - start_time

        return DatePlanResponse(
            success=False,
            plan_id="error",
            message="Internal server error",
            errors=[str(e)],
            processing_time_seconds=round(processing_time, 2)
        )


if __name__ == "__main__":
    import uvicorn

    logger.info("Starting Date-Planner Agent API...")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
