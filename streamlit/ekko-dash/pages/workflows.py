import streamlit as st

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