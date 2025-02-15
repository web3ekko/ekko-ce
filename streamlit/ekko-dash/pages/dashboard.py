import streamlit as st

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