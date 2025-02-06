#!/usr/bin/env python3

import os
import random
import argparse
import configparser
from pathlib import PurePath
from paho.mqtt import client as mqtt_client

CONFIG_ROOT = PurePath(f'{os.environ["HOME"]}/.config/mqtt')

def fix_rel_path_or_none(config, key, root):
    """Handle relative paths from the config file"""
    if key in config:
        file = PurePath(config[key])
        if not file.is_absolute():
            file = PurePath(root, file)
    else:
        file = None
    return file

def get_mqtt_client(config_key='default'):
    client_id = f'python-mqtt-{random.randint(0, 1000)}'    
    config = configparser.ConfigParser()
    config_file = PurePath(CONFIG_ROOT, PurePath('mqtt.ini'))
    config.read(str(config_file))

    client = mqtt_client.Client(client_id)
    client.username_pw_set(config[config_key]['username'],
            config[config_key]['password'])

    certfile = fix_rel_path_or_none(config[config_key], 'certfile', CONFIG_ROOT)
    keyfile = fix_rel_path_or_none(config[config_key], 'keyfile', CONFIG_ROOT)
    ca_certs = fix_rel_path_or_none(config[config_key], 'ca_certs', CONFIG_ROOT)
    if any([f is not None for f in (certfile, keyfile, ca_certs)]):
        client.tls_set(certfile=certfile, keyfile=keyfile, ca_certs=ca_certs)

    return client, config[config_key]['broker'], int(config[config_key]['port'])


def test_main():
    parser = argparse.ArgumentParser(description='Test interface for mqtt-client')
    parser.add_argument('topic', help='A test topic to subscribe to')
    args = parser.parse_args()

    client, broker, port = get_mqtt_client()
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            print("Connected to MQTT Broker!")
        else:
            print("Failed to connect, return code %d\n", rc)
    client.on_connect = on_connect
    client.connect(broker, port)

    def on_message(client, userdata, msg):
        print(f"Received '{msg.payload.decode()}' from '{msg.topic}' topic")
    client.subscribe(args.topic)
    client.on_message = on_message

    client.loop_forever()

if __name__ == '__main__': test_main()
