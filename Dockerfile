# Use an official Python runtime as a parent image
FROM python:3.13-slim-bookworm

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project into the container at /app
COPY src/ ./src/

# Copy the example environment file, assuming the application loads it
COPY src/.env_example ./.env

# Expose the port that the FastAPI application will run on (default 8000, can be overridden by .env)
EXPOSE 8000

# Define environment variables
ENV PYTHONPATH=/app

# Run the application by executing api_for_agent.py, which starts uvicorn
CMD ["python", "src/api_for_agent.py"]
