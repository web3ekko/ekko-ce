FROM --platform=linux/x86_64 rust:1.76.0

WORKDIR /root
RUN apt-get update && apt-get install -y \
    wget \
    build-essential \
    gcc \
    make \ 
    curl \
    git \
    clang \
    lld

# Install rustup
# RUN curl --proto -y '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y

# Add the cargo bin directory to PATH
ENV PATH="/root/.cargo/bin:${PATH}"


ARG SPIN_VERSION=v2.6.0

## spin
# RUN wget https://github.com/fermyon/spin/releases/download/${SPIN_VERSION}/spin-${SPIN_VERSION}-linux-amd64.tar.gz &&         \
#     tar -xvf spin-${SPIN_VERSION}-linux-amd64.tar.gz &&                                                                       \
#     ls -ltr &&                                                                                                                \
#     mv spin /usr/local/bin/spin;

# Download and install Spin
RUN curl -fsSL https://developer.fermyon.com/downloads/install.sh | bash || true

# Move Spin to PATH
RUN mv spin /usr/local/bin/spin

# Verify installation
RUN /usr/local/bin/spin --version

# Optional: Install templates separately
# RUN /usr/local/bin/spin templates install --git https://github.com/fermyon/spin-templates.git
RUN /usr/local/bin/spin plugin install -u https://github.com/fermyon/spin-test/releases/download/canary/spin-test.json -y

ENV RUST_LOG='spin=trace'

RUN rustup target add wasm32-wasi

COPY . /workspaces/consumer
