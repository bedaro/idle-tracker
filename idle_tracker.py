#!/usr/bin/env python3
"""MQTT-Based Idle Tracker

Gets screensaver status from dbus, then uses it to publish MQTT messages
about user activity on the host
"""

import os
import sys
import logging
import signal
import socket
from threading import Timer

from gi.repository import GLib
from pydbus import SessionBus

import mqttclient

class Publisher:
    """A MQTT recurring publishing system with forced updates"""

    class IntervalTimer(Timer):
        """Run a task on an interval, stopping after consecutive failures.

        Based on a Timer subclass posted at
        https://stackoverflow.com/a/48741004/413862

        The main differences with Timer are:
        - The function runs immediately when start() is called (unless cancel()
          was called first).
        - The timer continues calling the function on the interval, unless
          cancel() is called or the function returns False enough times
          consecutively. This behavior is intended to be robust against
          intermittent failures (like connectivity problems).
        - If failures cause the loop to stop, the class attribute "died" will
          be set to True.
        """

        # pylint: disable=too-many-arguments, too-many-positional-arguments
        def __init__(self, interval, function, args=None, kwargs=None, stop_after_fails=5):
            """Constructor.

            Most of the arguments are inherited from the superclass.

            Additional keyword arguments:
            stop_after_fails -- cancel the loop after this many consecutive
                                failures (default 5). Pass 0 to disable this.
            """
            self.stop_after_fails = stop_after_fails
            self.fail_count = 0
            self.died = False
            Timer.__init__(self, interval, function, args=args, kwargs=kwargs)

        def run(self):
            """override"""
            # For compatibility with Timer: make sure cancel() has not been
            # called before start()
            if self.finished.is_set():
                return
            while True:
                result = self.function(*self.args, **self.kwargs)
                self.fail_count = 0 if result else self.fail_count + 1
                if (self.stop_after_fails > 0 and
                        self.fail_count >= self.stop_after_fails):
                    self.died = True
                    break
                if self.finished.wait(self.interval):
                    break

    def __init__(self, client, topic, interval=5):
        self.logger = logging.getLogger().getChild('Publisher')
        self.client = client
        self.topic = topic
        self.interval = interval
        self.timer = None

    def setValue(self, value, now=False):
        self._value = value
        if now or self.timer is None:
            if self.timer is not None:
                self.timer.cancel()
            self.timer = Publisher.IntervalTimer(self.interval, self._update)
            self.timer.start()

    def stop(self):
        if self.timer is not None:
            self.timer.cancel()

    def _update(self):
        result = self.client.publish(self.topic, self._value)
        success = result[0] == 0
        if success:
            self.logger.debug('pushed %s to %s', self._value, self.topic)
        else:
            self.logger.error('Failed to send message: %s', result)
        return success

def status_to_value(status):
    """Converts screensaver status to user activity string"""
    return 'inactive' if status else 'active'

def setup_dbus(publisher):
    """Look for a screensaver interface and connect the publisher to it"""
    logger = logging.getLogger().getChild('setup_dbus')
    # Borrowed from https://stackoverflow.com/a/55157266/413862
    bus = SessionBus()

    screensaver_list = ['org.gnome.ScreenSaver',
                        'org.cinnamon.ScreenSaver',
                        'org.kde.screensaver',
                        'org.freedesktop.ScreenSaver']

    found = False
    for each in screensaver_list:
        try:
            object_path = f"/{each.replace('.', '/')}"
            ss = bus.get(each, object_path)
            ss_iface = ss[each]
            publisher.setValue(status_to_value(ss_iface.GetActive()))
            ss_iface.ActiveChanged.connect(
                    lambda status: publisher.setValue(status_to_value(status), now=True))
            logger.info('Listening for events from %s', each)
            found = True
            break
        except GLib.GError:
            pass
    if not found:
        logger.critical('No screensavers found to monitor')
    return found

def main():
    logging.basicConfig(level=logging.INFO)
    c, broker, port = mqttclient.get_mqtt_client()

    pub = None
    loop = None
    def on_connect(client, userdata, flags, rc):
        del client
        del userdata
        del flags
        logger = logging.getLogger().getChild('get_mqtt_client')
        if rc != 0:
            logger.critical('Failed to connect to MQTT broker, return code %d', rc)
            if pub is not None:
                pub.stop()
            if loop is not None:
                loop.quit()
            else:
                sys.exit(1)
    c.on_connect = on_connect
    c.connect(broker, port)

    c.loop_start()
    pub = Publisher(c, f'{socket.gethostname()}/user/{os.getlogin()}/status')

    if setup_dbus(pub):
        loop = GLib.MainLoop()
        def stop(sig, frame):
            del frame
            logging.getLogger().critical('Received signal %d', sig)
            pub.stop()
            loop.quit()

        signal.signal(signal.SIGINT, stop)
        signal.signal(signal.SIGTERM, stop)
        loop.run()
    else:
        sys.exit(1)

if __name__ == '__main__':
    main()
