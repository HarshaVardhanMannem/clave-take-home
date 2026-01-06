"""
Test Example Queries - Minimal test suite to validate core functionality
Tests that the system can handle essential query types via API endpoints

To run these tests:
1. Start the server: uvicorn backend.main:app --reload
2. Run: pytest tests/test_example_queries.py -v
"""

import pytest
import httpx


# API base URL - adjust if your server runs on different port
API_BASE_URL = "http://localhost:8000"


@pytest.fixture
def client():
    """Create HTTP client for API requests"""
    return httpx.Client(base_url=API_BASE_URL, timeout=60.0)


def make_query(client: httpx.Client, query: str) -> dict[str, any]:
    """
    Helper to make a query request to the API.
    
    Returns the response JSON which may be either:
    - QueryResponse (success=True, has intent, sql, results)
    - ClarificationResponse (clarification_needed=True, has detected_intent, question)
    """
    response = client.post(
        "/api/query",
        json={"query": query, "include_chart": False}
    )
    assert response.status_code == 200, f"API returned {response.status_code}: {response.text}"
    return response.json()


def get_intent(result: dict[str, any]) -> str | None:
    """
    Extract intent from response, handling both QueryResponse and ClarificationResponse.
    
    Returns:
        Intent string or None if not found
    """
    if result.get("clarification_needed"):
        return result.get("detected_intent")
    return result.get("intent")


class TestCoreFunctionality:
    """Minimal test suite covering essential query types"""
    
    def test_basic_sales_query(self, client):
        """Test basic sales analysis query"""
        result = make_query(client, "Show me sales for January 2nd")
        
        assert result.get("success") is True
        intent = get_intent(result)
        assert intent == "sales_analysis"
        
        # If clarification needed, that's acceptable
        if not result.get("clarification_needed"):
            sql = result.get("sql", "")
            assert "2025-01-02" in sql or "order_date" in sql.lower()
            assert "result_count" in result
    
    def test_location_comparison(self, client):
        """Test location comparison query"""
        result = make_query(client, "Compare sales between Downtown and Airport")
        
        assert result.get("success") is True
        intent = get_intent(result)
        assert intent == "location_comparison"
        
        if not result.get("clarification_needed"):
            sql = result.get("sql", "").upper()
            assert "DOWNTOWN" in sql or "downtown" in result.get("sql", "").lower()
            assert "AIRPORT" in sql or "airport" in result.get("sql", "").lower()
    
    def test_category_analysis(self, client):
        """Test category analysis query"""
        result = make_query(client, "Which category generates the most revenue?")
        
        assert result.get("success") is True
        intent = get_intent(result)
        assert intent == "category_analysis"
        
        if not result.get("clarification_needed"):
            sql_lower = result.get("sql", "").lower()
            assert "category" in sql_lower
            assert "revenue" in sql_lower or "sales" in sql_lower
    
    def test_order_type_analysis(self, client):
        """Test order type comparison query"""
        result = make_query(client, "Compare delivery vs dine-in revenue")
        
        assert result.get("success") is True
        intent = get_intent(result)
        assert intent == "order_type_analysis"
        
        if not result.get("clarification_needed"):
            sql_upper = result.get("sql", "").upper()
            assert "DELIVERY" in sql_upper or "DINE_IN" in sql_upper
            assert "ORDER_TYPE" in sql_upper or "order_type" in result.get("sql", "").lower()
    
    def test_api_returns_valid_response(self, client):
        """Test that API returns valid response structure"""
        result = make_query(client, "What was the revenue yesterday?")
        
        # Should always return success=True (even if clarification needed)
        assert result.get("success") is True
        
        # Should have either intent (for QueryResponse) or detected_intent (for ClarificationResponse)
        assert "intent" in result or "detected_intent" in result
        
        # If not clarification needed, should have SQL
        if not result.get("clarification_needed"):
            assert result.get("sql"), "Query should generate SQL when clarification not needed"
            assert len(result.get("sql", "").strip()) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--timeout=60"])
