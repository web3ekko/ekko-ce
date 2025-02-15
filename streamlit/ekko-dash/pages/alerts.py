import streamlit as st

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
