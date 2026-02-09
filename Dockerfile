# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    tmux \
    fzf \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 20
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy package files
COPY package.json ./

# Install Node.js dependencies
RUN npm install

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Copy Python project files
COPY pyproject.toml ./

# Install Python dependencies with uv
RUN /root/.local/bin/uv pip install --system -r pyproject.toml

# Create minimal tmux config
RUN mkdir -p /root && echo 'set -g status off' > /root/.tmux.conf

# Set environment variables
ENV TERM=xterm-256color
ENV NODE_ENV=test

# Copy application files
COPY . .

# Make session-zx.mjs executable
RUN chmod +x session-zx.mjs

# Default command runs tests
CMD ["pytest", "-v"]
