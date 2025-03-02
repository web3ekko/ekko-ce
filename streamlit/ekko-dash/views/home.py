import streamlit as st
from utils.alerts import show_enhanced_alerts
from utils.models import Database, Alert

# Initialize database
db = Database()
alert_model = Alert(db)

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
    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("Recent Transactions")
        
        # Mock transaction data
        transactions = [
            {"type": "Swap", "amount": "0.5 ETH → 1250 USDC", "time": "10 mins ago"},
            {"type": "Transfer", "amount": "0.25 BTC", "time": "2 hours ago"},
            {"type": "Stake", "amount": "100 MATIC", "time": "Yesterday"}
        ]
        
        for tx in transactions:
            st.markdown(f"""
                <div class="alert-card alert-info">
                    <div>
                        <div style="font-weight: 500;">{tx['type']}</div>
                        <div style="color: #64748b;">{tx['amount']}</div>
                        <div style="margin-top: 0.5rem; font-size: 0.875rem;">{tx['time']}</div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
    
    with col2:
        st.subheader("Recent Alerts")
        
        # Get recent alerts from database
        fetched_alerts = alert_model.get_all()
        if fetched_alerts and len(fetched_alerts) > 0:
            # Show only the most recent 3 alerts
            for alert in fetched_alerts[:3]:
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
            # Sample alerts if none found in the database
            sample_alerts = [
                {
                    'type': 'Price Alert',
                    'message': 'ETH price dropped below $2,000',
                    'time': '1 hour ago',
                    'status': 'warning',
                    'icon': '📉',
                    'priority': 'High'
                },
                {
                    'type': 'Workflow Alert',
                    'message': 'Weekly portfolio rebalance completed',
                    'time': 'Yesterday',
                    'status': 'success',
                    'icon': '✅',
                    'priority': 'Low'
                }
            ]
            
            for alert in sample_alerts:
                show_enhanced_alerts(alert)