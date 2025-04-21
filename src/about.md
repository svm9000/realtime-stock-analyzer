 # 📈 Real-Time Stock Dashboard

🚀 **What is this?**  
This dashboard streams, simulates, and visualizes real-time stock price data for your favorite stocks.

---

🧬 **How is the data simulated?**  
- **Historical Volatility 📊**: For each stock, we calculate annualized volatility using the last 30 days of real market data from Yahoo Finance.
- **Latest Price 💵**: The most recent closing price is fetched as the simulation starting point.
- **Geometric Brownian Motion 🔀**: We simulate the next price using a mathematical model that incorporates the fetched volatility and a random "shock," just like real market movements.

---

🛠️ **How is the data processed?**  
- **Filtering 🔍**: Only the latest data within your selected time window is shown.
- **Formatting ⏰**: Timestamps are converted to readable times, and prices are cleaned and validated.
- **Aggregation 📦**: Data is grouped by second and symbol, and prices are averaged for smooth, clear charts.

---

🧩 **How are clusters calculated dynamically?**  
- **Dynamic Clustering 🤖**: We use MiniBatch K-Means to group stocks with similar price behavior in real time.
- **Optimal Cluster Count 🔢**: The best number of clusters is chosen automatically using the silhouette score.
- **Always Adaptive 🌐**: The number of clusters adapts to the data for the most meaningful grouping.

---

✨ **Why use this dashboard?**  
- Track simulated stock prices in real time  
- Visualize clusters and trends  
- Experiment with streaming data and analytics  

