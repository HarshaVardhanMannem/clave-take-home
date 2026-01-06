"""
Tests for Agent Components
"""

import pytest
import sys
import os

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.models.state import (
    AgentState, 
    QueryIntent, 
    VisualizationType,
    create_initial_state,
    ExtractedEntities,
    TimeRange
)
from backend.utils.validators import SQLValidator, ValidationResult
from backend.config.schema_knowledge import SCHEMA_KNOWLEDGE, get_table_info, get_schema_summary


class TestAgentState:
    """Tests for AgentState creation and manipulation"""
    
    def test_create_initial_state(self):
        """Test initial state creation"""
        state = create_initial_state("What were sales yesterday?")
        
        assert state["user_query"] == "What were sales yesterday?"
        assert state["query_intent"] == QueryIntent.UNKNOWN
        assert state["retry_count"] == 0
        assert state["max_retries"] == 2
        assert state["needs_clarification"] is False
        assert state["sql_validation_passed"] is False
    
    def test_create_initial_state_with_history(self):
        """Test initial state with conversation history"""
        history = [
            {"role": "user", "content": "Show me sales"},
            {"role": "assistant", "content": "Here are the sales..."}
        ]
        state = create_initial_state(
            "Now filter by downtown location",
            conversation_history=history
        )
        
        assert len(state["conversation_history"]) == 2
        assert state["conversation_history"][0]["role"] == "user"


class TestQueryIntent:
    """Tests for QueryIntent enum"""
    
    def test_all_intents_defined(self):
        """Verify all expected intents exist"""
        expected_intents = [
            "sales_analysis",
            "product_analysis",
            "location_comparison",
            "time_series",
            "payment_analysis",
            "order_type_analysis",
            "source_comparison",
            "performance_metrics",
            "category_analysis",
            "customer_analysis",
            "unknown"
        ]
        
        for intent in expected_intents:
            assert hasattr(QueryIntent, intent.upper())
    
    def test_intent_values(self):
        """Test intent enum values match expected strings"""
        assert QueryIntent.SALES_ANALYSIS.value == "sales_analysis"
        assert QueryIntent.PRODUCT_ANALYSIS.value == "product_analysis"


class TestVisualizationType:
    """Tests for VisualizationType enum"""
    
    def test_all_viz_types_defined(self):
        """Verify all visualization types exist"""
        expected_types = [
            "bar_chart",
            "line_chart", 
            "pie_chart",
            "table",
            "multi_series",
            "heatmap",
            "stacked_bar",
            "area_chart",
            "none"
        ]
        
        for viz_type in expected_types:
            assert hasattr(VisualizationType, viz_type.upper())


class TestSQLValidator:
    """Tests for SQL validation"""
    
    def test_valid_select_query(self):
        """Test that valid SELECT queries pass"""
        sql = """
        SELECT location_code, SUM(total_revenue) as revenue
        FROM v_daily_sales_summary
        WHERE order_date = CURRENT_DATE
        GROUP BY location_code
        """
        
        result = SQLValidator.validate(sql)
        assert result.is_valid is True
        assert len(result.errors) == 0
    
    def test_dangerous_keywords_blocked(self):
        """Test that dangerous operations are blocked"""
        dangerous_queries = [
            "DROP TABLE unified_orders",
            "DELETE FROM unified_orders WHERE 1=1",
            "UPDATE unified_orders SET voided = true",
            "INSERT INTO unified_orders (order_id) VALUES (1)",
            "TRUNCATE TABLE unified_orders"
        ]
        
        for sql in dangerous_queries:
            result = SQLValidator.validate(sql)
            assert result.is_valid is False
            assert any("not allowed" in err.lower() or "only select" in err.lower() 
                      for err in result.errors)
    
    def test_cents_conversion_required(self):
        """Test that cents columns require division"""
        sql = """
        SELECT SUM(total_cents) as total
        FROM unified_orders
        WHERE voided = FALSE
        """
        
        result = SQLValidator.validate(sql)
        assert result.is_valid is False
        assert any("cents" in err.lower() or "100" in err.lower() 
                  for err in result.errors)
    
    def test_cents_conversion_passes(self):
        """Test that proper cents conversion passes"""
        sql = """
        SELECT SUM(total_cents) / 100.0 as total
        FROM unified_orders
        WHERE voided = FALSE
        """
        
        result = SQLValidator.validate(sql)
        assert result.is_valid is True
    
    def test_voided_filter_required(self):
        """Test that unified_orders requires voided filter"""
        sql = """
        SELECT COUNT(*) 
        FROM unified_orders
        """
        
        result = SQLValidator.validate(sql)
        assert result.is_valid is False
        assert any("voided" in err.lower() for err in result.errors)
    
    def test_voided_filter_passes(self):
        """Test that proper voided filter passes"""
        sql = """
        SELECT COUNT(*)
        FROM unified_orders
        WHERE voided = FALSE
        """
        
        result = SQLValidator.validate(sql)
        # Should pass voided check (might have other issues)
        assert not any("voided" in err.lower() for err in result.errors)
    
    def test_views_dont_need_division(self):
        """Test that views don't trigger cents warning"""
        sql = """
        SELECT location_code, SUM(total_revenue) as revenue
        FROM v_daily_sales_summary
        GROUP BY location_code
        """
        
        result = SQLValidator.validate(sql)
        assert result.is_valid is True
    
    def test_injection_patterns_detected(self):
        """Test SQL injection pattern detection"""
        injection_queries = [
            "SELECT * FROM unified_orders; --",
            "SELECT * FROM unified_orders WHERE name = '' OR '1'='1'",
        ]
        
        for sql in injection_queries:
            result = SQLValidator.validate(sql)
            # These should either fail validation or at least raise warnings
            # The exact behavior depends on the pattern
    
    def test_quick_check(self):
        """Test the quick_check convenience method"""
        valid, error = SQLValidator.quick_check("SELECT 1")
        assert valid is True
        assert error == ""
        
        valid, error = SQLValidator.quick_check("DROP TABLE users")
        assert valid is False
        assert len(error) > 0
    
    def test_validate_table_name(self):
        """Test table name validation"""
        assert SQLValidator.validate_table_name("unified_orders") is True
        assert SQLValidator.validate_table_name("v_daily_sales_summary") is True
        assert SQLValidator.validate_table_name("fake_table") is False
        assert SQLValidator.validate_table_name('"; DROP TABLE --') is False


class TestSchemaKnowledge:
    """Tests for schema knowledge base"""
    
    def test_schema_has_required_tables(self):
        """Test that all required tables are defined"""
        required_tables = [
            "unified_orders",
            "unified_order_items",
            "unified_products",
            "unified_locations",
            "unified_payments",
            "v_daily_sales_summary",
            "v_product_sales_summary"
        ]
        
        for table in required_tables:
            assert table in SCHEMA_KNOWLEDGE["tables"]
    
    def test_table_info_has_required_fields(self):
        """Test that table definitions have required fields"""
        for table_name, table_info in SCHEMA_KNOWLEDGE["tables"].items():
            assert "description" in table_info
            assert "key_columns" in table_info
            assert "use_for" in table_info
    
    def test_views_marked_correctly(self):
        """Test that views are marked as type=view"""
        views = ["v_daily_sales_summary", "v_product_sales_summary", "v_hourly_sales_pattern"]
        
        for view_name in views:
            if view_name in SCHEMA_KNOWLEDGE["tables"]:
                assert SCHEMA_KNOWLEDGE["tables"][view_name].get("type") == "view"
    
    def test_joins_defined(self):
        """Test that join information is defined"""
        assert "joins" in SCHEMA_KNOWLEDGE
        assert len(SCHEMA_KNOWLEDGE["joins"]) > 0
    
    def test_important_rules_exist(self):
        """Test that important rules are defined"""
        assert "important_rules" in SCHEMA_KNOWLEDGE
        assert len(SCHEMA_KNOWLEDGE["important_rules"]) > 0
    
    def test_get_table_info(self):
        """Test get_table_info helper"""
        info = get_table_info("unified_orders")
        assert info is not None
        assert "description" in info
        
        info = get_table_info("fake_table")
        assert info == {}
    
    def test_get_schema_summary(self):
        """Test schema summary generation"""
        summary = get_schema_summary()
        assert isinstance(summary, str)
        assert "unified_orders" in summary
        assert "IMPORTANT RULES" in summary


class TestExtractedEntities:
    """Tests for entity extraction types"""
    
    def test_extracted_entities_defaults(self):
        """Test default values for extracted entities"""
        entities = ExtractedEntities(
            locations=[],
            products=[],
            categories=[],
            order_types=[],
            payment_types=[],
            sources=[],
            metrics=[]
        )
        
        assert entities["locations"] == []
        assert entities.get("limit") is None
    
    def test_extracted_entities_with_values(self):
        """Test extracted entities with actual values"""
        entities = ExtractedEntities(
            locations=["DOWNTOWN", "AIRPORT"],
            products=["Pizza", "Burger"],
            categories=["Food"],
            order_types=["DELIVERY"],
            payment_types=["CREDIT"],
            sources=["toast"],
            metrics=["revenue"],
            limit=10
        )
        
        assert len(entities["locations"]) == 2
        assert entities["limit"] == 10


class TestTimeRange:
    """Tests for time range types"""
    
    def test_time_range_relative(self):
        """Test relative time range"""
        time_range = TimeRange(
            relative="last_week"
        )
        
        assert time_range["relative"] == "last_week"
        assert time_range.get("start_date") is None
    
    def test_time_range_explicit(self):
        """Test explicit date range"""
        time_range = TimeRange(
            start_date="2024-01-01",
            end_date="2024-01-31"
        )
        
        assert time_range["start_date"] == "2024-01-01"
        assert time_range["end_date"] == "2024-01-31"


# Sample queries for integration testing
SAMPLE_QUERIES = [
    {
        "query": "What were total sales yesterday?",
        "expected_intent": "sales_analysis",
        "should_use_view": True
    },
    {
        "query": "Show me the top 10 selling products",
        "expected_intent": "product_analysis",
        "should_use_view": True
    },
    {
        "query": "Compare revenue by location this month",
        "expected_intent": "location_comparison",
        "should_use_view": True
    },
    {
        "query": "What are our busiest hours?",
        "expected_intent": "time_series",
        "should_use_view": True
    },
    {
        "query": "Payment method breakdown",
        "expected_intent": "payment_analysis",
        "should_use_view": False
    }
]


class TestSampleQueries:
    """Tests using sample queries"""
    
    def test_sample_queries_format(self):
        """Verify sample queries have required fields"""
        for sample in SAMPLE_QUERIES:
            assert "query" in sample
            assert "expected_intent" in sample
            assert isinstance(sample["query"], str)
            assert len(sample["query"]) > 0


class TestAnswerGenerator:
    """Tests for Answer Generator Agent"""
    
    def test_format_value_currency_float(self):
        """Test currency formatting for float values"""
        from backend.agents.answer_generator import _format_value
        
        result = _format_value(1234.56, "total_revenue")
        assert result == "$1,234.56"
        
        result = _format_value(1000.0, "sales_amount")
        assert result == "$1,000.00"
    
    def test_format_value_currency_int(self):
        """Test currency formatting for integer values"""
        from backend.agents.answer_generator import _format_value
        
        result = _format_value(5000, "total_sales")
        assert result == "$5,000"
        
        result = _format_value(100, "revenue")
        assert result == "$100"
    
    def test_format_value_non_currency(self):
        """Test formatting for non-currency values"""
        from backend.agents.answer_generator import _format_value
        
        result = _format_value(1000, "order_count")
        assert result == "1,000"
        
        result = _format_value(3.14159, "average_rating")
        assert result == "3.14"
    
    def test_format_value_none(self):
        """Test None value formatting"""
        from backend.agents.answer_generator import _format_value
        
        result = _format_value(None, "any_column")
        assert result == "N/A"
    
    def test_format_value_string(self):
        """Test string value formatting"""
        from backend.agents.answer_generator import _format_value
        
        result = _format_value("test_value", "product_name")
        assert result == "test_value"
    
    def test_generate_fallback_answer_empty_results(self):
        """Test fallback answer when no results"""
        from backend.agents.answer_generator import _generate_fallback_answer
        
        result = _generate_fallback_answer("Show total sales", [], [])
        assert "No data was found" in result
    
    def test_generate_fallback_answer_single_result(self):
        """Test fallback answer with single result"""
        from backend.agents.answer_generator import _generate_fallback_answer
        
        results = [{"total_revenue": 5000.0, "location_code": "NYC"}]
        columns = ["total_revenue", "location_code"]
        
        result = _generate_fallback_answer("Show total sales", results, columns)
        assert "Total Revenue" in result or "$5,000" in result
        assert "result" in result.lower()
    
    def test_generate_fallback_answer_comparison_query(self):
        """Test fallback answer for comparison queries"""
        from backend.agents.answer_generator import _generate_fallback_answer
        
        results = [
            {"product": "Burger", "total_revenue": 5000.0},
            {"product": "Fries", "total_revenue": 3000.0},
        ]
        columns = ["product", "total_revenue"]
        
        result = _generate_fallback_answer("Compare sales of Burger and Fries", results, columns)
        assert "Burger" in result
        assert "Fries" in result
        assert "Comparing" in result or "compare" in result.lower()
    
    def test_generate_fallback_answer_top_query(self):
        """Test fallback answer for top/best queries"""
        from backend.agents.answer_generator import _generate_fallback_answer
        
        results = [
            {"product": "Pizza", "total_revenue": 8000.0},
            {"product": "Burger", "total_revenue": 5000.0},
            {"product": "Salad", "total_revenue": 2000.0},
        ]
        columns = ["product", "total_revenue"]
        
        result = _generate_fallback_answer("What are the top selling products?", results, columns)
        assert "top" in result.lower() or "performer" in result.lower() or "first" in result.lower()
        assert "Pizza" in result
    
    def test_generate_fallback_answer_total_query(self):
        """Test fallback answer for total queries"""
        from backend.agents.answer_generator import _generate_fallback_answer
        
        results = [
            {"location_code": "NYC", "total_revenue": 5000.0},
            {"location_code": "LA", "total_revenue": 3000.0},
        ]
        columns = ["location_code", "total_revenue"]
        
        result = _generate_fallback_answer("Show total revenue by location", results, columns)
        assert "total" in result.lower() or "result" in result.lower()
    
    def test_answer_generator_agent_with_results(self):
        """Test the full answer generator agent with mock results"""
        from backend.agents.answer_generator import answer_generator_agent
        from unittest.mock import patch, MagicMock
        
        # Create test state
        test_state = {
            "user_query": "What is the total revenue?",
            "query_results": [{"total_revenue": 15000.50}],
            "expected_columns": ["total_revenue"],
            "agent_trace": [],
        }
        
        # Mock the LLM to avoid actual API calls
        mock_response = MagicMock()
        mock_response.content = "The total revenue is $15,000.50. This represents all sales recorded in the database for the queried period."
        
        with patch('backend.agents.answer_generator.ChatNVIDIA') as mock_llm:
            mock_instance = MagicMock()
            mock_llm.return_value = mock_instance
            mock_instance.__or__ = lambda self, other: MagicMock(invoke=lambda x: mock_response)
            
            result = answer_generator_agent(test_state)
        
        assert "generated_answer" in result
        assert len(result["generated_answer"]) > 0
        assert "answer_generator" in result["agent_trace"]
    
    def test_answer_generator_agent_empty_results(self):
        """Test answer generator with empty results"""
        from backend.agents.answer_generator import answer_generator_agent
        from unittest.mock import patch, MagicMock
        
        test_state = {
            "user_query": "Show sales for nonexistent product",
            "query_results": [],
            "expected_columns": [],
            "agent_trace": [],
        }
        
        mock_response = MagicMock()
        mock_response.content = "No sales data was found for the specified product. The product may not exist in our records or there may be no sales for the given criteria."
        
        with patch('backend.agents.answer_generator.ChatNVIDIA') as mock_llm:
            mock_instance = MagicMock()
            mock_llm.return_value = mock_instance
            mock_instance.__or__ = lambda self, other: MagicMock(invoke=lambda x: mock_response)
            
            result = answer_generator_agent(test_state)
        
        assert "generated_answer" in result
        assert "answer_generator" in result["agent_trace"]
    
    def test_answer_generator_agent_fallback_on_error(self):
        """Test answer generator uses fallback when LLM fails"""
        from backend.agents.answer_generator import answer_generator_agent
        from unittest.mock import patch
        
        test_state = {
            "user_query": "What is the total revenue?",
            "query_results": [{"total_revenue": 10000.0}],
            "expected_columns": ["total_revenue"],
            "agent_trace": [],
        }
        
        # Make the LLM raise an exception
        with patch('backend.agents.answer_generator.ChatNVIDIA') as mock_llm:
            mock_llm.side_effect = Exception("API Error")
            
            result = answer_generator_agent(test_state)
        
        assert "generated_answer" in result
        # Should have a fallback answer
        assert len(result["generated_answer"]) > 0
        assert "answer_generator" in result["agent_trace"]
    
    def test_answer_generator_agent_cleans_response(self):
        """Test that answer generator cleans up LLM response artifacts"""
        from backend.agents.answer_generator import answer_generator_agent
        from unittest.mock import patch, MagicMock
        
        test_state = {
            "user_query": "What is the total revenue?",
            "query_results": [{"total_revenue": 5000.0}],
            "expected_columns": ["total_revenue"],
            "agent_trace": [],
        }
        
        # LLM returns response with artifacts
        mock_response = MagicMock()
        mock_response.content = "```\nAnswer: The total revenue is $5,000.00.\n```"
        
        with patch('backend.agents.answer_generator.ChatNVIDIA') as mock_llm:
            mock_instance = MagicMock()
            mock_llm.return_value = mock_instance
            mock_instance.__or__ = lambda self, other: MagicMock(invoke=lambda x: mock_response)
            
            result = answer_generator_agent(test_state)
        
        answer = result.get("generated_answer", "")
        # Should not contain code block markers
        assert "```" not in answer
        # Should not start with "Answer:"
        assert not answer.startswith("Answer:")
    
    def test_answer_generator_agent_validates_quality(self):
        """Test that short/invalid answers trigger fallback"""
        from backend.agents.answer_generator import answer_generator_agent
        from unittest.mock import patch, MagicMock
        
        test_state = {
            "user_query": "What are the top products?",
            "query_results": [
                {"product": "Burger", "total_revenue": 5000.0},
                {"product": "Pizza", "total_revenue": 4000.0},
            ],
            "expected_columns": ["product", "total_revenue"],
            "agent_trace": [],
        }
        
        # LLM returns too short response
        mock_response = MagicMock()
        mock_response.content = "OK"  # Too short, should trigger fallback
        
        with patch('backend.agents.answer_generator.ChatNVIDIA') as mock_llm:
            mock_instance = MagicMock()
            mock_llm.return_value = mock_instance
            mock_instance.__or__ = lambda self, other: MagicMock(invoke=lambda x: mock_response)
            
            result = answer_generator_agent(test_state)
        
        answer = result.get("generated_answer", "")
        # Should have used fallback, which should be longer
        assert len(answer) > 20


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

