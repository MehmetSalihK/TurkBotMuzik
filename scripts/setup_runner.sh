#!/bin/bash
# setup_runner.sh

# Install gitlab-runner
# http://docs.gitlab.com/runner/install/linux-repository.html
echo "Installing gitlab-runner"
curl -L https://packages.gitlab.com/install/repositories/runner/gitlab-runner/script.deb.sh | sudo bash
sudo apt-get install gitlab-runner -y

# Add to sudo group
sudo usermod -a -G sudo gitlab-runner

sudo gitlab-runner register

sudo gitlab-runner start

# Run sudo visudo and enter the following:
# gitlab-runner ALL=(ALL) NOPASSWD: ALL