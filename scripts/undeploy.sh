#!/bin/bash
# undeploy.sh - uninstalls the plombot service

function echo_blue(){ echo -e "\n\033[1;34m$@\033[0m\n"; }

echo_blue '---------- UNINSTALLING PLOMBOT ----------'

WorkingDirectory=/root/plombot
InstallDirectory=/opt/plombot

rm -rfv ${InstallDirectory}
find ${WorkingDirectory} -maxdepth 1 -not -path ${WorkingDirectory}/songs -and -not -path ${WorkingDirectory} -delete

sudo systemctl stop plombot || true
sudo rm -f /etc/systemd/system/plombot.service
sudo systemctl daemon-reload
   
echo_blue '---- PLOMBOT UNINSTALLED SUCCESSFULLY ----'