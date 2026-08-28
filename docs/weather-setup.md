# Weather logger

## Files

- weather/weather.py
- weather/requirements.txt
- systemd/weather.service

## Runtime paths

Script location:

/home/birduser/weather/weather.py

Log location:

/var/log/weather/weather.log

## Installation

sudo apt update
sudo apt install -y python3-pip python3-venv

mkdir -p ~/weather
cp weather/weather.py ~/weather/weather.py

python3 -m venv ~/weather/.venv
~/weather/.venv/bin/pip install -r weather/requirements.txt

sudo mkdir -p /var/log/weather
sudo chown birduser:birduser /var/log/weather

sudo cp systemd/weather.service /etc/systemd/system/weather.service
sudo systemctl daemon-reload
sudo systemctl enable --now weather.service

## Verify

systemctl status weather.service --no-pager
tail -f /var/log/weather/weather.log

## PostgreSQL Support

Weather observations are also stored permanently in PostgreSQL.

Install the PostgreSQL Python driver used by the system Python environment:

    sudo apt install -y python3-psycopg

The weather service connects to the `birdnet` PostgreSQL database using the local PostgreSQL client configuration.

Database credentials must not be stored in Git.
