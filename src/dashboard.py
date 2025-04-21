import streamlit as st
import os
from pathlib import Path
from typing import Optional, Dict, Any
import pandas as pd
import numpy as np
from sklearn.cluster import MiniBatchKMeans
from sklearn.metrics import silhouette_score
import json
import asyncio
import asyncpg
import redis.asyncio as redis
from collections import defaultdict
from streamlit_autorefresh import st_autorefresh
import plotly.express as px
from src.logger import get_logger

class AsyncRedisClient:
    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        redis_key: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize async Redis client with .env fallbacks.
        
        Args:
            **kwargs: Additional Redis connection parameters (e.g., password, db)
        """
        self.logger = get_logger(self.__class__.__name__)
        
        # Environment variable fallbacks
        self.host = host or os.getenv("REDIS_HOST", "redis")
        self.port = port or int(os.getenv("REDIS_PORT", 6379))
        self.redis_key = redis_key or os.getenv("REDIS_KEY", "stock_updates")   
        self.client = None

    async def connect(self):
        """
        Connect to Redis asynchronously.
        """
        try:
            self.client = redis.Redis(host=self.host, port=self.port, decode_responses=True)
            await self.client.ping()
            self.logger.info(f"Connected to Redis at {self.host}:{self.port}")
        except Exception as e:
            self.logger.error(f"Failed to connect to Redis at {self.host}:{self.port}. Error: {e}")
            raise

    async def fetch_data(self) -> pd.DataFrame:
        """
        Fetch data from Redis asynchronously and return it as a Pandas DataFrame.
        """
        try:
            messages = await self.client.lrange(self.redis_key, 0, -1)
            data = []
            for msg in messages:
                record = json.loads(msg)
                data.append({
                    "Symbol": record["symbol"],
                    "Timestamp": record.get("timestamp"),
                    "Price": record["price"]
                })
            df = pd.DataFrame(data)
            self.logger.info(f"Fetched {len(df)} records from Redis under key '{self.redis_key}'")
            return df
        except Exception as e:
            self.logger.error(f"Failed to fetch data from Redis under key '{self.redis_key}'. Error: {e}")
            return pd.DataFrame()

    async def close(self):
        """
        Close the Redis connection.
        """
        if self.client:
            await self.client.close()
            self.logger.info("Closed Redis connection.")


class AsyncPostgresClient:
    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        dbname: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize PostgreSQL connection with .env fallbacks.
        """
        self.logger = get_logger(self.__class__.__name__)
        
        # Environment variable fallbacks
        self.host = host or os.getenv("POSTGRES_HOST", "postgres")
        self.port = port or int(os.getenv("POSTGRES_PORT", 5432))
        self.user = user or os.getenv("POSTGRES_USER", "postgres")
        self.password = password or os.getenv("POSTGRES_PASSWORD", "postgres")
        self.dbname = dbname or os.getenv("POSTGRES_DB", "stock_data")
        
        # Connection pool (initialize separately)
        self.pool = None

    async def connect(self):
        """
        Connect to PostgreSQL asynchronously.
        """
        try:
            self.pool = await asyncpg.create_pool(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.dbname
            )
            self.logger.info(f"Connected to PostgreSQL at {self.host}:{self.port}, Database: {self.dbname}")
        except Exception as e:
            self.logger.error(f"Failed to connect to PostgreSQL at {self.host}:{self.port}. Error: {e}")
            raise

    async def fetch_data(self, window_seconds: int = None) -> pd.DataFrame:
        """
        Fetch data from PostgreSQL asynchronously and return it as a Pandas DataFrame.
        """
        try:
            query = "SELECT symbol, data->>'price' AS price, timestamp FROM stock_updates"
            if window_seconds is not None:
                query += f" WHERE timestamp >= NOW() - INTERVAL '{window_seconds} seconds'"
            query += " ORDER BY timestamp DESC"

            async with self.pool.acquire() as connection:
                rows = await connection.fetch(query)
                df = pd.DataFrame([dict(row) for row in rows])
                if not df.empty:
                    df = df.rename(columns={"symbol": "Symbol", "timestamp": "Timestamp", "price": "Price"})
                self.logger.info(f"Fetched {len(df)} rows from PostgreSQL.")
                return df
        except Exception as e:
            self.logger.error(f"Failed to fetch data from PostgreSQL. Error: {e}")
            return pd.DataFrame()

    async def close(self):
        """
        Close the PostgreSQL connection pool.
        """
        if self.pool:
            await self.pool.close()
            self.logger.info("Closed PostgreSQL connection pool.")


class DataProcessor:
    """
    Handles data processing tasks like filtering, formatting, and aggregation.
    """
    def __init__(self):
        self.logger = get_logger(self.__class__.__name__)

    def process(self, df: pd.DataFrame, window_seconds: int) -> pd.DataFrame:
        """
        Process the data by filtering, formatting, and aggregating it.
        """
        if df.empty:
            return df

        try:
            self.logger.debug(f"DataFrame before processing: {df.head()}")

            # Ensure the Price column is numeric
            df["Price"] = pd.to_numeric(df["Price"], errors="coerce")
            df = df.dropna(subset=["Price"])  # Drop rows with NaN in Price

            # Format the timestamp column
            df["Timestamp"] = pd.to_datetime(df["Timestamp"], unit='s', errors='coerce')
            df = df.dropna(subset=["Timestamp"])  # Drop rows with NaN in Timestamp
            df = df.sort_values("Timestamp")

            # Filter data based on the selected time window
            if window_seconds is not None:
                now = pd.Timestamp.now()
                df = df[df["Timestamp"] >= now - pd.Timedelta(seconds=window_seconds)]

            # Add a "Seconds" column for grouping
            df["Seconds"] = df["Timestamp"].dt.strftime("%H:%M:%S")  # Show only time (HH:MM:SS)

            # Aggregate data to ensure unique combinations of "Seconds" and "Symbol"
            df = df.groupby(["Seconds", "Symbol"], as_index=False).agg({"Price": "mean"})

            self.logger.info(f"Processed data with {len(df)} rows after filtering and aggregation.")
            return df
        except Exception as e:
            self.logger.error(f"Error while processing data. Error: {e}")
            return pd.DataFrame()

def find_optimal_clusters(
    data: np.ndarray, 
    max_k: int = 8, 
    batch_size: int = 100
) -> int:
    """
    Dynamically determine the optimal number of clusters for the data using silhouette score.
    Uses MiniBatchKMeans for efficiency on real-time/batch data.
    Returns at least 2 clusters, or 1 if not possible.
    """
    best_k = 2
    best_score = -1.0
    n_samples = data.shape[0]
    # Ensure max_k does not exceed n_samples - 1 (since k must be < n_samples)
    max_k = min(max_k, n_samples - 1)
    if n_samples < 2:
        return 1  # Not enough samples to cluster

    for k in range(2, max_k + 1):
        try:
            kmeans = MiniBatchKMeans(n_clusters=k, batch_size=batch_size, random_state=42)
            labels = kmeans.fit_predict(data)
            if len(set(labels)) < 2 or len(set(labels)) == n_samples:
                continue
            score = silhouette_score(data, labels)
            if score > best_score:
                best_k = k
                best_score = score
        except Exception as e:
            # Use your logger here if desired
            print(f"Clustering failed for k={k}: {e}")
            continue
    return best_k if best_score > -1 else 1


class Dashboard:
    """
    Handles the Streamlit dashboard rendering.
    """
    def __init__(self):
        self.logger = get_logger(self.__class__.__name__)

    def render(self, df: pd.DataFrame) -> None:
        """
        Render the Streamlit dashboard with the given DataFrame.
        """
        if df.empty:
            st.write("No data available for the selected time window.")
            return

        try:
      

            # Pivot the DataFrame for the chart
            chart_df = df.pivot(index="Seconds", columns="Symbol", values="Price")
            chart_df = chart_df.ffill().bfill()  # Fill gaps
            chart_df = chart_df.sort_index(ascending=True)  # Ensure ascending order
            # Display the data table
            st.dataframe(chart_df)
            #convert to long format for Plotly
            chart_df_long = chart_df.reset_index().melt(
                id_vars="Seconds", var_name="Symbol", value_name="Price"
            )

            # Define a color map for consistent colors (optional)
            symbols = chart_df.columns.tolist()
            palette = px.colors.qualitative.Plotly
            color_map = {symbol: palette[i % len(palette)] for i, symbol in enumerate(symbols)}

            # Plotly Express line chart
            fig = px.line(
                chart_df_long,
                x="Seconds",
                y="Price",
                color="Symbol",
                color_discrete_map=color_map,  # Optional, for consistent colors
                title="Stock Prices by Symbol"
            )
            st.plotly_chart(fig, use_container_width=True)

            self.logger.info("Dashboard rendered successfully.")
        except Exception as e:
            self.logger.error(f"Error while rendering dashboard. Error: {e}")



    def render_clusters(self, df: pd.DataFrame) -> None:
        """
        Render the Streamlit dashboard with the given DataFrame.
        Clusters stocks by recent price series and plots the clusters.
        Handles errors gracefully for production readiness.
        """
        if df.empty:
            st.write("No data available for the selected time window.")
            self.logger.warning("DataFrame is empty.")
            return

        try:
            # Pivot for time series: rows = time, columns = symbol
            chart_df = df.pivot(index="Seconds", columns="Symbol", values="Price")
            chart_df = chart_df.ffill().bfill()
            chart_df = chart_df.sort_index(ascending=True)  # Ensure ascending order
            st.dataframe(chart_df)
        except Exception as e:
            st.error("Error processing data for charting.")
            self.logger.error(f"Error in pivoting/filling data: {e}")
            return

        # Prepare for clustering: each stock is a row, columns are time points
        try:
            data_for_clustering = chart_df.T.values
            symbols = chart_df.columns.to_list()
            n_stocks = len(symbols)
        except Exception as e:
            st.error("Error preparing data for clustering.")
            self.logger.error(f"Error extracting clustering data: {e}")
            return

        if n_stocks < 2:
            st.info("Not enough stocks for clustering.")
            st.line_chart(chart_df)
            self.logger.info("Not enough stocks to perform clustering.")
            return

        # Cluster on the latest batch of data, with error handling
        try:
            optimal_k = find_optimal_clusters(
                data_for_clustering, 
                max_k=n_stocks - 1, # Ensure at least 2 clusters
                batch_size=max(10, n_stocks) # Batch size for MiniBatchKMeans
            )
            kmeans = MiniBatchKMeans(
                n_clusters=optimal_k, 
                batch_size=max(10, n_stocks), 
                random_state=42
            )
            clusters = kmeans.fit_predict(data_for_clustering)
        except Exception as e:
            st.error("Clustering failed. Please check your data or try again later.")
            self.logger.error(f"Clustering error: {e}")
            st.line_chart(chart_df)
            return

        # # Show cluster assignments
        try:
            cluster_df = pd.DataFrame({
                "Symbol": symbols,
                "Cluster": clusters
            }).sort_values("Cluster")
            ##-- added for debugging
            #st.subheader(f"Stock Clusters (k={optimal_k})")
            #st.dataframe(cluster_df)
        except Exception as e:
            st.error("Error displaying cluster assignments.")
            self.logger.error(f"Error displaying cluster assignments: {e}")

        

        try:
            # Use the same sorted index as the wide DataFrame
            seconds_order = chart_df.index.tolist()

            # Melt to long format for Plotly Express
            chart_df_long = chart_df.reset_index().melt(
                id_vars="Seconds", var_name="Symbol", value_name="Price"
            )
            # Merge in cluster assignments
            chart_df_long = chart_df_long.merge(cluster_df, on="Symbol")
            chart_df_long["Cluster"] = chart_df_long["Cluster"].astype(str)

            # Ensure consistent Seconds ordering
            chart_df_long["Seconds"] = pd.Categorical(
                chart_df_long["Seconds"],
                categories=seconds_order,
                ordered=True
            )
            chart_df_long = chart_df_long.sort_values("Seconds")
          
            # Get unique symbols
            symbols = chart_df_long["Symbol"].unique()
            # Choose a color palette (Plotly's default qualitative palette)
            palette = px.colors.qualitative.Plotly

            # Map each symbol to a color
            color_map = {symbol: palette[i % len(palette)] for i, symbol in enumerate(symbols)}
           
            fig = px.line(
                chart_df_long,
                x="Seconds",
                y="Price",
                color="Symbol",
                line_group="Symbol",
                hover_name="Symbol",
                line_dash="Cluster",
                color_discrete_map=color_map,  # <-- Ensures consistent colors
                title=f"Stock Prices: Color by Symbol, and {optimal_k} cluster line types"
            )

            # Only show the symbol in the legend (one entry per symbol)
            seen = set()
            for trace in fig.data:
                # The trace name is like 'AAPL, 0' -- we want only 'AAPL'
                symbol = trace.name.split(",")[0]
                if symbol in seen:
                    trace.showlegend = False
                else:
                    trace.name = symbol
                    trace.showlegend = True
                    seen.add(symbol)

            st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.error("Error generating cluster plot.")
            self.logger.error(f"Error plotting clusters: {e}")
            st.line_chart(chart_df)


async def main():
    # Initialize Redis client
    redis_client = AsyncRedisClient()
    await redis_client.connect()

    # Initialize PostgreSQL client
    postgres_client = AsyncPostgresClient()

    await postgres_client.connect()

    # Initialize data processor
    data_processor = DataProcessor()

    # Initialize dashboard
    dashboard = Dashboard()

    # Streamlit UI
    st.title("Real-time Data Streaming with Redis and PostgreSQL")

    # Create two tabs: Dashboard (default), About
    tab_dashboard, tab_about = st.tabs(["📊 Dashboard", "ℹ️ About"])

    with tab_dashboard:
        # Auto-refresh the dashboard every 2 seconds
        st_autorefresh(interval=2000, key="data_refresh")

        # Dropdown for time window selection
        window_option = st.selectbox(
            "Show data for:",
            ("Last 20 seconds", "Last 60 seconds", "Last 120 seconds")
        )
        if window_option == "Last 20 seconds":
            window_seconds = 20
        elif window_option == "Last 60 seconds":
            window_seconds = 60
        else:
            window_seconds = 120 

        # Fetch and process data from Redis
        with st.spinner("Fetching Redis data..."):
            raw_data_redis = await redis_client.fetch_data()
        processed_data_redis = data_processor.process(raw_data_redis, window_seconds)

        # Fetch and process data from PostgreSQL
        with st.spinner("Fetching PostgresSQL data..."):
            raw_data_postgres = await postgres_client.fetch_data(window_seconds)
        processed_data_postgres = data_processor.process(raw_data_postgres, window_seconds)

        # Render the dashboard for PostgreSQL data
        st.subheader("PostgreSQL Data")
        dashboard.render_clusters(processed_data_postgres)

        # Render the dashboard for Redis data
        st.subheader("Redis Data")
        dashboard.render(processed_data_redis)

        # Close connections
        await redis_client.close()
        await postgres_client.close()

    with tab_about:

        #about_md = Path("about.md").read_text()
        about_md_path = Path(__file__).parent / "about.md"
        about_md = about_md_path.read_text(encoding="utf-8")
        st.markdown(about_md, unsafe_allow_html=True)

if __name__ == "__main__":
    asyncio.run(main())