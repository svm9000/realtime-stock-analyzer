import pytest
import sys
import pandas as pd
from unittest.mock import patch, MagicMock
import plotly.graph_objs as go

# Mock imports for missing modules
sys.modules['src.data_processor'] = MagicMock()
sys.modules['src.redis_client'] = MagicMock()
sys.modules['src.postgres_client'] = MagicMock()

from src.dashboard import Dashboard  # Primary test target

def test_empty_dataframe():
    """Test empty DataFrame handling"""
    with patch('streamlit.write') as mock_write:
        dashboard = Dashboard()
        dashboard.render(pd.DataFrame())
        mock_write.assert_called_once_with("No data available for the selected time window.")

def test_successful_render():
    """Test successful chart rendering"""
    test_data = pd.DataFrame({
        "Seconds": [1, 2, 3],
        "Symbol": ["AAPL", "MSFT", "GOOGL"],
        "Price": [175.5, 250.3, 140.2]
    })
    
    with patch('streamlit.dataframe'), \
         patch('streamlit.line_chart'):
        dashboard = Dashboard()
        dashboard.render(test_data)
        
# def test_chart_data_structure():
#     """Verify chart data formatting"""
#     test_data = pd.DataFrame({
#         "Seconds": [1, 2],
#         "Symbol": ["AAPL", "MSFT"],
#         "Price": [175.5, 250.3]
#     })
    
#     with patch('streamlit.dataframe'), \
#          patch('streamlit.line_chart') as mock_chart:
        
#         dashboard = Dashboard()
#         dashboard.render(test_data)
        
#         args, _ = mock_chart.call_args
#         assert isinstance(args[0], pd.DataFrame)
#         assert "AAPL" in args[0].columns
#         assert "MSFT" in args[0].columns

def test_chart_data_structure():
    """Verify chart data formatting for Plotly chart"""
    test_data = pd.DataFrame({
        "Seconds": [1, 2],
        "Symbol": ["AAPL", "MSFT"],
        "Price": [175.5, 250.3]
    })
    
    with patch('streamlit.dataframe'), \
         patch('streamlit.plotly_chart') as mock_plotly_chart:
        
        dashboard = Dashboard()
        dashboard.render(test_data)
        
        # Ensure plotly_chart was called
        assert mock_plotly_chart.called, "st.plotly_chart was not called"
        args, kwargs = mock_plotly_chart.call_args
        fig = args[0]
        assert isinstance(fig, go.Figure), "First argument is not a Plotly Figure"

        # Extract data from the figure
        symbols_in_fig = set()
        for trace in fig.data:
            symbols_in_fig.add(trace.name)
        
        assert "AAPL" in symbols_in_fig, "'AAPL' not found in chart symbols"
        assert "MSFT" in symbols_in_fig, "'MSFT' not found in chart symbols"
