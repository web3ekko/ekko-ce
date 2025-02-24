import streamlit as st
from utils.models import Database, Wallet, Cache

# Initialize database and models
db = Database()
wallet_model = Wallet(db)
cache = Cache()

def show_wallets(blockchain_symbol):
    st.markdown('<h1 class="page-header">Wallets</h1>', unsafe_allow_html=True)
    
    col1, col2 = st.columns([2,1])
    with col1:
        st.markdown('<div class="filters-section">', unsafe_allow_html=True)
        st.subheader("Connected Wallets")
        
        # Fetch wallets from database
        fetched_wallets = wallet_model.get_all()
        if fetched_wallets:
            for wallet in fetched_wallets:
                st.markdown(f"""
                    <div class="alert-card alert-info">
                        <div>
                            <div style="font-weight: 500;">{wallet[3]}</div>
                            <div style="color: #64748b;">{wallet[2]}</div>
                            <div style="margin-top: 0.5rem;">{wallet[4]} {wallet[1]}</div>
                        </div>
                    </div>
                """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="filters-section">', unsafe_allow_html=True)
        st.subheader("Add New Wallet")
        
        # Fetch blockchains from the database
        blockchain_model = Blockchain(db)
        fetched_blockchains = blockchain_model.get_all()
        blockchain_options = {blockchain[2]: blockchain[1] for blockchain in fetched_blockchains}
        
        with st.form("add_wallet"):
            wallet_address = st.text_input("Wallet Address (0x...)")
            wallet_name = st.text_input("Wallet Name (optional)")
            selected_chain = st.selectbox("Blockchain", list(blockchain_options.keys()), format_func=lambda x: blockchain_options[x])
            
            if st.form_submit_button("Connect Wallet"):
                # Insert new wallet into database
                wallet_data = {
                    'blockchain_symbol': selected_chain,
                    'address': wallet_address,
                    'name': wallet_name
                }
                wallet_model.insert(wallet_data)
                cache.cache_wallet(wallet_data)
                st.success("Wallet added successfully!")
        
        st.markdown('</div>', unsafe_allow_html=True)