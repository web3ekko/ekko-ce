import streamlit as st
from datetime import datetime, timedelta
import random
from utils.db import db, alert_model, cache
from utils.styles import apply_cell_style, inject_custom_css, get_status_color
import os
from openai import OpenAI
import requests
import logging
logger = logging.getLogger('alerts_form')
import re
import polars as pl
from typing import Optional

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

# Rule-based NL→Polars parser
def nl_to_polars(nl: str) -> Optional[str]:
    expr = "df.filter(pl.col('type')=='transfer')"
    # Above threshold
    m = re.search(r"(?:above|over)\s*\$?(\d+(?:\.\d+)?)", nl, re.I)
    if m:
        expr += f" & (pl.col('value').cast(pl.UInt64)/1e9 > {float(m.group(1))})"
    # Below threshold
    m = re.search(r"(?:below|under|less than)\s*\$?(\d+(?:\.\d+)?)", nl, re.I)
    if m:
        expr += f" & (pl.col('value').cast(pl.UInt64)/1e9 < {float(m.group(1))})"
    # Gas price filters
    m = re.search(r"gas (?:above|over|below|under)\s*(\d+)", nl, re.I)
    if m:
        op = ">" if "above" in m.group(0).lower() or "over" in m.group(0).lower() else "<"
        expr += f" & (pl.col('gas_price'){op}{int(m.group(1))})"
    # From/To address
    m = re.search(r"(?:to|from)\s*(0x[a-fA-F0-9]{40})", nl)
    if m:
        col = 'to' if m.group(0).lower().startswith('to') else 'from'
        expr += f" & (pl.col('{col}')=='{m.group(1).lower()}')"
    # Time-window filter
    m = re.search(r"in the last\s*(\d+)\s*(minute|hour|day)s?", nl, re.I)
    if m:
        num, unit = int(m.group(1)), m.group(2)
        if 'minute' in unit:
            expr += f" & (pl.col('created_at') >= datetime.now() - timedelta(minutes={num}))"
        elif 'hour' in unit:
            expr += f" & (pl.col('created_at') >= datetime.now() - timedelta(hours={num}))"
        elif 'day' in unit:
            expr += f" & (pl.col('created_at') >= datetime.now() - timedelta(days={num}))"
    # Count-based transfers
    m = re.search(r"more than\s*(\d+)\s*transfers", nl, re.I)
    if m:
        return f"{expr}.shape[0] > {int(m.group(1))}"
    # Fallback if only basic filter
    if expr == "df.filter(pl.col('type')=='transfer')":
        return None
    return expr

# Helper to clean up generated Polars expressions
def sanitize_polars_condition(expr: str) -> str:
    """Ensure Polars condition string is syntactically valid.

    - Collapses duplicate `.filter(pl.col('type') == 'transfer')` segments.
    - Balances parentheses by appending missing ')' characters.
    """
    if not expr:
        return expr

    # Collapse duplicated transfer-filter segments beyond the first
    transfer_filter = ".filter(pl.col('type') == 'transfer')"
    # Split once on the first occurrence, remove further duplicates
    first_idx = expr.find(transfer_filter)
    if first_idx != -1:
        head = expr[: first_idx + len(transfer_filter)]
        tail = expr[first_idx + len(transfer_filter) :]
        tail = tail.replace(transfer_filter, "")
        expr = head + tail

    # Balance parentheses
    diff = expr.count("(") - expr.count(")")
    if diff > 0:
        expr += ")" * diff

    # Replace unsupported dtype aliases (e.g., pl.UInt) with pl.UInt64
    expr = re.sub(r"pl\.UInt(?!\d)", "pl.UInt64", expr)
    expr = re.sub(r"pl\.uint(?!\d)", "pl.UInt64", expr, flags=re.IGNORECASE)

    # Ensure numeric casts/strict_cast are compared to make Boolean predicate
    # e.g. `(pl.col('value').strict_cast(UInt64))` -> `(pl.col('value').strict_cast(UInt64) > 0)`
    cast_pattern = re.compile(r"(pl\.col\('[^']+'\)\\.[a-zA-Z_]*?cast\([^\)]*\))(?!\s*[<>=])")
    expr = cast_pattern.sub(r"\1 > 0", expr)

    strict_cast_pattern = re.compile(r"(pl\.col\('[^']+'\)\\.strict_cast\([^\)]*\))(?!\s*[<>=])")
    expr = strict_cast_pattern.sub(r"\1 > 0", expr)

    return expr.strip()

# Inject custom CSS
inject_custom_css()

# Generate dummy alerts for display purposes
def generate_dummy_alerts(count=10):
    alert_types = ["Wallet Alert", "Price Alert", "Workflow Alert", "Smart Contract Alert", "Security Alert"]
    alert_messages = [
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
    logger.debug("show_create_alert_form called, session_state: %s", dict(st.session_state))
    # Initialize dynamic condition state
    if 'alert_condition' not in st.session_state:
        st.session_state['alert_condition'] = ""
    # Callback to update condition from NL query
    def update_alert_condition():
        nl = st.session_state.get('nl_query_input', '').strip()
        if nl:
            try:
                # Try rule-based first, else LLM
                condition = nl_to_polars(nl)
                if condition is None:
                    logger.debug("No rule match, falling back to LLM")
                    condition = llm_to_polars(nl)
                condition = sanitize_polars_condition(condition)
                st.session_state['alert_condition'] = condition
                logger.debug("condition generated: %s", condition)
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
                placeholder="E.g., Alert me when AVAX price drops below $20",
                height=100
            )
            # Wallet selection
            wallets_raw = db.get_connection().execute(
                "SELECT id, address, blockchain_symbol, name FROM wallet"
            ).fetchall()
            wallets = [
                {'id': r[0], 'address': r[1], 'blockchain_symbol': r[2], 'name': r[3]}
                for r in wallets_raw
            ]
            logger.debug("create_alert_form fetched wallets: %s", wallets)
            if not wallets:
                st.error("No wallets found. Please add a wallet first.")
                return
            # Show name (or address) and blockchain symbol
            wallet_options = [f"{w['name'] or w['address']} ({w['blockchain_symbol']})" for w in wallets]
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
            # Show full condition for debugging
            if st.session_state.get('alert_condition'):
                with st.expander("Full Condition", expanded=False):
                    st.code(st.session_state.get('alert_condition',''), language='python')
        
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
            logger.debug("create_alert_form submit clicked: %s", submit)
        
        if submit:
            logger.info("create_alert_form: submit branch entered")
            nlq = st.session_state.get('nl_query_input','').strip()
            logger.debug("nlq value: %s", nlq)
            if not nlq:
                st.error("Please enter a natural language query for your alert.")
            else:
                # Generate condition via LLM
                with st.spinner("Generating condition..."):
                    try:
                        # Try rule-based first, else LLM
                        condition = nl_to_polars(nlq)
                        if condition is None:
                            logger.debug("No rule match, falling back to LLM")
                            condition = llm_to_polars(nlq)
                        condition = sanitize_polars_condition(condition)
                        st.session_state['alert_condition'] = condition
                        logger.debug("condition generated: %s", condition)
                    except Exception as e:
                        st.session_state['alert_condition'] = ""
                        st.error(f"Error generating condition: {e}")
                        return
                # Build alert data payload
                import uuid, json
                alert_data = {
                    'id': str(uuid.uuid4()),
                    'wallet_id': wallet_id,
                    'blockchain_symbol': blockchain_symbol,
                    'type': alert_type,
                    'condition': st.session_state.get('alert_condition', ''),
                    'priority': priority,
                    'status': 'active',
                    'created_at': datetime.now()
                }
                # Log condition being saved for debugging
                logger.info("Saving alert %s with condition: %s", alert_data['id'], alert_data['condition'])
                # Save to DuckDB
                alert_model.insert(alert_data)
                # Save alert data to Redis for the ekko processor
                cache.cache_alert(alert_data)
                st.success("Alert created successfully!")
                logger.info("create_alert_form: Alert inserted successfully: %s condition=%s", alert_data.get('id'), alert_data['condition'])
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
    # Map alert types to icons
    type_icons = {
        "Price Alert": "💲",
        "Workflow Alert": "🔄",
        "Smart Contract Alert": "📜",
        "Security Alert": "🔒",
        "Wallet Alert": "👛",
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
        
        /* Grid row styling: background, border, padding, and shadow */
        div.row-widget.stHorizontal {
            background-color: #f9fafb;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 12px;
            margin-bottom: 16px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }
        
        /* Target each alert card container specifically */
        div.element-container div.stVerticalBlock {
            height: 165px;
            background-color: #FFF8E1;
            border-radius: 10px;
            padding: 12px;
            border: 1px solid #FFE082;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
            margin-bottom: 8px;
            position: relative;
            overflow: hidden;
        }
        
        /* Highlight active alerts */
        div.element-container div.stVerticalBlock:has(div.alert-active) {
            background-color: #d1fae5 !important;
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
                # Mark active alerts for CSS override
                if alert.get('status') == 'active':
                    st.markdown('<div class="alert-active" style="display:none;"></div>', unsafe_allow_html=True)
                with cols[j]:
                    # Title with icon and alert type
                    icon_html = type_icons.get(alert['type'], 'ℹ️')
                    st.markdown(f"<strong>{icon_html} {alert['type']}</strong>", unsafe_allow_html=True)
                    
                    # Display full condition string for debugging purposes
                    st.code(alert['message'], language='python')
                    
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
                        # Status tag
                        status_txt = alert.get('status', '').capitalize()
                        status_color = {
                            'Active': '#22c55e',
                            'Triggered': '#ef4444',
                            'Inactive': '#9ca3af'
                        }.get(status_txt, '#6b7280')
                        st.markdown(
                            f"<span style='font-size:12px; font-weight:600; color:{status_color};'>Status: {status_txt}</span>",
                            unsafe_allow_html=True,
                        )
                    
                    # View details button with click handler
                    button_key = f"view_alert_{alert['id']}"
                    
                    # Action buttons: toggle and delete
                    col_toggle, col_delete = st.columns([1, 1], gap="small")
                    with col_toggle:
                        label = "Deactivate" if alert['status'] == "active" else "Activate"
                        if st.button(label, key=f"alert_toggle_{alert['id']}"):
                            alert_model.update_status(alert['id'], "inactive" if alert['status'] == "active" else "active")
                            st.rerun()
                    with col_delete:
                        if st.button("Delete", key=f"alert_delete_{alert['id']}"):
                            alert_model.delete(alert['id'])
                            cache.delete_alert(alert['blockchain_symbol'], alert['wallet_id'])
                            st.rerun()
                    
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
    
    # Status indicator
    status_val = alert.get('status', '').capitalize()
    if status_val.lower() == 'triggered':
        st.error(f"Status: {status_val}")
    elif status_val.lower() == 'active':
        st.success(f"Status: {status_val}")
    else:
        st.info(f"Status: {status_val}")
    
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
    
    # Fetch alerts from DB first (authoritative record)
    with st.spinner("Loading alerts..."):
        alerts = []
        try:
            raw = alert_model.get_all()

            # Helper to safely parse timestamps
            def _parse_dt(val):
                if not val:
                    return None
                if isinstance(val, datetime):
                    return val
                for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
                    try:
                        return datetime.strptime(val, fmt)
                    except ValueError:
                        continue
                try:
                    return datetime.fromisoformat(val)
                except Exception:
                    return None

            for r in raw:
                created = _parse_dt(r[6]) or datetime.now()
                last = _parse_dt(r[7])

                # Base record from DB
                alert_rec = {
                    'id': r[0],
                    'wallet_id': r[1],
                    'blockchain_symbol': r[9],
                    'type': r[2],
                    'message': r[3],
                    'time': created,
                    'status': r[5] or 'inactive',
                    'icon': r[2] or 'ℹ️',
                    'priority': r[4] or 'Medium',
                    'created_at': created,
                    'last_triggered': last,
                }

                # Overlay status/last_triggered from Redis (if available)
                if cache.is_connected():
                    key = f"alert:{alert_rec['blockchain_symbol'].lower()}:{alert_rec['wallet_id']}"
                    cached = cache.get_cached_data(key) or {}
                    if cached:
                        alert_rec['status'] = cached.get('status', alert_rec['status'])
                        lt = _parse_dt(cached.get('last_triggered'))
                        if lt:
                            alert_rec['last_triggered'] = lt
                            # Use last_triggered as primary timestamp for display metrics
                            alert_rec['time'] = lt

                alerts.append(alert_rec)
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

def show_alert_grid_legacy(alerts):
    if not alerts:
        st.info("No alerts found. Create your first alert!")
        return
    # Map alert types to icons
    type_icons = {
        "Price Alert": "💲",
        "Workflow Alert": "🔄",
        "Smart Contract Alert": "📜",
        "Security Alert": "🔒",
        "Wallet Alert": "👛",
    }
    for alert in alerts:
        # Render alert card with action toggle
        col_content, col_action = st.columns([6, 1], gap="small")
        with col_content:
            icon_html = type_icons.get(alert['type'], 'ℹ️')
            st.markdown(f"""
            <div style="{apply_cell_style(alert['status'])}">
                <div style="display:flex; flex-direction:column; gap:4px;">
                    <div><strong>{icon_html} {alert['type']}</strong></div>
                    <div style="color:#64748b; font-size:0.875rem;">{alert['message']}</div>
                    <div><small>{alert['time']} ({get_time_ago(alert.get('created_at') or alert['time'])})</small></div>
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
                st.rerun()
            
            # Delete Alert Button
            if st.button("Delete", key=f"alert_delete_{alert['id']}"):
                alert_model.delete(alert['id'])
                cache.delete_alert(alert['blockchain_symbol'], alert['wallet_id'])
                st.rerun()
            
            # View details button with click handler
            if st.button("View Details", key=f"view_alert_{alert['id']}", use_container_width=True):
                st.session_state['selected_alert_id'] = alert['id']
                st.session_state['alert_view'] = 'detail'
                st.rerun()