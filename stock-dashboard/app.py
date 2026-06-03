import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


st.set_page_config(page_title="Stock Dashboard", page_icon="📈", layout="wide")

st.title("Stock Dashboard")

REQUIRED_COLUMNS = {"ticker", "date", "quantity", "price", "action"}
UPLOAD_FIRST_MESSAGE = "Upload a CSV file in Tab 1, Upload CSV, to get started."


def prepare_stock_data(dataframe):
    stock_data = dataframe.copy()
    stock_data["date"] = pd.to_datetime(stock_data["date"], errors="coerce")
    stock_data["quantity"] = pd.to_numeric(stock_data["quantity"], errors="coerce")
    stock_data["price"] = pd.to_numeric(stock_data["price"], errors="coerce")
    stock_data["action"] = stock_data["action"].str.upper()
    stock_data = stock_data.dropna(subset=["date", "quantity", "price"])
    return stock_data.sort_values("date")


def build_position_summary(stock_data):
    rows = []

    for ticker, ticker_data in stock_data.groupby("ticker"):
        buys = ticker_data[ticker_data["action"] == "BUY"]
        sells = ticker_data[ticker_data["action"] == "SELL"]
        buy_quantity = buys["quantity"].sum()
        sell_quantity = sells["quantity"].sum()
        current_quantity = buy_quantity - sell_quantity
        avg_buy_price = (
            (buys["quantity"] * buys["price"]).sum() / buy_quantity
            if buy_quantity > 0
            else 0
        )
        latest_price = ticker_data.sort_values("date").iloc[-1]["price"]
        total_profit_loss = (latest_price - avg_buy_price) * current_quantity
        cost_basis = avg_buy_price * current_quantity
        return_percentage = (
            total_profit_loss / cost_basis * 100 if cost_basis > 0 else 0
        )

        rows.append(
            {
                "Ticker": ticker,
                "Current Quantity Held": current_quantity,
                "Average Buy Price": avg_buy_price,
                "Latest Price": latest_price,
                "Total Profit/Loss": total_profit_loss,
                "Return Percentage": return_percentage,
            }
        )

    return pd.DataFrame(rows).sort_values("Ticker")


def build_cumulative_profit(stock_data):
    running_positions = {}
    chart_rows = []

    for _, transaction in stock_data.iterrows():
        ticker = transaction["ticker"]
        quantity = transaction["quantity"]
        price = transaction["price"]
        action = transaction["action"]

        position = running_positions.setdefault(
            ticker, {"quantity": 0, "buy_quantity": 0, "buy_value": 0}
        )

        if action == "BUY":
            position["quantity"] += quantity
            position["buy_quantity"] += quantity
            position["buy_value"] += quantity * price
        elif action == "SELL":
            position["quantity"] -= quantity

        latest_prices = {
            row["ticker"]: row["price"]
            for _, row in stock_data[stock_data["date"] <= transaction["date"]].iterrows()
        }

        cumulative_profit = 0
        for position_ticker, current_position in running_positions.items():
            avg_buy_price = (
                current_position["buy_value"] / current_position["buy_quantity"]
                if current_position["buy_quantity"] > 0
                else 0
            )
            latest_price = latest_prices.get(position_ticker, avg_buy_price)
            cumulative_profit += (
                latest_price - avg_buy_price
            ) * current_position["quantity"]

        chart_rows.append(
            {"Date": transaction["date"], "Cumulative Profit": cumulative_profit}
        )

    return pd.DataFrame(chart_rows)


def calculate_stock_detail(ticker_data):
    buys = ticker_data[ticker_data["action"] == "BUY"]
    sells = ticker_data[ticker_data["action"] == "SELL"]
    buy_quantity = buys["quantity"].sum()
    sell_quantity = sells["quantity"].sum()
    current_quantity = buy_quantity - sell_quantity
    total_invested = (buys["quantity"] * buys["price"]).sum()
    avg_buy_price = total_invested / buy_quantity if buy_quantity > 0 else 0
    latest_price = ticker_data.sort_values("date").iloc[-1]["price"]
    unrealized_profit_loss = (latest_price - avg_buy_price) * current_quantity

    return {
        "avg_buy_price": avg_buy_price,
        "current_quantity": current_quantity,
        "total_invested": total_invested,
        "unrealized_profit_loss": unrealized_profit_loss,
    }


def color_profit_loss(value):
    if value > 0:
        return "color: #12805c"
    if value < 0:
        return "color: #b42318"
    return ""


if "watchlist" not in st.session_state:
    st.session_state["watchlist"] = []

upload_tab, analytics_tab, stock_detail_tab, watchlist_tab = st.tabs(
    ["Upload CSV", "Analytics", "Stock Detail", "Watchlist"]
)

with upload_tab:
    st.header("Upload CSV")
    st.write("Upload a stock transactions CSV file to begin analyzing your portfolio.")

    uploaded_file = st.file_uploader("Choose a CSV file", type=["csv"])

    if uploaded_file is None:
        st.info(
            "Your CSV should include these columns: ticker, date, quantity, price, action."
        )
        st.caption("Tip: use sample_stocks.csv from this project to test the app.")
    else:
        try:
            dataframe = pd.read_csv(uploaded_file)
        except Exception as exc:
            st.session_state.pop("stock_data", None)
            st.error(f"Could not read the uploaded CSV file: {exc}")
        else:
            missing_columns = REQUIRED_COLUMNS - set(dataframe.columns)

            if missing_columns:
                st.session_state.pop("stock_data", None)
                missing_list = ", ".join(sorted(missing_columns))
                st.error(f"The uploaded CSV is missing required columns: {missing_list}")
            else:
                st.session_state["stock_data"] = dataframe
                st.success("CSV uploaded and validated successfully.")
                st.subheader("Preview")
                st.dataframe(
                    dataframe.head(10).style.format(
                        {"quantity": "{:,.0f}", "price": "${:,.2f}"}
                    ),
                    use_container_width=True,
                    hide_index=True,
                )

with st.sidebar:
    st.title("Stock Dashboard")
    if "stock_data" in st.session_state:
        st.success("CSV loaded")
    else:
        st.info("No CSV loaded")

with analytics_tab:
    st.header("Analytics")

    if "stock_data" not in st.session_state:
        st.info(f"{UPLOAD_FIRST_MESSAGE} Analytics will appear here once data is loaded.")
    else:
        stock_data = prepare_stock_data(st.session_state["stock_data"])

        if stock_data.empty:
            st.warning("The uploaded CSV does not contain valid stock transaction data.")
        else:
            position_summary = build_position_summary(stock_data)
            open_positions = position_summary[
                position_summary["Current Quantity Held"] > 0
            ]
            total_profit_loss = position_summary["Total Profit/Loss"].sum()
            total_portfolio_value = (
                position_summary["Current Quantity Held"]
                * position_summary["Latest Price"]
            ).sum()
            best_stock = (
                position_summary.sort_values("Return Percentage", ascending=False)
                .iloc[0]["Ticker"]
                if not position_summary.empty
                else "N/A"
            )

            metric_1, metric_2, metric_3, metric_4 = st.columns(4)
            metric_1.metric("Total Profit/Loss", f"${total_profit_loss:,.2f}")
            metric_2.metric("Total Portfolio Value", f"${total_portfolio_value:,.2f}")
            metric_3.metric("Open Positions", f"{len(open_positions):,}")
            metric_4.metric("Best Performing Stock", best_stock)

            cumulative_profit = build_cumulative_profit(stock_data)
            figure = px.line(
                cumulative_profit,
                x="Date",
                y="Cumulative Profit",
                title="Cumulative Profit Over Time",
                markers=True,
            )
            figure.update_layout(
                yaxis_tickprefix="$",
                hovermode="x unified",
                margin={"l": 20, "r": 20, "t": 60, "b": 20},
            )
            st.plotly_chart(figure, use_container_width=True)

            st.subheader("Ticker Performance")
            styled_summary = position_summary.style.format(
                {
                    "Current Quantity Held": "{:,.0f}",
                    "Average Buy Price": "${:,.2f}",
                    "Latest Price": "${:,.2f}",
                    "Total Profit/Loss": "${:,.2f}",
                    "Return Percentage": "{:,.2f}%",
                }
            ).map(
                color_profit_loss,
                subset=["Total Profit/Loss", "Return Percentage"],
            )
            st.dataframe(
                styled_summary,
                use_container_width=True,
                hide_index=True,
            )

with stock_detail_tab:
    st.header("Stock Detail")

    if "stock_data" not in st.session_state:
        st.info(
            f"{UPLOAD_FIRST_MESSAGE} Stock-level details will appear here once data is loaded."
        )
    else:
        stock_data = prepare_stock_data(st.session_state["stock_data"])

        if stock_data.empty:
            st.warning("The uploaded CSV does not contain valid stock transaction data.")
        else:
            tickers = sorted(stock_data["ticker"].unique())
            selected_ticker = st.selectbox("Select a ticker", tickers)
            ticker_data = stock_data[
                stock_data["ticker"] == selected_ticker
            ].sort_values("date")
            stock_detail = calculate_stock_detail(ticker_data)

            metric_1, metric_2, metric_3, metric_4 = st.columns(4)
            metric_1.metric(
                "Average Buy Price", f"${stock_detail['avg_buy_price']:,.2f}"
            )
            metric_2.metric(
                "Shares Currently Held",
                f"{stock_detail['current_quantity']:,.0f}",
            )
            metric_3.metric(
                "Total Amount Invested", f"${stock_detail['total_invested']:,.2f}"
            )
            metric_4.metric(
                "Unrealized Profit/Loss",
                f"${stock_detail['unrealized_profit_loss']:,.2f}",
            )

            figure = px.line(
                ticker_data,
                x="date",
                y="price",
                title=f"{selected_ticker} Price Over Time",
                markers=True,
            )

            buy_transactions = ticker_data[ticker_data["action"] == "BUY"]
            sell_transactions = ticker_data[ticker_data["action"] == "SELL"]

            figure.add_trace(
                go.Scatter(
                    x=buy_transactions["date"],
                    y=buy_transactions["price"],
                    mode="markers",
                    name="BUY",
                    marker={
                        "symbol": "triangle-up",
                        "size": 13,
                        "color": "#12805c",
                        "line": {"width": 1, "color": "#0b4f3a"},
                    },
                )
            )
            figure.add_trace(
                go.Scatter(
                    x=sell_transactions["date"],
                    y=sell_transactions["price"],
                    mode="markers",
                    name="SELL",
                    marker={
                        "symbol": "triangle-down",
                        "size": 13,
                        "color": "#b42318",
                        "line": {"width": 1, "color": "#7a271a"},
                    },
                )
            )
            figure.add_hline(
                y=stock_detail["avg_buy_price"],
                line_dash="dash",
                line_color="#6b7280",
                annotation_text="Average buy price",
                annotation_position="top left",
            )
            figure.update_layout(
                yaxis_tickprefix="$",
                hovermode="x unified",
                margin={"l": 20, "r": 20, "t": 60, "b": 20},
            )
            st.plotly_chart(figure, use_container_width=True)

            st.subheader(f"{selected_ticker} Transaction History")
            transaction_history = ticker_data.copy()
            transaction_history["date"] = transaction_history["date"].dt.strftime(
                "%Y-%m-%d"
            )
            st.dataframe(
                transaction_history[["ticker", "date", "quantity", "price", "action"]]
                .style.format({"quantity": "{:,.0f}", "price": "${:,.2f}"}),
                use_container_width=True,
                hide_index=True,
            )

with watchlist_tab:
    st.header("Watchlist")

    if "stock_data" not in st.session_state:
        st.info(
            f"{UPLOAD_FIRST_MESSAGE} You can still draft watchlist alerts, but last known prices need uploaded data."
        )

    with st.form("watchlist_form", clear_on_submit=True):
        ticker = st.text_input("Ticker Symbol")
        target_price = st.number_input(
            "Target Price",
            min_value=0.01,
            step=1.00,
            format="%.2f",
        )
        direction = st.radio("Alert Direction", ["Above", "Below"], horizontal=True)
        submitted = st.form_submit_button("Add to Watchlist")

        if submitted:
            cleaned_ticker = ticker.strip().upper()

            if not cleaned_ticker:
                st.warning("Enter a ticker symbol before adding it to the watchlist.")
            else:
                st.session_state["watchlist"].append(
                    {
                        "ticker": cleaned_ticker,
                        "target_price": target_price,
                        "direction": direction.lower(),
                    }
                )
                st.success(f"{cleaned_ticker} added to the watchlist.")

    if not st.session_state["watchlist"]:
        st.info("Add a ticker above to start building your watchlist.")
    else:
        latest_prices = {}

        if "stock_data" in st.session_state:
            stock_data = prepare_stock_data(st.session_state["stock_data"])
            if not stock_data.empty:
                latest_prices = (
                    stock_data.sort_values("date")
                    .groupby("ticker")
                    .tail(1)
                    .set_index("ticker")["price"]
                    .to_dict()
                )

        header_columns = st.columns([2, 2, 2, 2, 2, 1])
        header_columns[0].markdown("**Ticker**")
        header_columns[1].markdown("**Target Price**")
        header_columns[2].markdown("**Direction**")
        header_columns[3].markdown("**Last Known Price**")
        header_columns[4].markdown("**Alert Status**")
        header_columns[5].markdown("**Remove**")

        for index, item in enumerate(st.session_state["watchlist"]):
            item_ticker = item["ticker"]
            target = item["target_price"]
            item_direction = item["direction"]
            last_price = latest_prices.get(item_ticker)
            triggered = False

            if last_price is not None:
                if item_direction == "above":
                    triggered = last_price >= target
                else:
                    triggered = last_price <= target

            row_columns = st.columns([2, 2, 2, 2, 2, 1])
            row_columns[0].write(item_ticker)
            row_columns[1].write(f"${target:,.2f}")
            row_columns[2].write(item_direction.title())
            row_columns[3].write(
                f"${last_price:,.2f}" if last_price is not None else "Not in CSV"
            )

            if last_price is None:
                row_columns[4].write("No data")
            elif triggered:
                row_columns[4].warning("Triggered")
            else:
                row_columns[4].write("Not triggered")

            if row_columns[5].button("Remove", key=f"remove_watchlist_{index}"):
                st.session_state["watchlist"].pop(index)
                st.rerun()
