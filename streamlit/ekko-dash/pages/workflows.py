import streamlit as st
from utils.models import Database, Workflow, Cache
from utils.alerts  import show_enhanced_alert

# Initialize database and models
db = Database()
workflow_model = Workflow(db)
cache = Cache()

def show_workflows():
    st.markdown('<h1 class="page-header">Workflows</h1>', unsafe_allow_html=True)
    
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
            cache.cache_workflow(workflow_data)
            st.success("Workflow created successfully!")
    
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