#!/bin/bash
# deploy.sh - installs a service to run the bot

function echo_blue(){ echo -e "\n\033[1;34m$@\033[0m\n"; }

echo_blue "----- INSTALLING PLOMBOT DEV -----"

WorkingDirectory=/root/plombot-dev
InstallDirectory=/opt/plombot-dev
sudo mkdir -p ${WorkingDirectory} ${InstallDirectory}

# Clean install dir
echo_blue "Cleaning install directory:"
sudo find ${InstallDirectory} -not -path ${InstallDirectory} -delete

# Clean working dir
echo_blue "Cleaning working directory:"
sudo find ${WorkingDirectory} -maxdepth 1 -not -path ${WorkingDirectory}/songs -and -not -path ${WorkingDirectory} -delete

# Move to install dir
echo_blue "Moving to install directory:"
sudo mv -v ${CI_PROJECT_DIR}/* ${InstallDirectory}

### /etc/systemd/system/plombot.service
echo_blue "Creating /etc/systemd/system/plombot-dev.service:"
cat << EOF | sudo tee /etc/systemd/system/plombot-dev.service
[Unit]
Description=Plombot-dev
After=multi-user.target
[Service]
User=root
Group=root
Type=idle
WorkingDirectory=${WorkingDirectory}
ExecStart=/usr/bin/python3 -u ${InstallDirectory}/plombot.py dev
Restart=always
RestartSec=1
[Install]
WantedBy=multi-user.target
EOF

#### Reload systemctl to trigger new service
sudo systemctl daemon-reload
sudo systemctl stop plombot-dev || true
sudo systemctl start plombot-dev.service
sudo systemctl enable plombot-dev.service

echo_blue "systemctl status plombot-dev"
systemctl status plombot-dev

echo_blue "----- PLOMBOT DEV INSTALLED SUCCESSFULLY -----"
