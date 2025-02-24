# /Users/abrahamalaka/Projects/ekko-ce/streamlit/ekko-dash/app.py

import streamlit as st
from datetime import datetime, timedelta
from utils.models import Database, Wallet, Blockchain, Alert, Workflow, Agent, Cache  # Import Blockchain and Workflow models
import random
import os

# Page config
st.set_page_config(
    page_title="Ekko",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state if not already set
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
def show_wallets(blockchain_symbol):
    st.markdown('<h1 class="page-header">Wallets</h1>', unsafe_allow_html=True)
    
    col1, col2 = st.columns([2,1])
    with col1:
        st.markdown('<div class="filters-section">', unsafe_allow_html=True)
        st.subheader("Connected Wallets")
        
        # Fetch wallets from database
        db = Database()
        wallet_model = Wallet(db)
        fetched_wallets = wallet_model.get_all()
        if fetched_wallets:
            for wallet in fetched_wallets:
                st.markdown(f"""
                    <div class="alert-card alert-info">
                        <div>
                            <div style="font-weight: 500;">{wallet[3]}</div>
                            <div style="color: #64748b;">{wallet[2]}</div>
                            <div style="margin-top: 0.5rem;">{wallet[4]} {wallet[1]}</div>
                        </div>
                    </div>
                """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="filters-section">', unsafe_allow_html=True)
        st.subheader("Add New Wallet")
        
        # Fetch blockchains from the database
        blockchain_model = Blockchain(db)
        fetched_blockchains = blockchain_model.get_all()
        blockchain_options = {blockchain[2]: f"{blockchain[1]}" for blockchain in fetched_blockchains}
        
        with st.form("add_wallet"):
            wallet_address = st.text_input("Wallet Address (0x...)")
            wallet_name = st.text_input("Wallet Name (optional)")
            selected_chain = st.selectbox("Blockchain", list(blockchain_options.keys()), format_func=lambda x: blockchain_options[x])
            
            if st.form_submit_button("Connect Wallet"):
                # Insert new wallet into database
                wallet_data = {
                    'blockchain_symbol': selected_chain,
                    'address': wallet_address,
                    'name': wallet_name
                }
                wallet_model.insert(wallet_data)
                
                # Initialize cache
                cache = Cache()
                if cache.is_connected():
                    cache.cache_wallet(wallet_data)
                    st.success("Wallet added successfully!")
                else:
                    st.error("Failed to connect to Redis. Wallet caching is disabled.")
        
        st.markdown('</div>', unsafe_allow_html=True)

# Alerts Page
def show_alerts():
    st.markdown('<h1 class="page-header">Alerts</h1>', unsafe_allow_html=True)
    
    # Initialize database and models
    db = Database()
    alert_model = Alert(db)
    
    # Filters
    st.markdown('<div class="filters-section">', unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    with col1:
        filter_type = st.selectbox("Filter by Type", ["All Types", "Price", "Workflow", "Smart Contract"])
    with col2:
        filter_priority = st.selectbox("Filter by Priority", ["All Priorities", "High", "Medium", "Low"])
    with col3:
        sort_order = st.selectbox("Sort by", ["Newest First", "Oldest First", "Priority"])
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Create New Alert
    with st.expander("Create New Alert"):
        col1, col2 = st.columns(2)
        with col1:
            alert_type = st.selectbox("Alert Type", ["Price Alert", "Workflow Alert", "Smart Contract Alert"])
            condition = st.text_area("Condition")
        with col2:
            priority = st.selectbox("Priority", ["High", "Medium", "Low"])
            notification_channels = st.multiselect("Notification Channels", ["Email", "Push", "Discord"])
        if st.button("Create Alert"):
            # Insert new alert into database
            alert_data = {
                'type': alert_type,
                'message': condition,
                'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'status': 'warning',  # Default status, change as needed
                'icon': '',  # Default icon, change as needed
                'priority': priority
            }
            alert_model.insert(alert_data)
            
            # Initialize cache
            cache = Cache()
            if cache.is_connected():
                cache.cache_alert(alert_data)
                st.success("Alert created successfully!")
            else:
                st.error("Failed to connect to Redis. Alert caching is disabled.")
    
    # Alert List
    fetched_alerts = alert_model.get_all()
    for alert in fetched_alerts:
        show_enhanced_alert(alert)

# Workflows Page
def show_workflows():
    st.markdown('<h1 class="page-header">Workflows</h1>', unsafe_allow_html=True)
    
    # Initialize database and models
    db = Database()
    workflow_model = Workflow(db)
    
    # Create New Workflow
    with st.expander("Create New Workflow"):
        description = st.text_area("Describe your workflow")
        col1, col2 = st.columns(2)
        with col1:
            schedule = st.selectbox("Schedule", ["Manual", "Daily", "Weekly", "Monthly"])
        with col2:
            risk_level = st.selectbox("Risk Level", ["Low", "Medium", "High"])
        if st.button("Create Workflow"):
            # Insert new workflow into database
            workflow_data = {
                'name': description,  # Use the description as a temporary name, improve as needed
                'description': description,
                'schedule': schedule,
                'risk_level': risk_level,
                'status': 'Pending',  # Default status, change as needed
                'last_run': None  # No run yet
            }
            workflow_model.insert(workflow_data)
            
            # Initialize cache
            cache = Cache()
            if cache.is_connected():
                cache.cache_workflow(workflow_data)
                st.success("Workflow created successfully!")
            else:
                st.error("Failed to connect to Redis. Workflow caching is disabled.")
    
    # Active Workflows
    fetched_workflows = workflow_model.get_all()
    for workflow in fetched_workflows:
        st.markdown(f"""
            <div class="alert-card alert-info">
                <div style="display: flex; justify-content: space-between;">
                    <div>
                        <div style="font-weight: 500;">{workflow[1]}</div>
                        <div style="color: #64748b;">Last run: {workflow[7] if workflow[7] else 'Never'}</div>
                    </div>
                    <div>
                        <span class="priority-badge priority-Medium">
                            {workflow[5]}
                        </span>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)

# AI Agents Page
def show_agents():
    st.markdown('<h1 class="page-header">AI Agents</h1>', unsafe_allow_html=True)
    
    # Initialize database and models
    db = Database()
    agent_model = Agent(db)
    
    # Create New Agent
    with st.expander("Create New Agent"):
        description = st.text_area("What should this agent do?")
        col1, col2 = st.columns(2)
        with col1:
            agent_type = st.selectbox("Agent Type", ["Monitor", "Trade", "Analyze"])
        with col2:
            max_budget = st.number_input("Max Budget (USD)", min_value=0.0)
        if st.button("Create Agent"):
            # Insert new agent into database
            agent_data = {
                'name': description,  # Use the description as a temporary name, improve as needed
                'agent_type': agent_type,
                'description': description,
                'status': 'Pending',  # Default status, change as needed
                'max_budget': max_budget
            }
            agent_model.insert(agent_data)
            
            # Initialize cache
            cache = Cache()
            if cache.is_connected():
                cache.cache_agent(agent_data)
                st.success("Agent created successfully!")
            else:
                st.error("Failed to connect to Redis. Agent caching is disabled.")
    
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

    # Blockchain Selection Dropdown
    st.markdown("---")  # Add a separator line
    st.subheader("Select Blockchain")
    
    # Fetch blockchains from the database
    db = Database()
    blockchain_model = Blockchain(db)
    fetched_blockchains = blockchain_model.get_all()

    # Define the directory where your SVG icons are located
    icon_dir = os.path.join(os.getcwd(), "static", "icons")

    # Create a dictionary mapping each blockchain symbol to its corresponding SVG file path
    svg_paths = {
        'ETH': 'ethereum-cryptocurrency.svg',
        'AVAX': 'avalanche-avax.svg',
        'MATIC': 'polygon-eth.svg',  # Assuming you have the Polygon icon as `polygon-eth.svg`
        'BTC': 'bitcoin-cryptocurrency.svg'
    }

    # Create a dropdown for blockchain selection with SVG icons
    options = []
    for blockchain in fetched_blockchains:
        symbol, name = blockchain[2], blockchain[1]
        svg_file_path = os.path.join(icon_dir, svg_paths.get(symbol, ""))
        
        if os.path.exists(svg_file_path):
            with open(svg_file_path, 'r') as file:
                svg_content = file.read()
            
            options.append({
                "label": name,
                "value": symbol,
                "icon": svg_content
            })
    
    # Dropdown display function
    def format_option(option):
        return f'<span>{option["icon"]}</span> {option["label"]}'

    selected_chain = st.selectbox(
        "Blockchain",
        options=options,
        format_func=format_option,
        key="blockchain_select"
    )
    
    # Extract the selected blockchain symbol
    if selected_chain:
        st.session_state.chain = selected_chain['value']
        
    # Page Content
    if st.session_state.page == "Dashboard":
        show_dashboard()
    elif st.session_state.page == "Wallets":
        show_wallets(st.session_state.chain)
    elif st.session_state.page == "Alerts":
        show_alerts()
    elif st.session_state.page == "Workflows":
        show_workflows()
    elif st.session_state.page == "AI Agents":
        show_agents()

if __name__ == "__main__":
    main()
