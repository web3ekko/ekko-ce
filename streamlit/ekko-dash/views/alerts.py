import streamlit as st
from utils.models import Database, Alert, Cache
from datetime import datetime, timedelta
import random

# Initialize database and models
db = Database()
alert_model = Alert(db)
cache = Cache()

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
    with st.form("create_alert_form"):
        st.subheader("Create New Alert")
        
        col1, col2 = st.columns(2)
        with col1:
            alert_type = st.selectbox("Alert Type", ["Price Alert", "Workflow Alert", "Smart Contract Alert", "Security Alert", "Wallet Alert"])
            condition = st.text_area("Condition/Message", placeholder="E.g., Alert me when ETH price drops below $2,000")
        with col2:
            priority = st.selectbox("Priority", ["High", "Medium", "Low"])
            notification_channels = st.multiselect("Notification Channels", ["Email", "Push", "Discord"])
        
        # Form submission buttons
        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("Cancel", use_container_width=True):
                st.session_state['create_alert_form_open'] = False
                st.rerun()
        
        with col2:
            if st.form_submit_button("Create Alert", use_container_width=True):
                if condition:
                    # Prepare alert data
                    status_map = {"High": "error", "Medium": "warning", "Low": "info"}
                    icon_map = {
                        "Price Alert": "📊",
                        "Workflow Alert": "🔄",
                        "Smart Contract Alert": "📝",
                        "Security Alert": "🔐",
                        "Wallet Alert": "👛"
                    }
                    
                    alert_data = {
                        'type': alert_type,
                        'message': condition,
                        'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'status': status_map.get(priority, "warning"),
                        'icon': icon_map.get(alert_type, "ℹ️"),
                        'priority': priority
                    }
                    
                    # Insert alert into database
                    try:
                        alert_model.insert(alert_data)
                        
                        if cache.is_connected():
                            try:
                                cache.cache_alert(alert_data)
                            except Exception as e:
                                st.warning(f"Alert created but not cached: {str(e)}")
                        
                        st.success("Alert created successfully!")
                    except Exception as e:
                        st.error(f"Failed to create alert: {str(e)}")
                    
                    # Close the form
                    st.session_state['create_alert_form_open'] = False
                    st.rerun()
                else:
                    st.error("Please enter an alert condition/message")

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
    
    # Add some CSS for alert styling
    st.markdown("""
    <style>
        /* Card wrapper for consistent spacing */
        .alert-wrapper {
            padding: 3px;
        }
        
        /* Priority tag styles */
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
    </style>
    """, unsafe_allow_html=True)
    
    # Calculate how many rows we need (4 alerts per row)
    alert_count = len(alerts)
    row_count = (alert_count + 3) // 4  # +3 to account for possible Add Alert card
    
    for row in range(row_count):
        # Create a row with 4 columns
        cols = st.columns(4)
        
        # Fill the columns with alert cards
        for col_idx in range(4):
            alert_idx = row * 4 + col_idx
            
            # Add "Create Alert" card as the last item
            if alert_idx == alert_count:
                with cols[col_idx]:
                    # Wrapper for consistent spacing
                    st.markdown('<div class="alert-wrapper">', unsafe_allow_html=True)
                    
                    # Create card with button
                    with st.container():
                        st.markdown("##### Create New Alert")
                        st.markdown("➕")
                        st.button("Add Alert", key="add_alert_grid", use_container_width=True,
                                 on_click=lambda: setattr(st.session_state, 'create_alert_form_open', True))
                    
                    st.markdown('</div>', unsafe_allow_html=True)
            
            # Display an alert if we have one for this position
            elif alert_idx < alert_count:
                alert = alerts[alert_idx]
                
                with cols[col_idx]:
                    # Wrapper for consistent spacing
                    st.markdown('<div class="alert-wrapper">', unsafe_allow_html=True)
                    
                    # Create a card-like container
                    with st.container():
                        # Title with icon and alert type
                        icon = alert.get('icon', status_icons.get(alert.get('status', 'info'), 'ℹ️'))
                        st.markdown(f"{icon} **{alert['type']}**")
                        
                        # Alert message (truncated if too long)
                        message = alert['message']
                        if len(message) > 60:
                            message = message[:57] + "..."
                        st.write(message)
                        
                        # Time ago and priority in columns
                        time_col, priority_col = st.columns([3, 2])
                        
                        with time_col:
                            time_ago = get_time_ago(alert.get('created_at') or alert.get('time'))
                            st.caption(f"{time_ago}")
                        
                        with priority_col:
                            priority = alert.get('priority', 'Medium')
                            priority_color = priority_colors.get(priority, "#6b7280")
                            st.markdown(f"""
                            <span class="priority-tag priority-{priority}">
                                {priority}
                            </span>
                            """, unsafe_allow_html=True)
                        
                        # View button
                        if st.button("View Details", key=f"view_alert_{alert['id']}", use_container_width=True):
                            # In a real implementation, this would show alert details
                            st.session_state['selected_alert_id'] = alert['id']
                            st.session_state['alert_view'] = 'detail'
                            st.rerun()
                    
                    st.markdown('</div>', unsafe_allow_html=True)

# Alert detail view
def show_alert_detail(alert_id, alerts):
    # Find the selected alert
    alert = next((a for a in alerts if a['id'] == alert_id), None)
    
    if not alert:
        st.error("Alert not found")
        return
    
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
    
    # Page title based on current view
    if st.session_state['alert_view'] == 'grid':
        st.markdown('<h1 class="page-header">Alerts</h1>', unsafe_allow_html=True)
    else:
        st.markdown('<h1 class="page-header">Alert Details</h1>', unsafe_allow_html=True)
    
    # Try to fetch alerts from database
    try:
        fetched_alerts = alert_model.get_all()
        
        # Process fetched alerts safely
        alerts = []
        if fetched_alerts:
            for alert_data in fetched_alerts:
                # Create dictionary with safe defaults
                alert = {
                    'id': str(alert_data[0]) if len(alert_data) > 0 else "unknown",
                    'type': str(alert_data[1]) if len(alert_data) > 1 else "Alert",
                    'message': str(alert_data[2]) if len(alert_data) > 2 else "",
                    'time': str(alert_data[3]) if len(alert_data) > 3 else "",
                    'status': str(alert_data[4]) if len(alert_data) > 4 else "info",
                    'icon': str(alert_data[5]) if len(alert_data) > 5 and alert_data[5] else "ℹ️",
                    'priority': str(alert_data[6]) if len(alert_data) > 6 else "Medium",
                    'created_at': alert_data[7] if len(alert_data) > 7 else None,
                    'updated_at': alert_data[8] if len(alert_data) > 8 else None
                }
                alerts.append(alert)
    except Exception as e:
        # If there's any error fetching or processing alert data
        st.warning(f"Using sample data. Database error: {str(e)}")
        alerts = []
    
    # If fewer than 8 alerts, add dummy alerts
    if len(alerts) < 8:
        # Calculate how many dummy alerts we need
        needed_dummy_count = 8 - len(alerts)
        # Generate dummy alerts with high IDs to avoid conflicts with real ones
        dummy_alerts = generate_dummy_alerts(count=needed_dummy_count)
        
        # Use high starting ID to avoid conflicts
        starting_id = 10000
        for i, dummy_alert in enumerate(dummy_alerts):
            dummy_alert['id'] = starting_id + i
            alerts.append(dummy_alert)
    
    # Show appropriate view based on session state
    if st.session_state['alert_view'] == 'grid':
        # Filters section
        st.markdown('<div style="background-color: #f9fafb; padding: 1rem; border-radius: 8px; margin-bottom: 1rem;">', unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        
        with col1:
            filter_type = st.selectbox("Filter by Type", ["All Types", "Price Alert", "Workflow Alert", "Smart Contract Alert", "Security Alert", "Wallet Alert"])
        
        with col2:
            filter_priority = st.selectbox("Filter by Priority", ["All Priorities", "High", "Medium", "Low"])
        
        with col3:
            sort_order = st.selectbox("Sort by", ["Newest First", "Oldest First", "Priority (High to Low)"])
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Add New Alert Button
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.subheader("Alert Dashboard")
            st.write("Monitor and manage your blockchain alerts.")
        
        with col2:
            st.write("")  # Add some space
            if st.button("➕ Add New Alert", use_container_width=True, key="add_new_alert_header"):
                st.session_state['create_alert_form_open'] = True
                st.rerun()
        
        # Show Create Alert Form if the button was clicked
        if st.session_state.get('create_alert_form_open', False):
            show_create_alert_form()
        
        # Apply filters (if not "All")
        if filter_type != "All Types":
            alerts = [a for a in alerts if a['type'] == filter_type]
        
        if filter_priority != "All Priorities":
            alerts = [a for a in alerts if a['priority'] == filter_priority]
        
        # Apply sorting
        if sort_order == "Newest First":
            alerts.sort(key=lambda x: x.get('created_at') or x.get('time', ''), reverse=True)
        elif sort_order == "Oldest First":
            alerts.sort(key=lambda x: x.get('created_at') or x.get('time', ''))
        elif sort_order == "Priority (High to Low)":
            priority_order = {"High": 0, "Medium": 1, "Low": 2}
            alerts.sort(key=lambda x: priority_order.get(x.get('priority', 'Medium'), 1))
        
        # Show alert grid
        show_alert_grid(alerts)
    
    elif st.session_state['alert_view'] == 'detail':
        # Show alert detail view for the selected alert
        show_alert_detail(st.session_state['selected_alert_id'], alerts)