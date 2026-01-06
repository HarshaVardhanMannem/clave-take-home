"""
FastAPI Application
Main entry point for the Restaurant Analytics Agent API
"""

import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from .config.settings import get_settings
from .config.schema_knowledge import SCHEMA_KNOWLEDGE
from .database import SupabasePool, init_database, close_database
from .agent_framework import get_agent_runner
from .agents.answer_and_viz_agent import answer_and_viz_agent
from .visualization import generate_chart_config
from .utils.formatters import format_results, get_result_columns

from .models.requests import QueryRequest
from .models.responses import (
    QueryResponse,
    ClarificationResponse,
    ErrorResponse,
    VisualizationResponse,
    SchemaResponse,
    ExamplesResponse,
    ExampleQuery,
    HealthResponse
)
from .models.state import QueryIntent, VisualizationType

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Global flag to track shutdown state
_shutdown_in_progress = False

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager - handles startup and shutdown"""
    global _shutdown_in_progress
    
    # Startup
    logger.info("Starting Restaurant Analytics Agent API...")
    _shutdown_in_progress = False
    
    try:
        # Initialize database connection pool
        await init_database()
        logger.info("Database connection pool initialized")
        
        # Initialize agent runner (preloads LLM config)
        get_agent_runner()
        logger.info("Agent runner initialized")
        
    except (KeyboardInterrupt, asyncio.CancelledError):
        # Gracefully handle cancellation during startup
        logger.info("Startup cancelled")
        raise
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise
    
    yield
    
    # Shutdown
    _shutdown_in_progress = True
    logger.info("Shutting down...")
    try:
        await close_database()
    except Exception as e:
        logger.error(f"Error during database shutdown: {e}")
    logger.info("Shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Restaurant Analytics Agent API",
    description="Natural Language to SQL agent for restaurant analytics",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
from .routes.auth import router as auth_router
app.include_router(auth_router)


# ==================== Main Query Endpoint ====================

@app.post("/api/query", response_model=None)
async def process_query(request: QueryRequest):
    """
    Process a natural language query about restaurant data.
    
    The agent will:
    1. Classify the intent and extract entities
    2. Analyze the schema to determine tables needed
    3. Generate a PostgreSQL query
    4. Validate the query for safety
    5. Execute on Supabase
    6. Plan appropriate visualization
    
    Returns either:
    - Query results with SQL and visualization config
    - Clarification request if query is ambiguous
    - Error response if query cannot be processed
    """
    query_id = str(uuid.uuid4())
    logger.info(f"[{query_id}] Processing query: {request.query[:100]}...")
    
    # Debug: Log request fields
    request_dict = request.model_dump() if hasattr(request, 'model_dump') else {}
    logger.info(f"[{query_id}] Request fields: {list(request_dict.keys())}, stream_answer: {request_dict.get('stream_answer', 'NOT_FOUND')}")
    
    try:
        # Get agent runner and process query
        runner = get_agent_runner()
        result = runner.process_query(
            query=request.query,
            conversation_history=request.context
        )
        
        # Check if clarification is needed
        if result.get("needs_clarification", False):
            logger.info(f"[{query_id}] Clarification needed")
            return ClarificationResponse(
                success=True,
                clarification_needed=True,
                question=result.get("clarification_question", "Could you please clarify your query?"),
                suggestions=_get_clarification_suggestions(result),
                original_query=request.query,
                detected_intent=result.get("query_intent")
            )
        
        # Check if SQL generation failed
        if not result.get("sql_validation_passed", False):
            logger.warning(f"[{query_id}] SQL validation failed")
            return ErrorResponse(
                success=False,
                error_code="SQL_GENERATION_FAILED",
                error_message="Failed to generate a valid SQL query",
                details={
                    "errors": result.get("sql_errors", []),
                    "generated_sql": result.get("generated_sql", ""),
                    "retries": result.get("retry_count", 0)
                },
                suggestions=[
                    "Try rephrasing your question",
                    "Be more specific about what data you want",
                    "Check example queries for guidance"
                ]
            )
        
        # Execute the SQL query
        sql = result.get("generated_sql", "")
        
        if not sql:
            logger.error(f"[{query_id}] No SQL generated")
            return ErrorResponse(
                success=False,
                error_code="NO_SQL_GENERATED",
                error_message="Failed to generate SQL query",
                details={"result": result}
            )
        
        # Check if shutdown is in progress (e.g., during uvicorn reload)
        if _shutdown_in_progress:
            logger.warning(f"[{query_id}] Shutdown in progress, aborting query execution")
            return ErrorResponse(
                success=False,
                error_code="SHUTDOWN_IN_PROGRESS",
                error_message="Server is shutting down. Please retry your query.",
                details={"sql": sql}
            )
        
        logger.debug(f"[{query_id}] Executing SQL: {sql[:200]}...")
        
        settings = get_settings()
        try:
            query_results, exec_time = await SupabasePool.execute_query(
                sql,
                timeout=settings.max_query_timeout
            )
        except asyncio.CancelledError:
            logger.warning(f"[{query_id}] Query execution cancelled (likely due to shutdown/reload)")
            return ErrorResponse(
                success=False,
                error_code="QUERY_CANCELLED",
                error_message="Query execution was cancelled. This may happen during server reload. Please retry.",
                details={"sql": sql}
            )
        except Exception as e:
            logger.error(f"[{query_id}] SQL execution failed: {e}")
            return ErrorResponse(
                success=False,
                error_code="SQL_EXECUTION_FAILED",
                error_message=f"Failed to execute query: {str(e)}",
                details={"sql": sql}
            )
        
        # Apply max results limit
        if request.max_results and len(query_results) > request.max_results:
            query_results = query_results[:request.max_results]
        
        # Format results
        formatted_results = format_results(query_results)
        columns = get_result_columns(query_results)
        
        # Update state with results for visualization and answer generation
        result["query_results"] = formatted_results
        result["result_count"] = len(formatted_results)
        result["expected_columns"] = columns
        result["execution_time_ms"] = exec_time
        
        # If streaming is requested, send results immediately
        # Use getattr as fallback in case model hasn't reloaded yet
        stream_answer = getattr(request, 'stream_answer', False)
        # Ensure it's a boolean (handle string "true"/"True")
        if isinstance(stream_answer, str):
            stream_answer = stream_answer.lower() in ('true', '1', 'yes')
        logger.info(f"[{query_id}] Stream answer requested: {stream_answer} (type: {type(stream_answer).__name__}), request fields: {list(request.model_fields.keys()) if hasattr(request, 'model_fields') else 'N/A'}")
        if stream_answer:
            logger.info(f"[{query_id}] ✅ Entering streaming path - will return StreamingResponse")
            import json
            
            async def generate_stream():
                try:
                    logger.info(f"[{query_id}] Streaming: Sending results immediately")
                    # Step 1: Send SQL results immediately after validation and execution
                    results_data = {
                        "type": "results",
                        "data": {
                            "query_id": query_id,
                            "intent": result.get("query_intent", QueryIntent.UNKNOWN).value,
                            "sql": sql,
                            "explanation": result.get("sql_explanation", ""),
                            "results": formatted_results,
                            "result_count": len(formatted_results),
                            "columns": columns,
                            "execution_time_ms": exec_time,
                        }
                    }
                    results_json = json.dumps(results_data)
                    logger.info(f"[{query_id}] Streaming: Yielding results event ({len(results_json)} bytes)")
                    yield f"data: {results_json}\n\n"
                    
                    # Step 2: Generate answer and stream chunks
                    answer_viz_state = dict(result)
                    answer_viz_state["agent_trace"] = list(result.get("agent_trace", []))
                    
                    # Generate answer (this may take time)
                    answer_viz_state = answer_and_viz_agent(answer_viz_state)
                    
                    generated_answer = answer_viz_state.get(
                        "generated_answer",
                        f"Query executed successfully. Found {len(formatted_results)} result(s)."
                    )
                    
                    # Stream answer chunks if it's a long answer
                    logger.info(f"[{query_id}] Streaming: Sending answer ({len(generated_answer)} chars)")
                    if len(generated_answer) > 100:
                        chunk_size = 50
                        for i in range(0, len(generated_answer), chunk_size):
                            chunk = generated_answer[i:i + chunk_size]
                            chunk_data = {
                                "type": "answer_chunk",
                                "chunk": chunk
                            }
                            yield f"data: {json.dumps(chunk_data)}\n\n"
                    else:
                        # Send full answer if short
                        chunk_data = {
                            "type": "answer_chunk",
                            "chunk": generated_answer
                        }
                        yield f"data: {json.dumps(chunk_data)}\n\n"
                    
                    # Step 3: Generate and send visualization
                    viz_response = None
                    if request.include_chart:
                        viz_type = answer_viz_state.get("visualization_type", VisualizationType.TABLE)
                        viz_config = answer_viz_state.get("visualization_config", {})
                        
                        logger.info(
                            f"[{query_id}] Visualization type selected: {viz_type.value if hasattr(viz_type, 'value') else viz_type}"
                        )
                        
                        # Update config with better defaults based on actual results
                        if viz_config:
                            default_titles = ["No Results", "No Results Found", "Result", "Query Results"]
                            if not viz_config.get("title") or viz_config.get("title") in default_titles:
                                viz_config["title"] = (
                                    request.query[:60] + "..." if len(request.query) > 60 else request.query
                                )
                            
                            if columns and not viz_config.get("x_axis"):
                                viz_config["x_axis"] = columns[0]
                            if len(columns) > 1 and not viz_config.get("y_axis"):
                                viz_config["y_axis"] = columns[1]
                        
                        try:
                            chart_config = generate_chart_config(formatted_results, viz_type, viz_config)
                            logger.info(
                                f"[{query_id}] Chart config generated: type={viz_type.value if hasattr(viz_type, 'value') else viz_type}, has_config={'data' in chart_config if chart_config else False}"
                            )
                        except Exception as e:
                            logger.error(f"[{query_id}] Error generating chart config: {e}", exc_info=True)
                            chart_config = {
                                "type": "table",
                                "data": {"columns": columns, "rows": formatted_results},
                                "options": {"title": viz_config.get("title", "Query Results")},
                            }
                            viz_type = VisualizationType.TABLE
                        
                        viz_response = VisualizationResponse(
                            type=viz_type,
                            config=dict(viz_config) if viz_config else {},
                            chart_js_config=chart_config,
                        )
                    else:
                        viz_response = VisualizationResponse(type=VisualizationType.TABLE, config={})
                    
                    # Send visualization
                    logger.info(f"[{query_id}] Streaming: Sending visualization")
                    viz_data = {
                        "type": "visualization",
                        "data": {
                            "type": viz_response.type.value if hasattr(viz_response.type, 'value') else str(viz_response.type),
                            "config": viz_response.config,
                            "chart_js_config": viz_response.chart_js_config,
                        }
                    }
                    yield f"data: {json.dumps(viz_data)}\n\n"
                    
                    # Step 4: Send complete response with all data
                    complete_response = QueryResponse(
                        success=True,
                        query_id=query_id,
                        intent=result.get("query_intent", QueryIntent.UNKNOWN),
                        sql=sql,
                        explanation=result.get("sql_explanation", ""),
                        results=formatted_results,
                        result_count=len(formatted_results),
                        columns=columns,
                        visualization=viz_response,
                        execution_time_ms=exec_time,
                        total_processing_time_ms=result.get("total_processing_time_ms", 0),
                        answer=generated_answer
                    )
                    
                    logger.info(f"[{query_id}] Streaming: Sending complete event")
                    complete_data = {
                        "type": "complete",
                        "response": complete_response.model_dump()
                    }
                    yield f"data: {json.dumps(complete_data)}\n\n"
                    logger.info(f"[{query_id}] Streaming: Stream complete")
                except Exception as e:
                    logger.error(f"[{query_id}] Error in streaming generator: {e}", exc_info=True)
                    error_data = {
                        "type": "error",
                        "error": str(e)
                    }
                    yield f"data: {json.dumps(error_data)}\n\n"
            
            logger.info(f"[{query_id}] ✅ Returning StreamingResponse with text/event-stream")
            return StreamingResponse(
                generate_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no"
                }
            )
        
        # Non-streaming path (original behavior)
        logger.info(f"[{query_id}] ⚠️ Using non-streaming path (stream_answer was False or not set)")
        # Generate answer and visualization in one merged call (after SQL execution with actual results)
        answer_viz_state = dict(result)
        answer_viz_state["agent_trace"] = list(result.get("agent_trace", []))
        
        # Always use merged agent - it handles both answer and visualization
        # If include_chart is False, we'll just ignore the visualization part
        answer_viz_state = answer_and_viz_agent(answer_viz_state)
        
        # Get generated answer
        generated_answer = answer_viz_state.get(
            "generated_answer",
            f"Query executed successfully. Found {len(formatted_results)} result(s)."
        )
        
        # Process visualization results
        viz_response = None
        if request.include_chart:
            viz_type = answer_viz_state.get("visualization_type", VisualizationType.TABLE)
            viz_config = answer_viz_state.get("visualization_config", {})
            
            logger.info(
                f"[{query_id}] Visualization type selected: {viz_type.value if hasattr(viz_type, 'value') else viz_type}"
            )
            
            # Update config with better defaults based on actual results
            if viz_config:
                # Set title from query if not set or if it's a default
                default_titles = ["No Results", "No Results Found", "Result", "Query Results"]
                if not viz_config.get("title") or viz_config.get("title") in default_titles:
                    viz_config["title"] = (
                        request.query[:60] + "..." if len(request.query) > 60 else request.query
                    )
                
                # Auto-detect axes from columns if not set
                if columns and not viz_config.get("x_axis"):
                    viz_config["x_axis"] = columns[0]
                if len(columns) > 1 and not viz_config.get("y_axis"):
                    viz_config["y_axis"] = columns[1]
            
            try:
                chart_config = generate_chart_config(formatted_results, viz_type, viz_config)
                logger.info(
                    f"[{query_id}] Chart config generated: type={viz_type.value if hasattr(viz_type, 'value') else viz_type}, has_config={'data' in chart_config if chart_config else False}"
                )
            except Exception as e:
                logger.error(f"[{query_id}] Error generating chart config: {e}", exc_info=True)
                # Fallback to table visualization on error
                chart_config = {
                    "type": "table",
                    "data": {"columns": columns, "rows": formatted_results},
                    "options": {"title": viz_config.get("title", "Query Results")},
                }
                viz_type = VisualizationType.TABLE
            
            viz_response = VisualizationResponse(
                type=viz_type,
                config=dict(viz_config) if viz_config else {},
                chart_js_config=chart_config,
            )
        else:
            viz_response = VisualizationResponse(type=VisualizationType.TABLE, config={})
        
        logger.info(
            f"[{query_id}] Query successful: {len(formatted_results)} rows "
            f"in {exec_time:.2f}ms"
        )
        
        return QueryResponse(
            success=True,
            query_id=query_id,
            intent=result.get("query_intent", QueryIntent.UNKNOWN),
            sql=sql,
            explanation=result.get("sql_explanation", ""),
            results=formatted_results,
            result_count=len(formatted_results),
            columns=columns,
            visualization=viz_response,
            execution_time_ms=exec_time,
            total_processing_time_ms=result.get("total_processing_time_ms", 0),
            answer=generated_answer
        )
        
    except TimeoutError as e:
        logger.error(f"[{query_id}] Query timeout: {e}")
        return ErrorResponse(
            success=False,
            error_code="QUERY_TIMEOUT",
            error_message=str(e),
            suggestions=["Try a simpler query", "Add more specific filters"]
        )
        
    except Exception as e:
        logger.exception(f"[{query_id}] Unexpected error: {e}")
        return ErrorResponse(
            success=False,
            error_code="INTERNAL_ERROR",
            error_message="An unexpected error occurred",
            details={"error": str(e)},
            suggestions=["Please try again", "Contact support if the issue persists"]
        )


def _get_clarification_suggestions(result: dict) -> list:
    """Generate clarification suggestions based on detected context"""
    suggestions = []
    
    intent = result.get("query_intent")
    if intent == QueryIntent.SALES_ANALYSIS:
        suggestions.extend([
            "What time period are you interested in?",
            "Which location do you want to analyze?",
            "Do you want total sales or a breakdown?"
        ])
    elif intent == QueryIntent.PRODUCT_ANALYSIS:
        suggestions.extend([
            "Top selling by quantity or revenue?",
            "For a specific time period?",
            "For a specific category?"
        ])
    
    return suggestions[:3]


# ==================== Schema & Examples Endpoints ====================

@app.get("/api/schema", response_model=SchemaResponse)
async def get_schema():
    """
    Get schema information for the restaurant database.
    Useful for understanding available tables and columns.
    """
    tables = {}
    views = {}
    
    for name, info in SCHEMA_KNOWLEDGE["tables"].items():
        if info.get("type") == "view":
            views[name] = info
        else:
            tables[name] = info
    
    return SchemaResponse(
        tables=tables,
        views=views,
        important_rules=SCHEMA_KNOWLEDGE.get("important_rules", [])
    )


@app.get("/api/examples", response_model=ExamplesResponse)
async def get_examples():
    """
    Get example natural language queries.
    Useful for understanding what kinds of questions can be asked.
    """
    # Note: Database contains data from Jan 1-4, 2025 only
    examples = [
        ExampleQuery(
            query="What were total sales on January 2nd?",
            intent=QueryIntent.SALES_ANALYSIS,
            description="Get aggregate sales for a specific day"
        ),
        ExampleQuery(
            query="Show me the top 10 selling products",
            intent=QueryIntent.PRODUCT_ANALYSIS,
            description="Product ranking by sales volume"
        ),
        ExampleQuery(
            query="Compare revenue across all locations",
            intent=QueryIntent.LOCATION_COMPARISON,
            description="Location-wise revenue comparison"
        ),
        ExampleQuery(
            query="What are our busiest hours?",
            intent=QueryIntent.TIME_SERIES,
            description="Time-of-day analysis for staffing"
        ),
        ExampleQuery(
            query="Payment method breakdown",
            intent=QueryIntent.PAYMENT_ANALYSIS,
            description="Analyze payment type distribution"
        ),
        ExampleQuery(
            query="Daily revenue trend from Jan 1-4, 2025",
            intent=QueryIntent.TIME_SERIES,
            description="Revenue trend over available dates"
        ),
        ExampleQuery(
            query="Compare dine-in vs delivery vs takeout sales",
            intent=QueryIntent.ORDER_TYPE_ANALYSIS,
            description="Order type comparison"
        ),
        ExampleQuery(
            query="Which categories generate the most revenue?",
            intent=QueryIntent.CATEGORY_ANALYSIS,
            description="Category-level revenue analysis"
        ),
        ExampleQuery(
            query="Average order value by location",
            intent=QueryIntent.PERFORMANCE_METRICS,
            description="Calculate KPIs by location"
        ),
        ExampleQuery(
            query="Toast vs DoorDash revenue comparison",
            intent=QueryIntent.SOURCE_COMPARISON,
            description="Compare data sources"
        )
    ]
    
    return ExamplesResponse(examples=examples)


# ==================== Health & Status Endpoints ====================

@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    db_healthy = await SupabasePool.check_health()
    
    return HealthResponse(
        status="healthy" if db_healthy else "degraded",
        database_connected=db_healthy,
        version="1.0.0"
    )


@app.get("/api/stats")
async def get_stats():
    """Get API statistics"""
    pool_stats = await SupabasePool.get_pool_stats()
    
    return {
        "database": pool_stats,
        "agent": {
            "status": "ready"
        }
    }


# ==================== Utility Endpoints ====================

@app.post("/api/validate-sql")
async def validate_sql(sql: str = Query(..., description="SQL to validate")):
    """
    Validate a SQL query without executing it.
    Useful for testing queries before running them.
    """
    from .utils.validators import SQLValidator
    
    result = SQLValidator.validate(sql)
    
    return {
        "valid": result.is_valid,
        "errors": result.errors,
        "warnings": result.warnings
    }


@app.post("/api/explain")
async def explain_query(request: QueryRequest):
    """
    Get an explanation of what SQL would be generated for a query,
    without actually executing it.
    """
    runner = get_agent_runner()
    result = runner.process_query(
        query=request.query,
        conversation_history=request.context
    )
    
    return {
        "intent": result.get("query_intent", QueryIntent.UNKNOWN).value,
        "entities": result.get("entities_extracted", {}),
        "time_range": result.get("time_range", {}),
        "tables": result.get("relevant_tables", []),
        "sql": result.get("generated_sql", ""),
        "explanation": result.get("sql_explanation", ""),
        "visualization_type": result.get("visualization_type", VisualizationType.TABLE).value,
        "validation_passed": result.get("sql_validation_passed", False),
        "errors": result.get("sql_errors", []),
        "warnings": result.get("sql_warnings", [])
    }


# ==================== Error Handlers ====================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error_code": f"HTTP_{exc.status_code}",
            "error_message": exc.detail
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error_code": "INTERNAL_ERROR",
            "error_message": "An unexpected error occurred"
        }
    )


# ==================== Run Configuration ====================

if __name__ == "__main__":
    import uvicorn
    
    settings = get_settings()
    
    uvicorn.run(
        "backend.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
        log_level=settings.log_level.lower()
    )

