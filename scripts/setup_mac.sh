#!/bin/bash
# setup_mac.sh
# Installs pre-reqs to run on a mac

HERE="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

# Install homebrew
echo "Installing homebrew"
/usr/bin/ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"

# Install OPUS and ffmpeg
echo "Installing OPUS and ffmpeg"
brew install opus ffmpeg

pip3 install --upgrade -r ${HERE}/requirements.txt