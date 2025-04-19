# Use a Conda-compatible base image
FROM continuumio/miniconda3

# Install system dependencies for browsers (needed for crawl4ai)
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    chromium \
    firefox-esr \
    xvfb \
    sqlite3 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy application code
COPY . .

# Copy Conda environment file
COPY environment.yml .

# Create and activate the Conda environment with improved error logging
RUN conda env create -f environment.yml --debug > conda_log.txt 2>&1 || (cat conda_log.txt && false)

# Set PATH to include the Conda environment's executables
ENV PATH /opt/conda/envs/cura-env/bin:$PATH

# Install crawl4ai and run setup in the Conda environment
RUN /opt/conda/envs/cura-env/bin/pip install crawl4ai && \
    /opt/conda/envs/cura-env/bin/crawl4ai-setup

# Set up virtual display for browser automation
ENV DISPLAY=:99

# Expose the port your FastAPI app runs on
EXPOSE 8000

# Modified CMD to include Xvfb startup
CMD sh -c "Xvfb :99 -screen 0 1024x768x16 & \
    sqlite3 medical_assessment.db < schema.sql && \
    python insert_data.py && \
    uvicorn main:app --host 0.0.0.0 --port 8000"