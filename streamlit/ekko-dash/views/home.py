import streamlit as st
from utils.alerts import show_enhanced_alerts
from utils.db import db, alert_model, agent_model
from utils.styles import inject_custom_css
import pandas as pd

def show_dashboard():
    inject_custom_css()
    st.markdown('<h1 class="page-header">Dashboard</h1>', unsafe_allow_html=True)
    
    conn = db.get_connection()
    total_balance = conn.execute("SELECT COALESCE(SUM(balance),0) FROM wallet").fetchone()[0]
    num_wallets = conn.execute("SELECT COUNT(*) FROM wallet").fetchone()[0]
    num_alerts = len(alert_model.get_all())
    num_agents = len(agent_model.get_all())
    
    col1, col2, col3, col4 = st.columns(4)
    for col, (label, value) in zip([col1, col2, col3, col4], [
        ("Total Balance", f"${total_balance:.2f}"),
        ("Wallets", num_wallets),
        ("Active Alerts", num_alerts),
        ("AI Agents", num_agents),
    ]):
        col.metric(label=label, value=value)
    
    # Display wallet balances
    st.markdown("### Wallet Balances")
    wallets = conn.execute(
        "SELECT blockchain_symbol, address, balance FROM wallet ORDER BY balance DESC"
    ).fetchall()
    df_wallets = pd.DataFrame(wallets, columns=["Chain", "Address", "Balance"])
    st.dataframe(df_wallets)
    
    # Display recent alerts
    st.markdown("### Recent Alerts")
    recent_alerts = alert_model.get_all()[:5]
    for alert in recent_alerts:
        show_enhanced_alerts(alert)