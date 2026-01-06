"""
Answer and Visualization Agent (Merged)
Combines answer generation and visualization planning into a single LLM call
to reduce latency while maintaining quality.
"""

import json
import logging

from langchain_core.prompts import ChatPromptTemplate

from ..config.settings import get_settings
from ..models.state import AgentState, QueryIntent, VisualizationConfig, VisualizationType
from ..utils.llm_factory import create_llm

logger = logging.getLogger(__name__)

# Combined prompt for answer generation and visualization planning
ANSWER_AND_VIZ_PROMPT = """Generate a natural language answer AND select visualization type for the query results.

=== PART 1: Answer Generation ===
User Question: {user_query}
SQL Query: {sql}
Query Results (first 20 rows): {results_sample}
Total Results: {result_count}
Columns: {columns}

Generate a concise, natural language answer that:
- Directly answers the user's question
- Highlights key findings or numbers
- Uses the actual values from the results EXACTLY as they appear
- **CRITICAL: Currency values are in DOLLARS, not thousands. Use exact values from results (e.g., $54.07, not $54.07K). Do NOT add "K" or assume values are in thousands.**
- Format currency as $X.XX (e.g., $54.07, $1,234.56) - use exact decimal values from results
- Is conversational and clear
- **IMPORTANT: If user asked about "yesterday", "today", "last week", etc., mention that the database only contains data from January 1-4, 2025, and provide results for the closest available date(s)**
- If results are empty, explain why (e.g., "No data found for the specified criteria")

=== PART 2: Visualization Planning ===
Query Intent: {intent}
Columns: {columns}
Rows: {result_count}

Chart types:
- line_chart: Time series, trends over time, multiple series
- bar_chart: Categories/locations/products, rankings, <=20 items (horizontal if long labels)
- pie_chart: Part-to-whole, <=8 categories, percentages
- stacked_bar: Category breakdown within groups
- table: >50 rows or >5 columns, exact values, multi-dimensional
- multi_series: Multiple metrics over time, location comparisons
- heatmap: Two categorical dimensions, time patterns (hour x day)

Return JSON only:
{{
    "answer": "Natural language answer to the user's question",
    "key_insights": ["insight1", "insight2"],
    "visualization_type": "bar_chart|line_chart|pie_chart|table|multi_series|heatmap|stacked_bar",
    "config": {{
        "x_axis": "column_name",
        "y_axis": "column_name",
        "title": "title",
        "format_type": "currency|number|percentage",
        "show_values": true
    }},
    "reasoning": "brief explanation for visualization choice"
}}

Keep the answer brief (2-4 sentences) and focused on answering the user's question.
"""


def answer_and_viz_agent(state: AgentState) -> AgentState:
    """
    Combined answer generation and visualization planning in a single LLM call.
    
    This merged agent reduces latency by combining two parallel operations
    into one, while maintaining the same quality and accuracy.
    """
    logger.info("Answer and visualization agent processing...")

    agent_trace = state.get("agent_trace", [])
    agent_trace.append("answer_and_viz")

    results = state.get("query_results", [])
    result_count = len(results)
    columns = list(results[0].keys()) if results else state.get("expected_columns", [])
    sql = state.get("generated_sql", "")
    user_query = state.get("user_query", "")

    # Sample results (first 5 rows for context - reduced for performance)
    # 20 rows was too much and added latency without significant quality improvement
    results_sample = results[:5] if results else []

    # Quick decision for obvious visualization cases (no LLM needed)
    if result_count == 0:
        state["generated_answer"] = (
            "No results found for your query. Please try different criteria or check if the data exists for the specified conditions."
        )
        state["key_insights"] = []
        state["visualization_type"] = VisualizationType.TABLE
        state["visualization_config"] = {"title": "No Results Found", "show_values": True}
        state["agent_trace"] = agent_trace
        return state

    if result_count == 1 and len(columns) <= 2:
        # Single value result - just show as table/card
        state["visualization_type"] = VisualizationType.TABLE
        state["visualization_config"] = {
            "title": user_query[:50] + "..." if len(user_query) > 50 else user_query,
            "show_values": True
        }
        # Still generate answer via LLM for single results
        # (fall through to LLM call)

    try:
        settings = get_settings()

        # Initialize LLM with parameters suitable for both tasks
        # NOTE: Reasoning disabled for performance - answer generation doesn't need reasoning
        llm = create_llm(
            temperature=0.3,  # Higher for more natural language in answers
            top_p=1,
            max_tokens=768,  # Increased for combined output
            reasoning_budget=None,  # Disabled for performance
            enable_thinking=False,  # Disabled for performance
        )

        prompt = ChatPromptTemplate.from_template(ANSWER_AND_VIZ_PROMPT)

        intent = state.get("query_intent", QueryIntent.UNKNOWN)

        chain = prompt | llm

        response = chain.invoke(
            {
                "user_query": user_query,
                "sql": sql,
                "results_sample": json.dumps(results_sample, default=str),
                "result_count": result_count,
                "columns": json.dumps(columns),
                "intent": intent.value if isinstance(intent, QueryIntent) else str(intent),
            }
        )

        # Parse response
        response_text = response.content.strip()

        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]

        result = json.loads(response_text)

        # === PART 1: Process Answer ===
        answer = result.get("answer", "Query executed successfully.")
        state["generated_answer"] = answer
        state["key_insights"] = result.get("key_insights", [])

        # === PART 2: Process Visualization ===
        # Map visualization type
        viz_type_str = result.get("visualization_type", "table")
        try:
            viz_type = VisualizationType(viz_type_str)
        except ValueError:
            viz_type = VisualizationType.TABLE

        # Parse config
        config_data = result.get("config", {})
        viz_config: VisualizationConfig = {
            "x_axis": config_data.get("x_axis", columns[0] if columns else ""),
            "y_axis": config_data.get("y_axis", columns[1] if len(columns) > 1 else ""),
            "title": config_data.get("title", "Query Results"),
            "format_type": config_data.get("format_type", "number"),
            "show_values": config_data.get("show_values", True),
            "colors": config_data.get("colors", ["#4f46e5", "#10b981", "#f59e0b", "#ef4444"]),
        }
        if config_data.get("subtitle"):
            viz_config["subtitle"] = config_data.get("subtitle")

        state["visualization_type"] = viz_type
        state["visualization_config"] = viz_config
        state["agent_trace"] = agent_trace

        logger.info(
            f"Answer generated: {len(answer)} chars | "
            f"Visualization planned: {viz_type.value}"
        )

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse answer and viz response: {e}")
        # Fallback: Generate simple answer and use fallback visualization
        if result_count == 0:
            state["generated_answer"] = (
                "No results found for your query. Please try different criteria or check if the data exists for the specified conditions."
            )
        else:
            state["generated_answer"] = (
                f"Query executed successfully. Found {result_count} result(s)."
            )
        state["key_insights"] = []
        state = _fallback_visualization(state, columns, result_count)
        state["agent_trace"] = agent_trace

    except Exception as e:
        logger.error(f"Answer and visualization agent error: {e}")
        # Fallback answer and visualization
        if result_count == 0:
            state["generated_answer"] = "No results found for your query."
        else:
            state["generated_answer"] = (
                f"Query executed successfully. Found {result_count} result(s)."
            )
        state["key_insights"] = []
        state = _fallback_visualization(state, columns, result_count)
        state["agent_trace"] = agent_trace

    return state


def _fallback_visualization(state: AgentState, columns: list[str], result_count: int) -> AgentState:
    """
    Fallback visualization selection based on heuristics.
    """
    intent = state.get("query_intent", QueryIntent.UNKNOWN)

    # Determine based on intent and data shape
    if intent == QueryIntent.TIME_SERIES:
        viz_type = VisualizationType.LINE_CHART
    elif intent == QueryIntent.PRODUCT_ANALYSIS:
        viz_type = VisualizationType.BAR_CHART if result_count <= 20 else VisualizationType.TABLE
    elif intent == QueryIntent.LOCATION_COMPARISON:
        viz_type = VisualizationType.BAR_CHART
    elif intent == QueryIntent.PAYMENT_ANALYSIS:
        viz_type = VisualizationType.PIE_CHART if result_count <= 8 else VisualizationType.BAR_CHART
    elif result_count > 50 or len(columns) > 5:
        viz_type = VisualizationType.TABLE
    elif result_count <= 10:
        viz_type = VisualizationType.BAR_CHART
    else:
        viz_type = VisualizationType.TABLE

    # Infer x and y axes
    x_axis = ""
    y_axis = ""

    for col in columns:
        col_lower = col.lower()
        if any(d in col_lower for d in ["date", "day", "week", "month", "hour"]):
            x_axis = col
        elif any(m in col_lower for m in ["name", "type", "code", "category"]):
            x_axis = col
        elif any(v in col_lower for v in ["revenue", "sales", "total", "count", "sum", "avg"]):
            y_axis = col

    if not x_axis and columns:
        x_axis = columns[0]
    if not y_axis and len(columns) > 1:
        y_axis = columns[1]

    state["visualization_type"] = viz_type
    state["visualization_config"] = {
        "x_axis": x_axis,
        "y_axis": y_axis,
        "title": "Query Results",
        "format_type": "number",
        "show_values": True,
    }

    return state

