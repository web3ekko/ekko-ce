# Ekko Community Edition

Ekko is an **open-source blockchain monitoring and automation platform** that helps you track, analyze, and automate blockchain transactions across multiple chains. Built with Python and a React-based frontend, Ekko provides a powerful yet user-friendly interface for managing your blockchain operations.

⭐ If you find Ekko useful, please consider giving us a star on GitHub!

![License](https://img.shields.io/github/license/ekkoblock/ekko-ce)
![Python Version](https://img.shields.io/badge/python-3.9%2B-blue)

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
  - **React Frontend:** Modern, responsive web interface
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
# Make sure to review and update .env with your NATS_URL if not using the default,
# and any other necessary configurations (e.g., API keys for external services if you add them).

# Start the services
docker-compose up -d
```

Once the services are running, you can access the Ekko Dashboard at `http://localhost:3000`.

**Creating an Initial User:**

To log in to the dashboard, you'll need a user account. You can create one using the provided script which interacts with the NATS Key-Value store where user data is stored.

Make sure your NATS server (e.g., `nats` service in `docker-compose.yml`) is running before executing this script.

```bash
# Run the user creation script (executes inside the 'api' service container)
docker-compose exec api python scripts/create_ekko_user.py
```

The script will interactively prompt you to enter the user's email, password, full name, and role (e.g., `admin` or `user`).

Alternatively, you can provide the details as command-line arguments:
```bash
docker-compose exec api python scripts/create_ekko_user.py --email your_email@example.com --password 'your_secure_password' --full_name "Your Full Name" --role admin
```
*   Ensure your password is enclosed in single quotes if it contains special characters that might be interpreted by the shell.
*   The `--role` can be `user` or `admin` (or other roles if defined in your system).

After creating a user, you can log in via the dashboard using the credentials you provided.

## Architecture

Ekko is built with a modular architecture focusing on real-time processing and scalability:

- **Bento Service:** Processes blockchain transactions and manages alerts
- **Web Dashboard:** Provides the user interface and data visualization
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
