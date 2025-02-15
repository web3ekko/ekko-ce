import streamlit as st

def show_wallets():
    st.markdown('<h1 class="page-header">Wallets</h1>', unsafe_allow_html=True)
    
    col1, col2 = st.columns([2,1])
    with col1:
        st.markdown('<div class="filters-section">', unsafe_allow_html=True)
        st.subheader("Connected Wallets")
        wallets = [
            {"address": "0x1234...5678", "name": "Main Wallet", "balance": "12.5 AVAX"},
            {"address": "0x8765...4321", "name": "Trading Wallet", "balance": "5,000 USDC"}
        ]
        for wallet in wallets:
            st.markdown(f"""
                <div class="alert-card alert-info">
                    <div>
                        <div style="font-weight: 500;">{wallet['name']}</div>
                        <div style="color: #64748b;">{wallet['address']}</div>
                        <div style="margin-top: 0.5rem;">{wallet['balance']}</div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="filters-section">', unsafe_allow_html=True)
        st.subheader("Add New Wallet")
        with st.form("add_wallet"):
            st.text_input("Wallet Address (0x...)")
            st.text_input("Wallet Name (optional)")
            st.form_submit_button("Connect Wallet")
        st.markdown('</div>', unsafe_allow_html=True)
