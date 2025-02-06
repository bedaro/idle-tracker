# MQTT-Based Idle Tracker

A simple Python script that reads Linux desktop screensaver state over
DBus and uses that to infer the activity of the current user. Publishes
that status as "active" or "inactive" to a MQTT broker at
`/<hostname>/user/<username>/status`.

Meant to be used in conjunction with the included systemd unit file run
by the user being monitored.

## Installation

 1. Copy idle-tracker.py and mqttclient.py somewhere in your PATH.
 2. Copy systemd/idle-tracker.service to ~/.config/systemd/user/ (you may need to add to the [Install] section to monitor more than just a gnome session)
 3. Install the required Python libraries (paho-mqtt, python-dbus). If
    you want to use a virtual environment you may need to edit the first
    line of the Python script.
 4. Create a directory ~/.config/mqtt. Create a mqtt.ini file using the included example, and make sure you lock down permissions since it contains private credentials for your MQTT broker. Test your MQTT setup by running `mqttclient.py <topic>` to test whether you can subscribe to a particular topic on your broker.
 5. Run `systemctl --user enable idle-tracker.service`
 6. Run `systemctl --user start idle-tracker`
 7. Run `systemctl --user status idle-tracker` to ensure it's working, then check if your MQTT broker is being published to.

## SSL usage hints

I've personally found getting SSL working for MQTT to be rather frustrating. If you're having trouble, try the following. Assumes your
client certificate is named client.pem, the private key is client.key, and you have a public certificate chain for signing your certificates is named signing-ca-chain.pem

Verify a client certificate: `openssl verify -CAfile signing-ca-chain.pem client.pem`

Test the MQTT broker (hostname/port) with: `openssl s_client -connect hostname:port -CAfile signing-ca-chain.pem`

This should validate the client can recognize the broker, but if you're requiring client certificates there will be an error at the very end asking for one.

To fix that: `openssl s_client -connect hostname:port -CAfile signing-ca-chain.pem -cert client.pem -key client.key`
