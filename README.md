# Ekko Community Edition

Ekko is an **open-source blockchain monitoring and automation platform** that helps you track, analyze, and automate blockchain transactions across multiple chains. Built with Python and Streamlit, Ekko provides a powerful yet user-friendly interface for managing your blockchain operations.

⭐ If you find Ekko useful, please consider giving us a star on GitHub!

![License](https://img.shields.io/github/license/ekkoblock/ekko-ce)
![Python Version](https://img.shields.io/badge/python-3.9%2B-blue)
![Streamlit Version](https://img.shields.io/badge/streamlit-1.28%2B-red)

<p align="center">
    <img src="docs/assets/dashboard.png" alt="Ekko Dashboard showing wallet monitoring and alerts"/>
</p>

## All Features

- **Multi-Chain Support:** Monitor transactions across Avalanche C-Chain (EVM) and P-Chain (Platform)
- **Real-Time Alerts:** Set up custom alerts for transactions, wallet balances, and smart contract events
- **Wallet Management:** Track and manage multiple wallets across different chains
- **Transaction Monitoring:** Real-time transaction monitoring with customizable filters (via NATS JetStream)
- **Workflow Automation:** Create automated workflows triggered by blockchain events (via NATS JetStream)
- **Agent System:** Deploy autonomous agents for automated trading and monitoring (with NATS JetStream integration)
- **Data Storage and Messaging:** Hybrid system using DuckDB, Valkey, and NATS JetStream for optimal performance
- **Modular Architecture:**
  - **Bento:** Real-time transaction processing and alert engine
  - **Streamlit:** Modern, responsive web interface
  - **Valkey:** High-performance caching and real-time data streaming
  - **NATS JetStream:** Distributed messaging and event streaming
  - **NATS JetStream:** Distributed messaging and event streaming for transaction data

## Quickstart

The easiest way to get started with Ekko is using Docker Compose:

```bash
# Clone the repository
git clone https://github.com/ekkoblock/ekko-ce.git
cd ekko-ce

# Copy and configure environment variables
cp .env.template .env

# Start the services
docker-compose up -d
```

Then visit `http://localhost:8501` to access the Ekko Dashboard.

## Architecture

Ekko is built with a modular architecture focusing on real-time processing and scalability:

- **Bento Service:** Processes blockchain transactions and manages alerts
- **Streamlit Dashboard:** Provides the user interface and data visualization
- **Valkey:** Handles caching and real-time data streaming
- **NATS JetStream:** Handles distributed messaging and event streaming
- **DuckDB:** Manages structured data for wallets, alerts, and workflows

## Documentation

- [Setup Guide](docs/setup.md)
- [Configuration](docs/configuration.md)
- [API Reference](docs/api.md)
- [Contributing Guide](docs/contributing.md)

## Development

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
python -m pytest

# Run linting
flake8 .
```

## Contributing

We welcome contributions! Please see our [Contributing Guide](docs/contributing.md) for details.

## License

Ekko Community Edition is open-source software licensed under the [MIT license](LICENSE).
