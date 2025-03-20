FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the working directory in the container to /app
WORKDIR /app

# Copy the current directory (all files in /guruclubai) into /app in the container
COPY . /app/

# Install dependencies using the requirements.txt in /app
RUN pip install --upgrade pip && pip install -r requirements.txt

# Expose port 5000 (the port your app runs on)
EXPOSE 5000

# Command to run your application
CMD ["python", "app.py"]