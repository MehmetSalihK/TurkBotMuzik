#!/bin/bash
# setup.sh - installs pre-reqs

HERE="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
function echo_blue(){ echo -e "\n\033[1;34m$@\033[0m\n"; }

# Install apt packages
sudo apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 3F01618A51312F3F

sudo add-apt-repository --yes ppa:deadsnakes/ppa

echo_blue "apt update -y"
sudo apt update --yes
echo_blue "sudo apt install -y python3 python3-pip libffi-dev libnacl-dev python3.8-distutils opus-tools"
sudo apt install --yes python3.8 python3-pip libffi-dev libnacl-dev python3.8-distutils opus-tools

# Install pip packages
echo_blue "sudo python3.8 -m pip install --upgrade pip setuptools wheel"
sudo python3.8 -m pip install --upgrade pip setuptools wheel
echo_blue "sudo python3.8 -m pip install --upgrade -r ${HERE}/requirements.txt"
sudo python3.8 -m pip install --upgrade -r ${HERE}/requirements.txt

# Install snap packages
echo_blue "sudo snap install ffmpeg"
sudo snap install ffmpeg
