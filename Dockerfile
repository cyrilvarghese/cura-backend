# Use a Conda-compatible base image
FROM continuumio/miniconda3:latest

# Set the working directory in the container
WORKDIR /app

# Copy only the environment file first to leverage Docker caching
COPY environment.yml .

# Create Conda environment with detailed error logging
RUN set -x && \
    echo "Starting Conda environment creation..." && \
    (conda env create -f environment.yml 2>&1 | tee conda_create.log) || \
    (echo "Conda environment creation failed. See logs below:" && \
    cat conda_create.log && \
    exit 1) && \
    echo "Cleaning Conda cache..." && \
    conda clean -afy && \
    echo "Removing unnecessary files..." && \
    find /opt/conda/ -follow -type f -name '*.a' -delete && \
    find /opt/conda/ -follow -type f -name '*.pyc' -delete && \
    find /opt/conda/ -follow -type f -name '*.js.map' -delete && \
    echo "Environment setup completed successfully"

# Activate the Conda environment
SHELL ["conda", "run", "-n", "cura-env", "/bin/bash", "-c"]

# Copy the rest of the application code
COPY . .

# Set PATH to include the Conda environment's executables
ENV PATH /opt/conda/envs/cura-env/bin:$PATH

# Expose the port your FastAPI app runs on
EXPOSE 8000

# Command to run the FastAPI app with error logging
CMD echo "Starting FastAPI application..." && \
    conda run --no-capture-output -n cura-env uvicorn main:app --host 0.0.0.0 --port 8000 2>&1 | tee app.log