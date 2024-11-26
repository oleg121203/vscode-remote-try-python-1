
#!/bin/bash

# Safely remove apt lists with sudo
sudo rm -rf /var/lib/apt/lists/*
sudo mkdir -p /var/lib/apt/lists/partial

# Update package lists
sudo apt-get update