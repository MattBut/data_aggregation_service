# data_aggregation_service

# 🚀 Crypto Investment Data Aggregator: Installation & Usage Guide

This guide provides step-by-step instructions on how to deploy the FastAPI microservice on an Ubuntu server using systemd and how to interact with its protected API endpoints.

Prerequisites

An Ubuntu server (e.g., 20.04, 22.04).

python3 and pip installed.

Administrative (sudo) access.
#
# 🛠️ Section 1: Server Setup & Dependencies

These steps prepare the server environment and install the required Python packages.

Update System Packages:



sudo apt update && sudo apt upgrade -y

Install Base Utilities:



sudo apt install python3-pip python3-venv uvicorn -y

Prepare Project Directory: Create a dedicated directory and navigate into it. Ensure your market_data_service.py file is placed here.



sudo mkdir -p /opt/crypto_aggregator

sudo chown -R $USER:$USER /opt/crypto_aggregator

cd /opt/crypto_aggregator

Ensure market_data_service.py is in /opt/crypto_aggregator

Install Python Dependencies: Create and activate a virtual environment, then install the necessary libraries (fastapi, uvicorn, httpx).



python3 -m venv venv

source venv/bin/activate

pip install fastapi uvicorn[standard] httpx python-multipart

deactivate
#
# 🛡️ Section 2: Service Configuration (systemd)
 
We use systemd to ensure the service runs continuously in the background and restarts automatically if it crashes.

2.1. Define the Service

Create the systemd unit file:



sudo nano /etc/systemd/system/crypto-aggregator.service

Paste the configuration below:

⚠️ CRITICAL SECURITY STEP: Replace YOUR_SECURE_API_KEY_HERE with your actual long, secret API key.

[Unit]

Description=FastAPI Crypto Data Aggregator Microservice

After=network.target

[Service]

ExecStart=/opt/crypto_aggregator/venv/bin/uvicorn market_data_service:app --host 0.0.0.0 --port 8000

WorkingDirectory=/opt/crypto_aggregator

# It is best practice to run web apps under a dedicated, non-root user

User=www-data

Restart=always

# Configure the environment variable for API Key protection

Environment="CRYPTO_API_KEY=YOUR_SECURE_API_KEY_HERE"

[Install]

WantedBy=multi-user.target

2.2. Manage the Service

Reload configuration and start the service:



sudo systemctl daemon-reload

sudo systemctl start crypto-aggregator.service

Enable auto-start on boot:



sudo systemctl enable crypto-aggregator.service

Verify service status and check logs:



sudo systemctl status crypto-aggregator.service

Stream the service logs:

sudo journalctl -u crypto-aggregator.service -f
#
# 🌐 Section 3: Reverse Proxy Setup (Nginx)

For production environments, an Nginx reverse proxy is essential for handling external traffic, SSL (HTTPS), and security headers.

Install Nginx:



sudo apt install nginx -y

Create Nginx site configuration:



sudo nano /etc/nginx/sites-available/crypto_api

Paste the Nginx configuration:

💡 Remember: Replace your_domain.com with your actual domain or server IP.

Nginx

server {

    listen 80;
    
    server_name your_domain.com; 

    location / {
    
        # Proxy pass requests to the Uvicorn application running on port 8000
        
        proxy_pass http://127.0.0.1:8000;
        
        proxy_set_header Host $host;
        
        proxy_set_header X-Real-IP $remote_addr;
        
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        
        proxy_set_header X-Forwarded-Proto $scheme;
    
    }

}

Activate and Restart Nginx:



sudo ln -s /etc/nginx/sites-available/crypto_api /etc/nginx/sites-enabled/

sudo nginx -t # Test configuration syntax

sudo systemctl restart nginx

Your service is now accessible via the standard HTTP port 80.
#
# 💡 Section 4: API Usage Examples

All API endpoints require the X-API-Key header for authorization. Use the key you set in the systemd file.

1. Get Aggregated Market Data (Cached)

Endpoint: /api/market/aggregated_data

Description: Returns combined data (Price, Cap, Volume, Logo) for all USDT pairs, served from a cache (300-second duration).



Replace YOUR_API_KEY and YOUR_DOMAIN

curl -X GET "http://your_domain.com/api/market/aggregated_data" \

     -H "X-API-Key: YOUR_SECURE_API_KEY_HERE"

2. Get Candlestick Data (Klines)

Endpoint: /api/market/klines

Description: Fetches raw OHLCV data from Bybit for a specific symbol and interval.



Example: 1-hour interval for ETHUSDT

Replace YOUR_API_KEY and YOUR_DOMAIN

curl -X GET "http://your_domain.com/api/market/klines?symbol=ETHUSDT&interval=60&limit=500" \

     -H "X-API-Key: YOUR_SECURE_API_KEY_HERE"
