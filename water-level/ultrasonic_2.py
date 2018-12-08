#!/usr/bin/python
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |R|a|s|p|b|e|r|r|y|P|i|-|S|p|y|.|c|o|.|u|k|
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#
# ultrasonic_2.py
# Measure distance using an ultrasonic module
# in a loop.
#
# Ultrasonic related posts:
# http://www.raspberrypi-spy.co.uk/tag/ultrasonic/
#
# Author : Matt Hawkins
# Date   : 16/10/2016
# -----------------------

# -----------------------
# Import required Python libraries
# -----------------------
from __future__ import print_function
import time
import RPi.GPIO as GPIO

from dateutil import relativedelta
import datetime
import numpy as np
import signal


# -----------------------
# Define constants
# -----------------------
# NOTE: make this enum
class Signal(object):
    ON = True
    OFF = False


SIGNAL = Signal()

# Define GPIO to use on Pi
GPIO_TRIGGER = 23
GPIO_ECHO = 24
GPIO_RELAY_UPPER = 22
GPIO_RELAY_LOWER = 27


UPPER_LOW = 8
UPPER_HIGH = 2  # 20

LOWER_LOW = 8  # 800
LOWER_HIGH = 2  # 20

N_SAMPLES_PER_INTERVAL = 10
UPDATE_INTERVAL = 5
ULTRASONIC_SENSOR_PULSE_DELAY = .1

# Speed of sound in cm/s at temperature
# temperature = 20
# speedSound = 33100 + (0.6 * temperature)
TEMPERATURE = 20
SOUND_SPEED = 33100 + (0.6*TEMPERATURE)


# -----------------------
# Define some functions
# -----------------------
# def measure():
#     # This function measures a distance
#     GPIO.output(GPIO_TRIGGER, True)
#     # Wait 10us
#     time.sleep(0.001)
#     GPIO.output(GPIO_TRIGGER, False)
#     # start = time.time()
#
#     while GPIO.input(GPIO_ECHO) == 0:
#         start = time.time()
#
#     while GPIO.input(GPIO_ECHO) == 1:
#         stop = time.time()
#
#     elapsed = stop - start
#     distance = (elapsed * speedSound) / 2
#
#     return distance

def measure():
    # This function measures a distance
    GPIO.output(GPIO_TRIGGER, False)
    GPIO.output(GPIO_TRIGGER, True)
    # Wait 10us
    time.sleep(0.00001)
    GPIO.output(GPIO_TRIGGER, False)
    start = time.time()

    # print('echo: {}'.format(GPIO.input(GPIO_ECHO)))
    while GPIO.input(GPIO_ECHO)==0:
        start = time.time()

    while GPIO.input(GPIO_ECHO)==1:
        stop = time.time()

    stop = time.time()
    elapsed = stop-start
    distance = (elapsed * SOUND_SPEED)/2.

    return distance


def measure_average_simple():
    # This function takes 3 measurements and
    # returns the average.

    distance1 = measure()
    time.sleep(0.1)
    distance2 = measure()
    time.sleep(0.1)
    distance3 = measure()
    distance = distance1 + distance2 + distance3
    distance = distance / 3.
    return distance

class TimeoutException(Exception):   # Custom exception class
    pass

def timeout_handler(signum, frame):   # Custom signal handler
    raise TimeoutException

# Change the behavior of SIGALRM
signal.signal(signal.SIGALRM, timeout_handler)

def measure_average():
    # This function takes 3 measurements and
    # returns the average.

    distance = None
    distances = []
    precision = 2
    for i in range(N_SAMPLES_PER_INTERVAL):
        signal.alarm(1)
        try:
            print('next measurement...')
            d = measure()
            distances.append(d)
            sleep = max(ULTRASONIC_SENSOR_PULSE_DELAY, UPDATE_INTERVAL / float(N_SAMPLES_PER_INTERVAL))
            print('pause between measurements for {}s'.format(sleep))
            time.sleep(sleep)
        except TimeoutException:
            print('timeout measurement after 1 s')
            continue # continue the for loop if function A takes more than 5 second
        except Exception as e:
            # warnings.warn(str(e))
            # logging.debug(str(e))
            raise e
            # distances = reject_outliers(distances)
        finally:
            # Reset the alarm
            signal.alarm(0)
        print('>>> measure {} : {}'.format(i, d))

    try:
        #distance = np.mean(distances)
        distance = np.median(distances)
    except Exception as e:
        # warnings.warn(str(e))
        # logging.info(str(e))
        raise e
    print('>>> median measure: {}'.format(d))

    return distance


class Period(object):
    def __init__(self, start, stop):
        self.start = start
        self.stop = stop


class RelayState(object):
    def __init__(self, duration=0):
        self.is_on = False
        self.start_time = None
        self._duration = duration

    def reset(self):
        self.is_on = False
        self.start_time = None

    def update(self, signal):
        self.is_on = signal
        return self

    # def update(self,is_on, ):


class Tank(object):
    def __init__(self, high=None, low=None):
        self.is_low = False
        self.is_high = False
        self.is_ok = False

        self.HIGH = high
        self.LOW = low

    def reset(self):
        self.is_ok = False
        self.is_low = False
        self.is_high = False

    def update(self, level):
        if self.LOW <= level:
            self.is_low = True
            self.is_high = False
        elif self.HIGH >= level:
            self.is_low = False
            self.is_high = True
        else:
            self.is_ok = True
            self.is_low = False
            self.is_high = False
        return self


def relay_logic(relay, upper_tank, lower_tank, clock_times):
    action_time = False
    now = datetime.datetime.now().time()
    for t in clock_times:
        if t.start <= now < t.stop:
            action_time = True
            break
        else:
            print("wrong time ", t.start, now, t.stop)
            relay.update(SIGNAL.OFF)

    if action_time:
        if upper_tank.is_high:
            relay.update(SIGNAL.OFF)
            print('detected upper high')
        elif not upper_tank.is_high and not lower_tank.is_low:
            relay.update(SIGNAL.ON)
            print('detected ok', relay.is_on)
        else:
            print("No conditions met")
            relay.update(SIGNAL.OFF)

    print('relay state: {}'.format(relay.is_on))
    return relay


# ----------------------
# test input
# ----------------------

def test_init():
    upper_tank = Tank(low=UPPER_LOW, high=UPPER_HIGH)
    lower_tank = Tank(low=LOWER_LOW, high=LOWER_HIGH)
    upper_tank_relay = RelayState(duration=20)

    now = datetime.datetime.now()
    clock_times = [
        Period(
            now.time(),
            (now +
             relativedelta.relativedelta(
                 seconds=60)).time()),
        Period((now + relativedelta.relativedelta(seconds=100)).time(),
               (now + relativedelta.relativedelta(seconds=110)).time())]
    print('clock times ', [(c.start, c.stop) for c in clock_times])
    return upper_tank, lower_tank, upper_tank_relay, clock_times

# -----------------------
# Main Script
# -----------------------


# Use BCM GPIO references
# instead of physical pin numbers
GPIO.setmode(GPIO.BCM)


print("Ultrasonic Measurement")
print("Speed of sound is", SOUND_SPEED / 100, "m/s at ", TEMPERATURE, "deg")

# Set pins as output and input
GPIO.setup(GPIO_TRIGGER, GPIO.OUT)  # Trigger
GPIO.setup(GPIO_ECHO, GPIO.IN)      # Echo

GPIO.setup(GPIO_RELAY_UPPER, GPIO.OUT)
GPIO.setup(GPIO_RELAY_LOWER, GPIO.OUT)


# Set trigger to False (Low)
GPIO.output(GPIO_TRIGGER, False)
GPIO.output(GPIO_RELAY_UPPER, False)
GPIO.output(GPIO_RELAY_LOWER, False)


# Allow module to settle
time.sleep(0.5)


# Wrap main content in a try block so we can
# catch the user pressing CTRL-C and run the
# GPIO cleanup function. This will also prevent
# the user seeing lots of unnecessary error
# messages.
try:
    # relay = RelayState(dur_keep_on=20)
    upper_tank, lower_tank, upper_tank_relay, clock_times = test_init()
    while True:
        print('reading distance...')
        upper_level = measure_average()
        print("upper tank level : {0:5.1f}".format(upper_level))
        # time.sleep(1)

        # upper_tank = set_tank_state(upper_tank, upper_level)
        print('updating upper tank')
        upper_tank.update(upper_level)
        print(upper_tank.__dict__)
        print('updating lower tank')
        lower_tank.update(upper_level)
        print(lower_tank.__dict__)
        upper_tank_relay = relay_logic(
            upper_tank_relay, upper_tank, lower_tank, clock_times)

        GPIO.output(GPIO_RELAY_UPPER, upper_tank_relay.is_on)


except KeyboardInterrupt:
    # User pressed CTRL-C
    # Reset GPIO settings
    GPIO.cleanup()
