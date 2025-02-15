import streamlit as st
from datetime import datetime, timedelta
import random

# Page config
st.set_page_config(
    page_title="Ekko",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'page' not in st.session_state:
    st.session_state.page = 'Dashboard'
if 'chain' not in st.session_state:
    st.session_state.chain = 'Ethereum'
if 'alerts' not in st.session_state:
    st.session_state.alerts = [
        {
            "type": "Price Alert",
            "message": "AVAX dropped by 5% in the last hour",
            "time": "30 mins ago",
            "status": "warning",
            "icon": "📉",
            "priority": "High"
        },
        {
            "type": "Workflow Success",
            "message": "Weekly staking rewards claimed",
            "time": "1 hour ago",
            "status": "success",
            "icon": "✅",
            "priority": "Medium"
        },
        {
            "type": "Smart Contract",
            "message": "New proposal in governance contract",
            "time": "2 hours ago",
            "status": "info",
            "icon": "📜",
            "priority": "Low"
        }
    ]

# Import CSS file
with open("utils/style.css") as f:
    css = f.read()

# Apply CSS to the Streamlit app
st.markdown(css, unsafe_allow_html=True)

# Enhanced Alert Display
def show_enhanced_alert(alert):
    st.markdown(f"""
        <div class="alert-card alert-{alert['status']}">
            <div style="font-size: 1.5rem;">{alert['icon']}</div>
            <div style="flex-grow: 1;">
                <div style="display: flex; justify-content: space-between; align-items: start;">
                    <div>
                        <div style="font-weight: 500; margin-bottom: 0.25rem;">
                            {alert['type']}
                        </div>
                        <div style="color: #64748b;">
                            {alert['message']}
                        </div>
                    </div>
                    <div style="text-align: right;">
                        <span class="priority-badge priority-{alert['priority']}">
                            {alert['priority']}
                        </span>
                        <div style="color: #64748b; font-size: 0.875rem; margin-top: 0.5rem;">
                            {alert['time']}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)

# Dashboard Page
def show_dashboard():
    st.markdown('<h1 class="page-header">Dashboard</h1>', unsafe_allow_html=True)
    
    # Metrics
    col1, col2, col3 = st.columns(3)
    metrics = [
        {"label": "Total Balance", "value": "$45,231.89", "change": "+2.5% today"},
        {"label": "Active Workflows", "value": "12", "subtitle": "3 pending approval"},
        {"label": "AI Agents", "value": "5", "subtitle": "2 active now"}
    ]
    
    for col, metric in zip([col1, col2, col3], metrics):
        with col:
            st.metric(
                label=metric["label"],
                value=metric["value"],
                delta=metric.get("change", metric.get("subtitle"))
            )
    
    # Main content
    col1, col2 = st.columns([2,1])
    with col1:
        st.subheader("Recent Transactions")
        # Your existing transactions code
    
    with col2:
        st.subheader("Recent Alerts")
        for alert in st.session_state.alerts[:2]:
            show_enhanced_alert(alert)

# Wallets Page
def show_wallets():
    st.markdown('<h1 class="page-header">Wallets</h1>', unsafe_allow_html=True)
    
    col1, col2 = st.columns([2,1])
    with col1:
        st.markdown('<div class="filters-section">', unsafe_allow_html=True)
        st.subheader("Connected Wallets")
        wallets = [
            {"address": "0x1234...5678", "name": "Main Wallet", "balance": "12.5 AVAX"},
            {"address": "0x8765...4321", "name": "Trading Wallet", "balance": "5,000 USDC"}
        ]
        for wallet in wallets:
            st.markdown(f"""
                <div class="alert-card alert-info">
                    <div>
                        <div style="font-weight: 500;">{wallet['name']}</div>
                        <div style="color: #64748b;">{wallet['address']}</div>
                        <div style="margin-top: 0.5rem;">{wallet['balance']}</div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="filters-section">', unsafe_allow_html=True)
        st.subheader("Add New Wallet")
        with st.form("add_wallet"):
            st.text_input("Wallet Address (0x...)")
            st.text_input("Wallet Name (optional)")
            st.form_submit_button("Connect Wallet")
        st.markdown('</div>', unsafe_allow_html=True)

# Alerts Page
def show_alerts():
    st.markdown('<h1 class="page-header">Alerts</h1>', unsafe_allow_html=True)
    
    # Filters
    st.markdown('<div class="filters-section">', unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.selectbox("Filter by Type", ["All Types", "Price", "Workflow", "Smart Contract"])
    with col2:
        st.selectbox("Filter by Priority", ["All Priorities", "High", "Medium", "Low"])
    with col3:
        st.selectbox("Sort by", ["Newest First", "Oldest First", "Priority"])
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Create New Alert
    with st.expander("Create New Alert"):
        col1, col2 = st.columns(2)
        with col1:
            st.selectbox("Alert Type", ["Price Alert", "Workflow Alert", "Smart Contract Alert"])
            st.text_area("Condition")
        with col2:
            st.selectbox("Priority", ["High", "Medium", "Low"])
            st.multiselect("Notification Channels", ["Email", "Push", "Discord"])
        st.button("Create Alert")
    
    # Alert List
    for alert in st.session_state.alerts:
        show_enhanced_alert(alert)

# Workflows Page
def show_workflows():
    st.markdown('<h1 class="page-header">Workflows</h1>', unsafe_allow_html=True)
    
    # Create New Workflow
    with st.expander("Create New Workflow"):
        st.text_area("Describe your workflow")
        col1, col2 = st.columns(2)
        with col1:
            st.selectbox("Schedule", ["Manual", "Daily", "Weekly", "Monthly"])
        with col2:
            st.selectbox("Risk Level", ["Low", "Medium", "High"])
        st.button("Create Workflow")
    
    # Active Workflows
    workflows = [
        {"name": "DeFi Rebalance", "status": "Active", "last_run": "2 hours ago"},
        {"name": "Staking Rewards", "status": "Pending", "last_run": "1 day ago"}
    ]
    
    for workflow in workflows:
        st.markdown(f"""
            <div class="alert-card alert-info">
                <div style="display: flex; justify-content: space-between;">
                    <div>
                        <div style="font-weight: 500;">{workflow['name']}</div>
                        <div style="color: #64748b;">Last run: {workflow['last_run']}</div>
                    </div>
                    <div>
                        <span class="priority-badge priority-Medium">
                            {workflow['status']}
                        </span>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)

# AI Agents Page
def show_agents():
    st.markdown('<h1 class="page-header">AI Agents</h1>', unsafe_allow_html=True)
    
    # Create New Agent
    with st.expander("Create New Agent"):
        st.text_area("What should this agent do?")
        col1, col2 = st.columns(2)
        with col1:
            st.selectbox("Agent Type", ["Monitor", "Trade", "Analyze"])
        with col2:
            st.number_input("Max Budget (USD)", min_value=0.0)
        st.button("Create Agent")
    
    # Active Agents
    agents = [
        {"name": "Gas Price Monitor", "status": "Active", "type": "Monitor"},
        {"name": "DEX Arbitrage", "status": "Paused", "type": "Trade"}
    ]
    
    for agent in agents:
        st.markdown(f"""
            <div class="alert-card alert-info">
                <div style="display: flex; justify-content: space-between;">
                    <div>
                        <div style="font-weight: 500;">{agent['name']}</div>
                        <div style="color: #64748b;">Type: {agent['type']}</div>
                    </div>
                    <div>
                        <span class="priority-badge priority-Medium">
                            {agent['status']}
                        </span>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)

# Navigation and Main App
def main():
    # Sidebar Navigation
    with st.sidebar:
        st.title("⚡ Ekko")
        pages = {
            "Dashboard": "📊",
            "Wallets": "👛",
            "Alerts": "🔔",
            "Workflows": "⚡",
            "AI Agents": "🤖"
        }
        for page, icon in pages.items():
            if st.button(f"{icon} {page}"):
                st.session_state.page = page
    
    # Page Content
    if st.session_state.page == "Dashboard":
        show_dashboard()
    elif st.session_state.page == "Wallets":
        show_wallets()
    elif st.session_state.page == "Alerts":
        show_alerts()
    elif st.session_state.page == "Workflows":
        show_workflows()
    elif st.session_state.page == "AI Agents":
        show_agents()

if __name__ == "__main__":
    main()