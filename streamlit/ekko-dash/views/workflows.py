import streamlit as st
from utils.models import Database, Workflow, Cache
from datetime import datetime, timedelta
import random

# Initialize database and models
db = Database()
workflow_model = Workflow(db)
cache = Cache()

# Generate dummy workflows for display purposes
def generate_dummy_workflows(count=10):
    workflow_names = [
        "Portfolio Rebalance",
        "Daily Price Alerts",
        "Smart Contract Monitor",
        "Gas Price Tracker",
        "DeFi Yield Optimizer",
        "Arbitrage Scanner",
        "Whale Alert Monitor",
        "NFT Price Floor Monitor",
        "Weekly Token Report",
        "Staking Rewards Harvester"
    ]
    workflow_descriptions = [
        "Automatically rebalance portfolio based on predefined allocations",
        "Monitor prices for specified tokens and send alerts on significant movements",
        "Track smart contract interactions for suspicious activity",
        "Track gas prices and alert when optimal for transactions",
        "Monitor and optimize positions across DeFi protocols",
        "Scan for arbitrage opportunities across DEXes",
        "Track large transactions from whale wallets",
        "Monitor floor prices for specified NFT collections",
        "Generate weekly performance reports for token holdings",
        "Automatically claim and compound staking rewards"
    ]
    schedules = ["Manual", "Hourly", "Daily", "Weekly", "Monthly"]
    risk_levels = ["Low", "Medium", "High"]
    statuses = ["Active", "Paused", "Pending", "Failed"]
    
    dummy_workflows = []
    now = datetime.now()
    
    for i in range(count):
        # Pick random properties for this workflow
        name_idx = i % len(workflow_names)
        name = workflow_names[name_idx]
        description = workflow_descriptions[name_idx]
        schedule = random.choice(schedules)
        risk_level = random.choice(risk_levels)
        status = random.choice(statuses)
        
        # Randomize the last run time (some might be None for never run)
        if random.random() > 0.2:  # 80% chance to have a last run time
            days_ago = random.randint(0, 30)
            last_run = now - timedelta(days=days_ago)
        else:
            last_run = None
        
        # Create the workflow object
        dummy_workflows.append({
            'id': i + 1,
            'name': name,
            'description': description,
            'schedule': schedule,
            'risk_level': risk_level,
            'status': status,
            'last_run': last_run,
            'created_at': now - timedelta(days=random.randint(30, 120)),
            'updated_at': now - timedelta(days=random.randint(0, 30))
        })
    
    return dummy_workflows

# Function to get time ago string
def get_time_ago(timestamp):
    if not timestamp:
        return "Never"
    
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

# Function to show workflow form
def show_create_workflow_form():
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
    
    with st.form("create_workflow_form"):
        st.subheader("Create New Workflow")
        
        workflow_name = st.text_input("Workflow Name")
        description = st.text_area("Description", placeholder="Describe what this workflow does...")
        
        col1, col2 = st.columns(2)
        with col1:
            schedule = st.selectbox("Schedule", ["Manual", "Hourly", "Daily", "Weekly", "Monthly"])
        
        with col2:
            risk_level = st.selectbox("Risk Level", ["Low", "Medium", "High"])
        
        # Form submission buttons
        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("Cancel", use_container_width=True):
                st.session_state['create_workflow_form_open'] = False
                st.rerun()
        
        with col2:
            if st.form_submit_button("Create Workflow", use_container_width=True):
                if workflow_name:
                    # Prepare workflow data
                    workflow_data = {
                        'name': workflow_name,
                        'description': description,
                        'schedule': schedule,
                        'risk_level': risk_level,
                        'status': 'Pending',
                        'last_run': None
                    }
                    
                    # Insert workflow into database
                    try:
                        workflow_model.insert(workflow_data)
                        
                        if cache.is_connected():
                            try:
                                cache.cache_workflow(workflow_data)
                            except Exception as e:
                                st.warning(f"Workflow created but not cached: {str(e)}")
                        
                        st.success("Workflow created successfully!")
                    except Exception as e:
                        st.error(f"Failed to create workflow: {str(e)}")
                    
                    # Close the form
                    st.session_state['create_workflow_form_open'] = False
                    st.rerun()
                else:
                    st.error("Please enter a workflow name")

# Function to display workflow grid
def show_workflow_grid(workflows):
    # Define color coding for statuses
    status_colors = {
        "Active": "#10b981",     # Green
        "Paused": "#f59e0b",     # Amber
        "Pending": "#3b82f6",    # Blue
        "Failed": "#ef4444"      # Red
    }
    
    # Define color coding for risk levels
    risk_colors = {
        "Low": "#10b981",        # Green
        "Medium": "#f59e0b",     # Amber
        "High": "#ef4444"        # Red
    }
    
    # Add CSS for workflow styling with fixed heights and better alignment
    st.markdown("""
    <style>
        /* Fix for the grid layout and card alignment */
        div.row-widget.stHorizontal > div {
            padding: 0 3px;
            box-sizing: border-box;
            margin-bottom: 8px;
        }
        
        /* Target each workflow card container specifically */
        div.element-container div.stVerticalBlock {
            height: 180px;
            background-color: #FFF8E1;
            border-radius: 10px;
            padding: 12px;
            border: 1px solid #FFE082;
            margin-bottom: 8px;
            position: relative;
            overflow: hidden;
        }
        
        /* Style for the status tag */
        .status-tag {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 500;
        }
        
        .status-Active {
            background-color: #ecfdf5;
            color: #10b981;
        }
        
        .status-Paused {
            background-color: #fffbeb;
            color: #f59e0b;
        }
        
        .status-Pending {
            background-color: #eff6ff;
            color: #3b82f6;
        }
        
        .status-Failed {
            background-color: #fef2f2;
            color: #ef4444;
        }
        
        /* Style for risk level */
        .risk-tag {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 500;
            margin-left: 4px;
        }
        
        .risk-Low {
            background-color: #ecfdf5;
            color: #10b981;
        }
        
        .risk-Medium {
            background-color: #fffbeb;
            color: #f59e0b;
        }
        
        .risk-High {
            background-color: #fef2f2;
            color: #ef4444;
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
        
        /* Fix description height to exactly 2 lines */
        .workflow-description {
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
    
    # Create rows of workflows, 4 per row
    total_workflows = len(workflows)
    
    # Use evenly spaced grid layout
    for i in range(0, total_workflows, 4):
        # Create a new row
        cols = st.columns(4)
        
        # Fill the row with workflow cards (up to 4)
        for j in range(4):
            idx = i + j
            if idx < total_workflows:
                workflow = workflows[idx]
                with cols[j]:
                    # Workflow name as title
                    st.markdown(f"<strong>{workflow['name']}</strong>", unsafe_allow_html=True)
                    
                    # Workflow description (always 2 lines with CSS control)
                    description = workflow['description']
                    if len(description) > 65:  # Slightly longer to fill 2 lines
                        description = description[:62] + "..."
                        
                    # Use a special class to ensure 2-line height
                    st.markdown(f'<div class="workflow-description">{description}</div>', unsafe_allow_html=True)
                    
                    # Schedule and last run info
                    schedule = workflow['schedule']
                    last_run = get_time_ago(workflow['last_run']) if workflow.get('last_run') else "Never run"
                    
                    st.caption(f"Schedule: {schedule} | Last run: {last_run}")
                    
                    # Status and risk level tags
                    status = workflow.get('status', 'Pending')
                    risk_level = workflow.get('risk_level', 'Medium')
                    
                    st.markdown(f"""
                    <div>
                        <span class="status-tag status-{status}">
                            {status}
                        </span>
                        <span class="risk-tag risk-{risk_level}">
                            {risk_level} Risk
                        </span>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Create a unique key for each button
                    button_key = f"view_workflow_{workflow['id']}"
                    
                    # View details button with click handler
                    if st.button("View Details", key=button_key, use_container_width=True):
                        st.session_state['selected_workflow_id'] = workflow['id']
                        st.session_state['workflow_view'] = 'detail'
                        st.rerun()

# Workflow detail view
def show_workflow_detail(workflow_id, workflows):
    # Find the selected workflow
    workflow = next((w for w in workflows if w['id'] == workflow_id), None)
    
    if not workflow:
        st.error("Workflow not found")
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
    if st.button("← Back to Workflows", use_container_width=False):
        st.session_state['workflow_view'] = 'grid'
        st.rerun()
    
    # Workflow header
    st.subheader(workflow['name'])
    
    # Status indicator
    status = workflow.get('status', 'Pending')
    risk_level = workflow.get('risk_level', 'Medium')
    
    col1, col2 = st.columns(2)
    
    with col1:
        if status == "Active":
            st.success(f"Status: {status}")
        elif status == "Paused":
            st.warning(f"Status: {status}")
        elif status == "Failed":
            st.error(f"Status: {status}")
        else:
            st.info(f"Status: {status}")
    
    with col2:
        if risk_level == "Low":
            st.success(f"Risk Level: {risk_level}")
        elif risk_level == "Medium":
            st.warning(f"Risk Level: {risk_level}")
        else:
            st.error(f"Risk Level: {risk_level}")
    
    # Workflow schedule and timing
    st.markdown("### Schedule")
    schedule = workflow.get('schedule', 'Manual')
    last_run = workflow.get('last_run')
    last_run_str = last_run.strftime("%Y-%m-%d %H:%M:%S") if last_run else "Never"
    last_run_ago = get_time_ago(last_run) if last_run else "Never"
    
    st.write(f"Schedule: {schedule}")
    st.write(f"Last Run: {last_run_str} ({last_run_ago})")
    
    # Workflow description
    st.markdown("### Description")
    st.write(workflow['description'])
    
    # Action buttons
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if status == "Active":
            st.button("Pause Workflow", use_container_width=True, type="primary")
        else:
            st.button("Start Workflow", use_container_width=True, type="primary")
    
    with col2:
        st.button("Run Now", use_container_width=True)
    
    with col3:
        st.button("Delete", use_container_width=True)
    
    # Additional information (placeholder)
    st.markdown("### Execution History")
    st.info("Workflow execution history will be displayed here.")

# Main workflows display function
def show_workflows():
    # Initialize session state for workflow navigation
    if 'workflow_view' not in st.session_state:
        st.session_state['workflow_view'] = 'grid'
    if 'selected_workflow_id' not in st.session_state:
        st.session_state['selected_workflow_id'] = None
    if 'create_workflow_form_open' not in st.session_state:
        st.session_state['create_workflow_form_open'] = False
    
    # Page title based on current view
    if st.session_state['workflow_view'] == 'grid':
        st.markdown('<h1 class="page-header">Workflows</h1>', unsafe_allow_html=True)
    else:
        st.markdown('<h1 class="page-header">Workflow Details</h1>', unsafe_allow_html=True)
    
    # Try to fetch workflows from database
    try:
        fetched_workflows = workflow_model.get_all()
        
        # Process fetched workflows safely
        workflows = []
        if fetched_workflows:
            for workflow_data in fetched_workflows:
                # Create dictionary with safe defaults
                workflow = {
                    'id': str(workflow_data[0]) if len(workflow_data) > 0 else "unknown",
                    'name': str(workflow_data[1]) if len(workflow_data) > 1 else "Unnamed Workflow",
                    'description': str(workflow_data[2]) if len(workflow_data) > 2 else "",
                    'schedule': str(workflow_data[3]) if len(workflow_data) > 3 else "Manual",
                    'risk_level': str(workflow_data[4]) if len(workflow_data) > 4 else "Medium",
                    'status': str(workflow_data[5]) if len(workflow_data) > 5 else "Pending",
                    'last_run': workflow_data[6] if len(workflow_data) > 6 else None,
                    'created_at': workflow_data[7] if len(workflow_data) > 7 else None,
                    'updated_at': workflow_data[8] if len(workflow_data) > 8 else None
                }
                workflows.append(workflow)
    except Exception as e:
        # If there's any error fetching or processing workflow data
        st.warning(f"Using sample data. Database error: {str(e)}")
        workflows = []
    
    # If no workflows found, add dummy workflows
    if not workflows:
        # Generate dummy workflows with high IDs to avoid conflicts with real ones
        dummy_workflows = generate_dummy_workflows(count=12)  # A nice multiple of 4 for the grid
        
        # Use high starting ID to avoid conflicts
        starting_id = 10000
        for i, dummy_workflow in enumerate(dummy_workflows):
            dummy_workflow['id'] = starting_id + i
            workflows.append(dummy_workflow)
    
    # Show appropriate view based on session state
    if st.session_state['workflow_view'] == 'grid':
        # Filters section
        st.markdown('<div style="background-color: #f9fafb; padding: 1rem; border-radius: 8px; margin-bottom: 1rem;">', unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        
        with col1:
            filter_status = st.selectbox("Filter by Status", ["All Statuses", "Active", "Paused", "Pending", "Failed"])
        
        with col2:
            filter_risk = st.selectbox("Filter by Risk Level", ["All Risk Levels", "Low", "Medium", "High"])
        
        with col3:
            sort_order = st.selectbox("Sort by", ["Newest First", "Oldest First", "Last Run"])
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Add New Workflow Button
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.subheader("Workflow Dashboard")
            st.write("Create and manage automated blockchain workflows.")
        
        with col2:
            st.write("")  # Add some space
            if st.button("➕ Add New Workflow", use_container_width=True, key="add_new_workflow_header"):
                st.session_state['create_workflow_form_open'] = True
                st.rerun()
        
        # Show Create Workflow Form if the button was clicked
        if st.session_state.get('create_workflow_form_open', False):
            show_create_workflow_form()
        
        # Apply filters (if not "All")
        if filter_status != "All Statuses":
            workflows = [w for w in workflows if w['status'] == filter_status]
        
        if filter_risk != "All Risk Levels":
            workflows = [w for w in workflows if w['risk_level'] == filter_risk]
        
        # Apply sorting
        if sort_order == "Newest First":
            workflows.sort(key=lambda x: x.get('created_at') or datetime.min, reverse=True)
        elif sort_order == "Oldest First":
            workflows.sort(key=lambda x: x.get('created_at') or datetime.min)
        elif sort_order == "Last Run":
            # Sort by last_run with None values last
            workflows.sort(key=lambda x: (x.get('last_run') is None, x.get('last_run') or datetime.min), reverse=True)
        
        # Show workflow grid
        show_workflow_grid(workflows)
    
    elif st.session_state['workflow_view'] == 'detail':
        # Show workflow detail view for the selected workflow
        show_workflow_detail(st.session_state['selected_workflow_id'], workflows)