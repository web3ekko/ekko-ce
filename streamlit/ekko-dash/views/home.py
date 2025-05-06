import streamlit as st
from utils.alerts import show_enhanced_alerts
from utils.db import db, alert_model, agent_model
from utils.styles import inject_custom_css
import pandas as pd
from views.wallets import show_wallet_grid

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
    
    # Display wallet balances as grid
    st.markdown("### Wallet Balances")
    raw_wallets = conn.execute(
        "SELECT id, name, blockchain_symbol, address, balance FROM wallet ORDER BY balance DESC"
    ).fetchall()
    wallets_list = [
        {
            'id': r[0],
            'name': r[1] or r[3],
            'blockchain_symbol': r[2],
            'address': r[3],
            'balance': float(r[4] or 0)
        }
        for r in raw_wallets
    ]
    show_wallet_grid(wallets_list, cols=3)
    
    # Display recent alerts
    st.markdown("### Recent Alerts")
    raw = alert_model.get_all()[:5]
    # Map raw rows to dict for enhanced display
    for r in raw:
        alert = {
            'id': r[0],
            'type': r[2],
            'message': r[3],
            'time': str(r[6]),
            'status': r[5],
            'icon': 'ℹ️',
            'priority': 'Medium'
        }
        show_enhanced_alerts(alert)