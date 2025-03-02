import streamlit as st

def show_about():
    st.markdown('<h1 class="page-header">About Ekko</h1>', unsafe_allow_html=True)
    
    # Ekko Description
    st.markdown("""
    <div class="ekko-title">
        <span class="ekko-icon">🔔</span>
        <span class="ekko-name">Ekko Dashboard</span>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    Ekko is a comprehensive dashboard for blockchain monitoring and management. 
    It provides tools for tracking wallets, setting up alerts, creating automated workflows, 
    and deploying AI agents for blockchain activities.
    
    ### Key Features
    
    * **Wallet Tracking**: Monitor multiple blockchain wallets in one place
    * **Smart Alerts**: Get notified about important events and price movements
    * **Automated Workflows**: Create and schedule blockchain-related tasks
    * **AI Agents**: Deploy intelligent agents for monitoring and trading
    
    ### Version Information
    
    * **Version**: 1.0.0-beta
    * **Last Updated**: March 2, 2025
    * **Framework**: Streamlit
    * **Database**: DuckDB, Redis
    
    ### Support
    
    For support or feature requests, please contact support@ekko.io
    """)
    
    # Team section
    st.subheader("Development Team")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        **Abraham Alaka**  
        Lead Developer  
        abraham@ekko.io
        """)
    
    with col2:
        st.markdown("""
        **Ekko Team**  
        Blockchain Specialists  
        team@ekko.io
        """)