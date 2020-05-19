#!/bin/bash
# deploy.sh - installs a service to run the bot

function echo_blue(){ echo -e "\n\033[1;34m$@\033[0m\n"; }

echo_blue "----- INSTALLING PLOMBOT -----"

WorkingDirectory=/root/plombot
InstallDirectory=/opt/plombot
sudo mkdir -p ${WorkingDirectory} ${InstallDirectory} "${InstallDirectory}/songs"

# Clean install dir
echo_blue "Cleaning install directory:"
sudo find ${InstallDirectory} -not -path ${InstallDirectory}/keys.py -and -not -path ${InstallDirectory} -delete

# Move to install dir
echo_blue "Moving to install directory:"
sudo mv -v ${CI_PROJECT_DIR}/* ${InstallDirectory}

### /etc/systemd/system/plombot.service
echo_blue "Creating /etc/systemd/system/plombot.service:"
cat << EOF | sudo tee /etc/systemd/system/plombot.service
[Unit]
Description=Plombot
After=multi-user.target
[Service]
User=root
Group=root
Type=idle
WorkingDirectory=${WorkingDirectory}
ExecStart=/usr/bin/python3.8 -u ${InstallDirectory}/plombot.py
Restart=always
RestartSec=1
[Install]
WantedBy=multi-user.target
EOF

#### Reload systemctl to trigger new service
sudo systemctl daemon-reload
sudo systemctl stop plombot || true
sudo systemctl start plombot.service
sudo systemctl enable plombot.service

echo_blue "systemctl status"
systemctl status plombot

echo_blue "----- PLOMBOT INSTALLED SUCCESSFULLY -----"