import streamlit as st
from utils.models import Database, Alert, Cache
from utils.alerts import show_enhanced_alerts
from datetime import datetime

# Initialize database and models
db = Database()
alert_model = Alert(db)
cache = Cache()

def show_alerts():
    st.markdown('<h1 class="page-header">Alerts</h1>', unsafe_allow_html=True)
    
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
                'icon': '⚠️',  # Added default icon
                'priority': priority
            }
            alert_model.insert(alert_data)
            
            if cache.is_connected():
                try:
                    cache.cache_alert(alert_data)
                    st.success("Alert created successfully!")
                except Exception as e:
                    st.error(f"Failed to cache alert: {str(e)}")
            else:
                st.warning("Redis cache is not connected. Alert created but not cached.")
                st.success("Alert created successfully!")
    
    # Alert List
    fetched_alerts = alert_model.get_all()
    if fetched_alerts:
        for alert in fetched_alerts:
            # Convert database row to dictionary if needed
            if not isinstance(alert, dict):
                alert_dict = {
                    'type': alert[1],
                    'message': alert[2],
                    'time': alert[3],
                    'status': alert[4],
                    'icon': alert[5] or '⚠️',  # Default icon if not provided
                    'priority': alert[6]
                }
                show_enhanced_alerts(alert_dict)
            else:
                show_enhanced_alerts(alert)
    else:
        st.info("No alerts found. Create a new alert to get started.")