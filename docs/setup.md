# Setup Guide

## Prerequisites

- Docker and Docker Compose
- Python 3.9 or higher (for local development)
- Redis
- MinIO

## Installation

### Using Docker Compose (Recommended)

1. Clone the repository:
```bash
git clone https://github.com/ekkoblock/ekko-ce.git
cd ekko-ce
```

2. Copy and configure environment variables:
```bash
cp .env.template .env
```

3. Edit the `.env` file with your configuration:
```env
# Redis Configuration
REDIS_URL=redis://redis:6379

# MinIO Configuration
MINIO_ACCESS_KEY=your_access_key
MINIO_SECRET_KEY=your_secret_key
MINIO_BUCKET=ekko
MINIO_URL=http://minio:9000

# Blockchain API Keys
SNOWTRACE_API_KEY=your_snowtrace_api_key  # For C-Chain transactions
AVALANCHE_NODE_URL=your_node_url  # For P-Chain interactions
```

4. Start the services:
```bash
docker-compose up -d
```

5. Access the dashboard at `http://localhost:8501`

### Local Development Setup

1. Install Python dependencies:
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt  # for development tools
```

2. Start Redis and MinIO:
```bash
docker-compose up -d redis minio
```

3. Start the Bento service:
```bash
cd bento
python main.py
```

4. Start the Streamlit dashboard:
```bash
cd streamlit/ekko-dash
streamlit run app.py
```

## Configuration

See [Configuration Guide](configuration.md) for detailed settings.
