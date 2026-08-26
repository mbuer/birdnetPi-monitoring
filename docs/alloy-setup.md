# Alloy setup

## Runtime files

Alloy config:
/etc/alloy/config.alloy

Alloy defaults:
/etc/default/alloy

Alloy state:
/var/lib/alloy/data

## Install

Install Grafana Alloy using the official Grafana package instructions.

Copy the saved config:

sudo mkdir -p /etc/alloy
sudo cp alloy/config.alloy /etc/alloy/config.alloy
sudo cp alloy/default-alloy /etc/default/alloy

Edit /etc/alloy/config.alloy and replace:

GRAFANA_CLOUD_USERNAME
GRAFANA_CLOUD_PASSWORD

with the real Grafana Cloud credentials.

Enable and start Alloy:

sudo systemctl enable alloy
sudo systemctl restart alloy

## Verify

systemctl status alloy --no-pager
journalctl -u alloy -n 50 --no-pager
