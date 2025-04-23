# Use a Conda-compatible base image
FROM continuumio/miniconda3

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

# Install SQLite CLI (not included by default in some base images)
RUN apt-get update && apt-get install -y sqlite3 && apt-get clean

# Create case-data directory if it doesn't exist
RUN mkdir -p /app/case-data

# Expose the port your FastAPI app runs on
EXPOSE 8000

# Command to create DB from schema, seed it, then run the app
CMD sh -c "sqlite3 medical_assessment.db < schema.sql && python insert_data.py && uvicorn main:app --host 0.0.0.0 --port 8000"