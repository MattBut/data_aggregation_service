# data_aggregation_service

Data aggregation service for cryptocurrency asset analysis.

⚙️ Microservice Installation Guide (Ubuntu + systemd)
This guide explains how to set up the FastAPI application as a systemd service on an Ubuntu server, ensuring it runs reliably in the background.
Prerequisites
    • An Ubuntu server (e.g., 20.04, 22.04).
    • python3 and pip installed.
    • systemctl (standard on modern Linux distributions).
Step 1: Prepare the Server and Project
    1. Update packages:
       Bash
       sudo apt update && sudo apt upgrade -y
    2. Install necessary packages:
       Bash
       sudo apt install python3-pip python3-venv uvicorn -y
    3. Create a dedicated project directory and place the code:
       Bash
       sudo mkdir -p /opt/crypto_aggregator
       sudo chown -R $USER:$USER /opt/crypto_aggregator
       cd /opt/crypto_aggregator
        ◦ Save the code: Save the translated Python code into a file named market_data_service.py within this directory.
    4. Create a Python Virtual Environment:
       Bash
       python3 -m venv venv
       source venv/bin/activate
    5. Install project dependencies:
       Bash
       pip install fastapi uvicorn[standard] httpx python-multipart
    6. Deactivate the environment:
       Bash
       deactivate
Step 2: Configure the Environment Variable
The application requires the CRYPTO_API_KEY environment variable for security. This should be set in the systemd service file (Step 3).
⚠️ Security Note: Replace YOUR_SECURE_API_KEY_HERE with a long, randomly generated secret key.
Step 3: Create the systemd Service File
This file tells the operating system how to run the microservice.
    1. Create the service file:
       Bash
       sudo nano /etc/systemd/system/crypto-aggregator.service
    2. Paste the following content (adjust User and WorkingDirectory if needed):
       Ini, TOML
       [Unit]
       Description=FastAPI Crypto Data Aggregator Microservice
       After=network.target
       
       [Service]
       # Replace with the path to your Python virtual environment
       ExecStart=/opt/crypto_aggregator/venv/bin/uvicorn market_data_service:app --host 0.0.0.0 --port 8000
       
       # Set the working directory to the project folder
       WorkingDirectory=/opt/crypto_aggregator
       
       # Set the user to run the service (e.g., a non-root user)
       User=www-data
       
       # Restart the service if it fails
       Restart=always
       
       # Set the required environment variable for API Key protection
       Environment="CRYPTO_API_KEY=YOUR_SECURE_API_KEY_HERE"
       
       [Install]
       WantedBy=multi-user.target
Step 4: Manage the systemd Service
    1. Reload the systemd manager configuration:
       Bash
       sudo systemctl daemon-reload
    2. Start the service:
       Bash
       sudo systemctl start crypto-aggregator.service
    3. Enable the service to start automatically on boot:
       Bash
       sudo systemctl enable crypto-aggregator.service
    4. Check the service status and logs:
       Bash
       sudo systemctl status crypto-aggregator.service
       # For more detailed logs:
       sudo journalctl -u crypto-aggregator.service -f
Step 5: (Optional) Set up a Reverse Proxy (Nginx/Apache)
For production, it is highly recommended to use a reverse proxy like Nginx to handle external requests, SSL termination (HTTPS), and rate limiting.
    1. Install Nginx:
       Bash
       sudo apt install nginx -y
    2. Create a new Nginx configuration file:
       Bash
       sudo nano /etc/nginx/sites-available/crypto_api
    3. Add the following configuration (replace your_domain.com):
       Nginx
       server {
           listen 80;
           server_name your_domain.com; # Replace with your domain or IP
       
           location / {
               # Proxy pass all requests to the Uvicorn application running on port 8000
               proxy_pass http://127.0.0.1:8000;
               proxy_set_header Host $host;
               proxy_set_header X-Real-IP $remote_addr;
               proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
               proxy_set_header X-Forwarded-Proto $scheme;
           }
       }
    4. Link the configuration and restart Nginx:
       Bash
       sudo ln -s /etc/nginx/sites-available/crypto_api /etc/nginx/sites-enabled/
       sudo nginx -t
       sudo systemctl restart nginx
The microservice is now running and accessible through port 80 (or 443 with HTTPS, which should be configured separately using a tool like Certbot).
