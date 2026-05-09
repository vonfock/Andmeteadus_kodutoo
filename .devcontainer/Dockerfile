# Estonian Roadworthiness Analysis — Dev Container
# Ubuntu 22.04 LTS + Python 3.11

FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV LANG=en_US.UTF-8
ENV LC_ALL=en_US.UTF-8

# System packages + Python
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3.11-dev \
    python3-pip \
    python3.11-venv \
    git \
    curl \
    wget \
    build-essential \
    ca-certificates \
    locales \
    sudo \
    && locale-gen en_US.UTF-8 \
    && rm -rf /var/lib/apt/lists/*

# Make python3.11 the default
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1 \
    && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

# Upgrade pip
RUN python -m pip install --upgrade pip

# Install all project dependencies
RUN pip install \
    duckdb \
    pandas \
    numpy \
    scikit-learn \
    matplotlib \
    seaborn \
    plotly \
    streamlit \
    requests \
    jupyterlab \
    ipykernel \
    ipywidgets \
    openpyxl \
    pyarrow \
    scipy \
    black \
    ruff

# Create non-root user
RUN useradd -m -s /bin/bash devuser \
    && echo "devuser ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

USER devuser
WORKDIR /workspace

EXPOSE 8501 8888