import streamlit as st
from datetime import datetime, timedelta
import random
from utils.db import db, alert_model, cache
from utils.styles import apply_cell_style, inject_custom_css, get_status_color
import os
from openai import OpenAI
import requests

# Configure LLM provider (local LMStudio or remote OpenAI) via env vars
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()
if LLM_PROVIDER == "local":
    os.environ["OPENAI_API_BASE"] = os.getenv("LMSTUDIO_API_BASE", "http://host.docker.internal:1234/v1")
    os.environ["OPENAI_API_KEY"] = os.getenv("LMSTUDIO_API_KEY", "")
else:
    os.environ["OPENAI_API_BASE"] = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
    os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY", "")

client = OpenAI()

# Helper to convert NL query to Polars condition via OpenAI
def llm_to_polars(nl_query: str) -> str:
    prompt = """
Generate a Polars expression on DataFrame df for **wallet transfers only**.
Assume df has:
- 'type' (transaction type),
- 'value' (in wei).
Start with df.filter(pl.col('type') == 'transfer') and add conditions from the user query.
Return only the final expression, no explanation.
Example:
df.filter((pl.col('type') == 'transfer') & (pl.col('value').cast(pl.UInt64)/1e9 > 1)).shape[0] > 0
"""
    # Select model based on provider
    model_name = os.getenv("LMSTUDIO_MODEL", "gpt4all") if LLM_PROVIDER == "local" else os.getenv("OPENAI_MODEL", "gpt-4")
    
    # Local LMStudio via direct HTTP
    if LLM_PROVIDER == "local":
        base = os.getenv("LMSTUDIO_API_BASE", os.getenv("OPENAI_API_BASE", "http://host.docker.internal:1234/v1"))
        url = base.rstrip("/") + "/chat/completions"
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": nl_query},
            ],
            "temperature": 0,
            "max_tokens": 64,
        }
        resp = requests.post(url, json=payload)
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"].strip()
        # Extract only the expression starting with df.filter
        start = raw.find("df.filter")
        if start != -1:
            expr = raw[start:].splitlines()[0].strip()
            return expr
        return raw
    # Remote OpenAI
    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": nl_query},
        ],
        temperature=0,
        max_tokens=64,
    )
    raw = response.choices[0].message.content.strip()
    # Extract only the expression starting with df.filter
    start = raw.find("df.filter")
    if start != -1:
        expr = raw[start:].splitlines()[0].strip()
        return expr
    return raw

# Inject custom CSS
inject_custom_css()

# Generate dummy alerts for display purposes
def generate_dummy_alerts(count=10):
    alert_types = ["Price Alert", "Workflow Alert", "Smart Contract Alert", "Security Alert", "Wallet Alert"]
    alert_messages = [
        "ETH price dropped below $2,000",
        "BTC price increased by 5% in the last hour",
        "Workflow 'Portfolio Rebalance' completed successfully",
        "Smart contract approval detected for token XYZ",
        "Suspicious transaction detected in wallet",
        "Gas prices are unusually high right now",
        "New airdrop detected for wallet 0x123",
        "DEX liquidity pool rewards available to claim",
        "Weekly portfolio report generated",
        "Whale movement detected on BTC"
    ]
    alert_icons = ["📉", "📈", "🔄", "📝", "🔐", "⛽", "🎁", "💧", "📊", "🐋"]
    
    dummy_alerts = []
    now = datetime.now()
    
    for i in range(count):
        # Pick random properties for this alert
        alert_type_idx = i % len(alert_types)
        alert_type = alert_types[alert_type_idx]
        message = alert_messages[i % len(alert_messages)]
        icon = alert_icons[i % len(alert_icons)]
        
        # Randomize times within the last 7 days
        hours_ago = random.randint(0, 168)  # Up to 7 days ago (168 hours)
        time_ago = now - timedelta(hours=hours_ago)
        
        # Randomize status and priority
        status = random.choice(["warning", "success", "info", "error"])
        priority = random.choice(["High", "Medium", "Low"])
        
        # Create the alert object
        dummy_alerts.append({
            'id': i + 1,
            'type': alert_type,
            'message': message,
            'time': time_ago.strftime('%Y-%m-%d %H:%M:%S'),
            'status': status,
            'icon': icon,
            'priority': priority,
            'created_at': time_ago,
            'updated_at': time_ago,
        })
    
    # Sort alerts by created_at (newest first)
    dummy_alerts.sort(key=lambda x: x['created_at'], reverse=True)
    return dummy_alerts

# Function to get relative time string (e.g., "2 hours ago")
def get_time_ago(timestamp_str):
    if not timestamp_str:
        return "Unknown time"
    
    try:
        # Convert string timestamp to datetime
        if isinstance(timestamp_str, str):
            timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
        else:
            timestamp = timestamp_str
            
        now = datetime.now()
        diff = now - timestamp
        
        if diff.days > 30:
            return f"{diff.days // 30} months ago"
        elif diff.days > 0:
            return f"{diff.days} days ago"
        elif diff.seconds > 3600:
            return f"{diff.seconds // 3600} hours ago"
        elif diff.seconds > 60:
            return f"{diff.seconds // 60} minutes ago"
        else:
            return "Just now"
    except Exception:
        return "Unknown time"

# Function to show alert form
def show_create_alert_form():
    # Initialize dynamic condition state
    if 'alert_condition' not in st.session_state:
        st.session_state['alert_condition'] = ""
    # Callback to update condition from NL query
    def update_alert_condition():
        nl = st.session_state.get('nl_query_input', '').strip()
        if nl:
            try:
                st.session_state['alert_condition'] = llm_to_polars(nl)
            except Exception as e:
                st.session_state['alert_condition'] = ""
                st.error(f"Error generating condition: {e}")
        else:
            st.session_state['alert_condition'] = ""
    
    # Add warm background styling to form
    st.markdown("""
    <style>
        div[data-testid="stForm"] {
            background-color: #FFF8E1;
            padding: 20px;
            border-radius: 10px;
            border: 1px solid #FFE082;
        }
    </style>
    """, unsafe_allow_html=True)
    
    with st.form("create_alert_form"):
        st.subheader("Create New Alert")
        st.caption("Define your alert conditions and notification preferences.")
        
        form_col1, form_col2 = st.columns([1,1])
        with form_col1:
            alert_type = st.selectbox(
                "Alert Type", ["Price Alert","Workflow Alert","Smart Contract Alert","Security Alert","Wallet Alert"]
            )
            nl_query = st.text_area(
                "Natural Language Query", 
                key="nl_query_input",
                placeholder="E.g., Alert me when ETH price drops below $2,000",
                height=100
            )
            # Wallet selection
            wallets_raw = db.get_connection().execute(
                "SELECT id, address, blockchain_symbol FROM wallet"
            ).fetchall()
            wallets = [dict(r) for r in wallets_raw]
            if not wallets:
                st.error("No wallets found. Please add a wallet first.")
                return
            wallet_options = [f"{w['blockchain_symbol']}:{w['address']}" for w in wallets]
            wallet_choice = st.selectbox("Wallet", wallet_options)
            selected_wallet = wallets[wallet_options.index(wallet_choice)]
            wallet_id = selected_wallet["id"]
            blockchain_symbol = selected_wallet["blockchain_symbol"]
        with form_col2:
            priority = st.selectbox("Priority", ["High","Medium","Low"])
            st.text_area(
                "Condition", 
                value=st.session_state.get('alert_condition',''),
                height=100,
                disabled=True
            )
        
        # Review section
        st.caption("Review inputs before submitting.")
        st.divider()
        
        # Form submission buttons
        col_cancel, col_submit = st.columns(2)
        with col_cancel:
            if st.form_submit_button("Cancel", use_container_width=True):
                st.session_state['create_alert_form_open'] = False
                st.rerun()
        
        with col_submit:
            submit = st.form_submit_button("Create Alert", use_container_width=True)
        
        if submit:
            nlq = st.session_state.get('nl_query_input','').strip()
            if not nlq:
                st.error("Please enter a natural language query for your alert.")
            else:
                # Generate condition via LLM
                with st.spinner("Generating condition..."):
                    try:
                        condition = llm_to_polars(nlq)
                        st.session_state['alert_condition'] = condition
                    except Exception as e:
                        st.error(f"Error generating condition: {e}")
                        return
                if not condition:
                    st.error("Failed to generate condition.")
                    return
        
                status_map = {"High":"error","Medium":"warning","Low":"info"}
                icon_map = {"Price Alert":"📊","Workflow Alert":"🔄","Smart Contract Alert":"📝","Security Alert":"🔐","Wallet Alert":"👛"}
                alert_data = {
                    'wallet_id': wallet_id,
                    'blockchain_symbol': blockchain_symbol,
                    'type': alert_type,
                    'message': st.session_state['nl_query_input'],
                    'condition': condition,
                    'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'status': status_map.get(priority,"warning"),
                    'icon': icon_map.get(alert_type,"ℹ️"),
                    'priority': priority,
                    'notification_topic': None
                }
        
                try:
                    alert_model.insert(alert_data)
                    if cache.is_connected():
                        try:
                            cache.cache_alert(alert_data)
                        except Exception as e:
                            st.warning(f"Alert created but not cached: {e}")
                    st.success("Alert created successfully!")
                except Exception as e:
                    st.error(f"Failed to create alert: {e}")
        
                st.session_state['create_alert_form_open'] = False
                st.rerun()

# Function to display alert grid
def show_alert_grid(alerts):
    # Define color coding for priorities
    priority_colors = {
        "High": "#ef4444",  # Red
        "Medium": "#f59e0b",  # Amber
        "Low": "#3b82f6"   # Blue
    }
    
    # Define emoji/icon for status
    status_icons = {
        "warning": "⚠️",
        "error": "🚨",
        "info": "ℹ️",
        "success": "✅"
    }
    
    # Add CSS for alert styling with fixed heights and better alignment
    st.markdown("""
    <style>
        /* Fix for the grid layout and card alignment */
        div.row-widget.stHorizontal > div {
            padding: 0 3px;
            box-sizing: border-box;
            margin-bottom: 8px;
        }
        
        /* Target each alert card container specifically */
        div.element-container div.stVerticalBlock {
            height: 165px;
            background-color: #FFF8E1;
            border-radius: 10px;
            padding: 12px;
            border: 1px solid #FFE082;
            margin-bottom: 8px;
            position: relative;
            overflow: hidden;
        }
        
        /* Style for the priority tag */
        .priority-tag {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 500;
        }
        
        .priority-High {
            background-color: #fef2f2;
            color: #ef4444;
        }
        
        .priority-Medium {
            background-color: #fffbeb;
            color: #f59e0b;
        }
        
        .priority-Low {
            background-color: #eff6ff;
            color: #3b82f6;
        }
        
        /* Remove margins that cause misalignment */
        div.element-container div.stVerticalBlock div {
            margin-top: 0 !important;
            margin-bottom: 0 !important;
        }
        
        /* Make buttons appear at the bottom */
        div.element-container div.stVerticalBlock div.stButton {
            position: absolute;
            bottom: 12px;
            left: 12px;
            right: 12px;
        }
        
        /* Fix message height to exactly 2 lines */
        .alert-message {
            height: 40px !important;
            line-height: 20px !important;
            overflow: hidden !important;
            display: -webkit-box !important;
            -webkit-line-clamp: 2 !important;
            -webkit-box-orient: vertical !important;
            margin-bottom: 10px !important;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Create rows of alerts, 4 per row
    total_alerts = len(alerts)
    
    # Use evenly spaced grid layout
    for i in range(0, total_alerts, 4):
        # Create a new row
        cols = st.columns(4)
        
        # Fill the row with alert cards (up to 4)
        for j in range(4):
            idx = i + j
            if idx < total_alerts:
                alert = alerts[idx]
                with cols[j]:
                    # Title with icon and alert type
                    icon = alert.get('icon', status_icons.get(alert.get('status', 'info'), 'ℹ️'))
                    st.markdown(f"<strong>{icon} {alert['type']}</strong>", unsafe_allow_html=True)
                    
                    # Alert message (always 2 lines with CSS control)
                    message = alert['message']
                    if len(message) > 65:  # Slightly longer to fill 2 lines
                        message = message[:62] + "..."
                        
                    # Use a special class to ensure 2-line height
                    st.markdown(f'<div class="alert-message">{message}</div>', unsafe_allow_html=True)
                    
                    # Time ago and priority in columns
                    col1, col2 = st.columns([3, 2])
                    with col1:
                        time_ago = get_time_ago(alert.get('created_at') or alert.get('time'))
                        st.caption(f"{time_ago}")
                    
                    with col2:
                        priority = alert.get('priority', 'Medium')
                        st.markdown(f"""
                        <span class="priority-tag priority-{priority}">
                            {priority}
                        </span>
                        """, unsafe_allow_html=True)
                    
                    # Create a unique key for each button
                    button_key = f"view_alert_{alert['id']}"
                    
                    # View details button with click handler
                    if st.button("View Details", key=button_key, use_container_width=True):
                        st.session_state['selected_alert_id'] = alert['id']
                        st.session_state['alert_view'] = 'detail'
                        st.rerun()

# Alert detail view
def show_alert_detail(alert_id, alerts):
    # Find the selected alert
    alert = next((a for a in alerts if a['id'] == alert_id), None)
    
    if not alert:
        st.error("Alert not found")
        return
    
    # Apply warm styling to detail view
    st.markdown("""
    <style>
        div.element-container div.stVerticalBlock {
            background-color: #FFF8E1;
            border-radius: 10px;
            padding: 15px;
            border: 1px solid #FFE082;
            margin-bottom: 15px;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Back button
    if st.button("← Back to Alerts", use_container_width=False):
        st.session_state['alert_view'] = 'grid'
        st.rerun()
    
    # Alert header
    st.subheader(f"{alert.get('icon', '')} {alert['type']}")
    
    # Priority indicator
    priority = alert.get('priority', 'Medium')
    if priority == "High":
        st.error(f"Priority: {priority}")
    elif priority == "Medium":
        st.warning(f"Priority: {priority}")
    else:
        st.info(f"Priority: {priority}")
    
    # Alert message
    st.markdown("### Message")
    st.write(alert['message'])
    
    # Time information
    st.markdown("### Time")
    time_str = alert.get('time', '')
    time_ago = get_time_ago(alert.get('created_at') or time_str)
    st.write(f"{time_str} ({time_ago})")
    
    # Action buttons
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.button("Mark as Resolved", use_container_width=True)
    
    with col2:
        st.button("Snooze Alert", use_container_width=True)
    
    with col3:
        st.button("Delete", use_container_width=True, type="primary")
    
    # Additional information (placeholder)
    st.markdown("### Related Information")
    st.info("This is a placeholder for additional information related to this alert.")

# Main alerts display function
def show_alerts():
    # Initialize session state for alert navigation
    if 'alert_view' not in st.session_state:
        st.session_state['alert_view'] = 'grid'
    if 'selected_alert_id' not in st.session_state:
        st.session_state['selected_alert_id'] = None
    if 'create_alert_form_open' not in st.session_state:
        st.session_state['create_alert_form_open'] = False
    
    # Fetch alerts from db
    with st.spinner("Loading alerts..."):
        try:
            raw = alert_model.get_all()
            alerts = []
            for r in raw:
                alerts.append({
                    'id': r[0], 'type': r[1], 'message': r[2], 'time': r[3],
                    'status': r[4], 'icon': r[5] or 'ℹ️', 'priority': r[6],
                    'created_at': r[7], 'last_triggered': r[8]
                })
        except Exception as e:
            st.warning(f"Using sample alerts: {str(e)}")
            alerts = generate_dummy_alerts(count=10)
    
    # Page header and Add New Alert button
    header_col1, header_col2 = st.columns([3,1])
    with header_col1:
        st.subheader("Alerts Dashboard")
        st.write("Manage and monitor all your alerts in one place.")
    with header_col2:
        if st.button("➕ Add New Alert", use_container_width=True, key="header_add_alert"):
            st.session_state['create_alert_form_open'] = True
            st.session_state['alert_view'] = 'grid'
            st.rerun()
    
    # Show create-alert form if open
    if st.session_state.get('create_alert_form_open'):
        show_create_alert_form()
    
    # Search Alerts
    search_text = st.text_input("Search Alerts", placeholder="Type to search...", key="alert_search")
    
    # Metrics Summary
    st.markdown(f'<h1 class="page-header">Alerts</h1>', unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Alerts", len(alerts))
    cutoff = datetime.now() - timedelta(hours=1)
    recent = sum(1 for a in alerts if a.get('last_triggered') and a['last_triggered'] >= cutoff)
    col2.metric("Triggered Last 1h", recent)
    col3.metric("Avg Resolution", "N/A")
    
    if st.session_state['alert_view'] == 'grid':
        # Apply search filter
        alerts_filtered = alerts
        if search_text:
            alerts_filtered = [a for a in alerts_filtered if search_text.lower() in a['message'].lower()]
        show_alert_grid(alerts_filtered)
    else:
        # Detail view with tabs
        tabs = st.tabs(["Overview", "History", "Related Data"])
        with tabs[0]:
            show_alert_detail(st.session_state['selected_alert_id'], alerts)
        with tabs[1]:
            st.info("Alert history will appear here.")
        with tabs[2]:
            st.info("Related chain data will appear here.")

def show_alert_grid(alerts):
    if not alerts:
        st.info("No alerts found. Create your first alert!")
        return
    for alert in alerts:
        # Render alert card with action toggle
        col_content, col_action = st.columns([6, 1], gap="small")
        with col_content:
            st.markdown(f"""
            <div style="{apply_cell_style(alert['status'])}">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <strong>{alert['icon']} {alert['message']}</strong><br/>
                        <small>{alert['time']} ({get_time_ago(alert.get('created_at') or alert['time'])})</small>
                    </div>
                    <div>
                        <span class="status-badge" style="background-color:{get_status_color(alert['status'])}; color:#fff;">
                            {alert['status'].title()}
                        </span>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        with col_action:
            # Toggle active/inactive status
            label = "Deactivate" if alert['status'] == "active" else "Activate"
            new_status = "inactive" if alert['status'] == "active" else "active"
            if st.button(label, key=f"alert_toggle_{alert['id']}"):
                alert_model.update_status(alert['id'], new_status)
                st.experimental_rerun()

def show_alert_detail(alert_id, alerts):
    # Find the selected alert
    alert = next((a for a in alerts if a['id'] == alert_id), None)
    
    if not alert:
        st.error("Alert not found")
        return
    
    # Apply warm styling to detail view
    st.markdown("""
    <style>
        div.element-container div.stVerticalBlock {
            background-color: #FFF8E1;
            border-radius: 10px;
            padding: 15px;
            border: 1px solid #FFE082;
            margin-bottom: 15px;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Back button
    if st.button("← Back to Alerts", use_container_width=False):
        st.session_state['alert_view'] = 'grid'
        st.rerun()
    
    # Alert header
    st.subheader(f"{alert.get('icon', '')} {alert['type']}")
    
    # Priority indicator
    priority = alert.get('priority', 'Medium')
    if priority == "High":
        st.error(f"Priority: {priority}")
    elif priority == "Medium":
        st.warning(f"Priority: {priority}")
    else:
        st.info(f"Priority: {priority}")
    
    # Alert message
    st.markdown("### Message")
    st.write(alert['message'])
    
    # Time information
    st.markdown("### Time")
    time_str = alert.get('time', '')
    time_ago = get_time_ago(alert.get('created_at') or time_str)
    st.write(f"{time_str} ({time_ago})")
    
    # Action buttons
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.button("Mark as Resolved", use_container_width=True)
    
    with col2:
        st.button("Snooze Alert", use_container_width=True)
    
    with col3:
        st.button("Delete", use_container_width=True, type="primary")
    
    # Additional information (placeholder)
    st.markdown("### Related Information")
    st.info("This is a placeholder for additional information related to this alert.")