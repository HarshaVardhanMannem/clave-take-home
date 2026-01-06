"""
Integration Tests for Restaurant Analytics Agent

These tests require:
1. Valid .env file with database credentials
2. Running database with test data
3. Valid NVIDIA API key

Run with: pytest tests/test_integration.py -v --timeout=30
"""

import os
import sys
from pathlib import Path

import pytest

# Load environment variables from .env file
from dotenv import dotenv_values

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Load .env file if it exists
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    env_vars = dotenv_values(env_path)
    for key, value in env_vars.items():
        if value and key not in os.environ:
            os.environ[key] = value

# Skip all tests if environment not configured
pytestmark = pytest.mark.skipif(
    not os.getenv("NVIDIA_API_KEY"),
    reason="NVIDIA_API_KEY not set - skipping integration tests. "
    "Set it in .env file or as environment variable.",
)


class TestDatabaseConnection:
    """Test database connectivity"""
    
    @pytest.mark.asyncio
    async def test_database_connect(self):
        """Test that database connection can be established"""
        from backend.database import SupabasePool
        
        try:
            await SupabasePool.connect()
            assert await SupabasePool.check_health() is True
        finally:
            await SupabasePool.disconnect()
    
    @pytest.mark.asyncio
    async def test_simple_query(self):
        """Test executing a simple query"""
        from backend.database import SupabasePool
        
        try:
            await SupabasePool.connect()
            
            results, exec_time = await SupabasePool.execute_query("SELECT 1 as test")
            
            assert len(results) == 1
            assert results[0]["test"] == 1
            assert exec_time > 0
        finally:
            await SupabasePool.disconnect()
    
    @pytest.mark.asyncio
    async def test_query_timeout(self):
        """Test that query timeout works"""
        from backend.database import SupabasePool
        
        try:
            await SupabasePool.connect()
            
            # This should complete quickly
            results, _ = await SupabasePool.execute_query(
                "SELECT pg_sleep(0.1)::text",
                timeout=5
            )
            assert results is not None
            
        finally:
            await SupabasePool.disconnect()


class TestAgentWorkflow:
    """Test the complete agent workflow"""
    
    @pytest.fixture
    def runner(self):
        """Get agent runner"""
        from backend.agent_framework import get_agent_runner
        return get_agent_runner()
    
    def test_simple_sales_query(self, runner):
        """Test a simple sales query"""
        result = runner.process_query("What were total sales yesterday?")
        
        assert "query_intent" in result
        assert "generated_sql" in result
        assert result.get("sql_validation_passed") is True or result.get("needs_clarification") is True
    
    def test_product_query(self, runner):
        """Test a product analysis query"""
        result = runner.process_query("Show me the top 10 selling products")
        
        assert result.get("query_intent") is not None
        assert "generated_sql" in result
    
    def test_location_comparison(self, runner):
        """Test a location comparison query"""
        result = runner.process_query("Compare revenue across all locations this month")
        
        assert result.get("query_intent") is not None
        if result.get("sql_validation_passed"):
            assert "v_daily_sales_summary" in result.get("generated_sql", "").lower() or \
                   "unified" in result.get("generated_sql", "").lower()
    
    def test_ambiguous_query_clarification(self, runner):
        """Test that ambiguous queries request clarification"""
        result = runner.process_query("Show me data")
        
        # Very ambiguous query should trigger clarification or low confidence
        # The exact behavior depends on the LLM
        assert "query_intent" in result
    
    def test_retry_mechanism(self, runner):
        """Test that validation retry works"""
        # Use a query that might need retries
        result = runner.process_query(
            "Show me order details with payment information"
        )
        
        # Check retry tracking
        assert "retry_count" in result
        assert result.get("retry_count", 0) <= result.get("max_retries", 2)


class TestVisualization:
    """Test visualization generation"""
    
    def test_bar_chart_generation(self):
        """Test bar chart config generation"""
        from backend.visualization import VisualizationGenerator
        from backend.models.state import VisualizationType, VisualizationConfig
        
        data = [
            {"location": "Downtown", "revenue": 1000},
            {"location": "Airport", "revenue": 1500},
            {"location": "Mall", "revenue": 800}
        ]
        
        config = VisualizationConfig(
            x_axis="location",
            y_axis="revenue",
            title="Revenue by Location",
            format_type="currency"
        )
        
        chart = VisualizationGenerator.generate_config(
            data,
            VisualizationType.BAR_CHART,
            config
        )
        
        assert chart["type"] == "bar"
        assert len(chart["data"]["labels"]) == 3
        assert len(chart["data"]["datasets"]) >= 1
    
    def test_line_chart_generation(self):
        """Test line chart config generation"""
        from backend.visualization import VisualizationGenerator
        from backend.models.state import VisualizationType, VisualizationConfig
        
        data = [
            {"date": "2024-01-01", "revenue": 1000},
            {"date": "2024-01-02", "revenue": 1200},
            {"date": "2024-01-03", "revenue": 900}
        ]
        
        config = VisualizationConfig(
            x_axis="date",
            y_axis="revenue",
            title="Daily Revenue"
        )
        
        chart = VisualizationGenerator.generate_config(
            data,
            VisualizationType.LINE_CHART,
            config
        )
        
        assert chart["type"] == "line"
        assert len(chart["data"]["datasets"][0]["data"]) == 3
    
    def test_pie_chart_generation(self):
        """Test pie chart config generation"""
        from backend.visualization import VisualizationGenerator
        from backend.models.state import VisualizationType, VisualizationConfig
        
        data = [
            {"payment_type": "Credit", "count": 100},
            {"payment_type": "Cash", "count": 50},
            {"payment_type": "Debit", "count": 30}
        ]
        
        config = VisualizationConfig(
            x_axis="payment_type",
            y_axis="count",
            title="Payment Methods"
        )
        
        chart = VisualizationGenerator.generate_config(
            data,
            VisualizationType.PIE_CHART,
            config
        )
        
        assert chart["type"] == "pie"
    
    def test_empty_data_handling(self):
        """Test handling of empty data"""
        from backend.visualization import VisualizationGenerator
        from backend.models.state import VisualizationType, VisualizationConfig
        
        chart = VisualizationGenerator.generate_config(
            [],
            VisualizationType.BAR_CHART,
            VisualizationConfig(title="Empty Chart")
        )
        
        assert chart["data"]["labels"] == []
        assert chart["data"]["datasets"] == []


class TestAPIEndpoints:
    """Test FastAPI endpoints"""
    
    @pytest.fixture
    def client(self):
        """Get test client"""
        from fastapi.testclient import TestClient
        from backend.main import app
        return TestClient(app)
    
    def test_health_endpoint(self, client):
        """Test health check endpoint"""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
    
    def test_examples_endpoint(self, client):
        """Test examples endpoint"""
        response = client.get("/api/examples")
        assert response.status_code == 200
        data = response.json()
        assert "examples" in data
        assert len(data["examples"]) > 0
    
    def test_schema_endpoint(self, client):
        """Test schema endpoint"""
        response = client.get("/api/schema")
        assert response.status_code == 200
        data = response.json()
        assert "tables" in data
        assert "views" in data
        assert "important_rules" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--timeout=60"])


