import streamlit as st
from datetime import datetime
from utils.db import db, alert_model, cache




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
                'icon': '',  # Default icon, change as needed
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
                st.error("Failed to connect to Redis. Alert caching is disabled.")
    
    # Alert List
    fetched_alerts = alert_model.get_all()
    for alert in fetched_alerts:
        show_enhanced_alerts(alert)

# Enhanced Alert Display
def show_enhanced_alerts(alert):
    """
    Display an enhanced alert card with styling
    
    Args:
        alert (dict): Alert data dictionary containing type, message, status, etc.
    """
    st.markdown(f"""
        <div class="alert-card alert-{alert['status']}">
            <div style="font-size: 1.5rem;">{alert.get('icon', '')}</div>
            <div style="flex-grow: 1;">
                <div style="display: flex; justify-content: space-between; align-items: start;">
                    <div>
                        <div style="font-weight: 500; margin-bottom: 0.25rem;">
                            {alert.get('type', 'Alert')}
                        </div>
                        <div style="color: #64748b;">
                            {alert.get('message', '')}
                        </div>
                    </div>
                    <div style="text-align: right;">
                        <span class="priority-badge priority-{alert.get('priority', 'Medium')}">
                            {alert.get('priority', 'Medium')}
                        </span>
                        <div style="color: #64748b; font-size: 0.875rem; margin-top: 0.5rem;">
                            {alert.get('time', '')}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)