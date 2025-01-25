# Use a Conda-compatible base image
FROM continuumio/miniconda3

# Set the working directory in the container
WORKDIR /app

# Copy application code
COPY . .

# Copy Conda environment file
COPY environment.yml .

# Create and activate the Conda environment
RUN conda env create -f environment.yml --debug > conda_log.txt 2>&1

# Set PATH to include the Conda environment's executables
ENV PATH /opt/conda/envs/cura-env/bin:$PATH

# Expose the port your FastAPI app runs on
EXPOSE 8000

# Command to run the FastAPI app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]