# Use the official Python 3.9 slim image as the base image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install the dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Expose the port that the Flask app will run on
EXPOSE 8080

# Set the entrypoint to run the Flask app using gunicorn
ENTRYPOINT ["gunicorn", "--bind", "0.0.0.0:8080", "src.main:app"] 
