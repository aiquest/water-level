#!/usr/bin/env python
'''Show streaming graph of water level.'''

from __future__ import print_function
import time
import RPi.GPIO as GPIO

from jinja2 import Template
from flask import Flask, jsonify
from six.moves.urllib.request import urlopen
from six.moves.urllib.parse import urlencode

from collections import deque
from threading import Thread
# from time import time, sleep
import csv
import codecs
import numpy as np



html = Template('''\
<!DOCTYPE html>
<html>
  <head>
    <title>Streaming Water Level</title>
    <style>
      #chart {
        min-height: 300px;
      }
    </style>
    <link
      rel="stylesheet"
      href="//maxcdn.bootstrapcdn.com/bootstrap/3.2.0/css/bootstrap.min.css">
  </head>
  <body>
    <div class="container">
    <h4 class="label label-primary">{ 'water level' }</h4>
    <div id="chart"></div>
  </body>
  <script
    src="//ajax.googleapis.com/ajax/libs/jquery/1.11.1/jquery.min.js">
  </script>
  <script
    src="//cdnjs.cloudflare.com/ajax/libs/flot/0.8.2/jquery.flot.min.js">
  </script>
  <script
    src="//cdnjs.cloudflare.com/ajax/libs/flot/0.8.2/jquery.flot.time.min.js">
  </script>
  <script>
  var chart;
  function get_data() {
    $.ajax({
        url: '/data',
        type: 'GET',
        dataType: 'json',
        success: on_data
    });
  }
  function on_data(data) {
    chart.setData([{data: data.values}]);
    chart.setupGrid();
    chart.draw();
    setTimeout(get_data, 1000);
  }
  $(function() {
    chart = $.plot("#chart", [ ], {xaxis: {mode: "time"}});
    get_data();
  });
    </script>
</html>
''')

app = Flask(__name__)


TANK_HEIGHT = 2000
MAX_DATA_POINTS = 100
# In memory RRDB
values = deque(maxlen=MAX_DATA_POINTS)
np.random.seed(0)


def poll_data():
    # random_water_level()
    water_level()


def random_water_level():
    while True:
        level = np.random.choice(range(100))
        values.append((time.time(), level))
        time.sleep(3)




# -----------------------
# R-pi GPIO from ultrasonic sensor
# -----------------------

# Define GPIO to use on Pi
GPIO_TRIGGER = 23
GPIO_ECHO    = 24
# Speed of sound in cm/s at temperature
temperature = 20
speedSound = 33100 + (0.6*temperature)


def measure():
    # This function measures a distance
    GPIO.output(GPIO_TRIGGER, True)
    # Wait 10us
    time.sleep(0.00001)
    GPIO.output(GPIO_TRIGGER, False)
    start = time.time()

    while GPIO.input(GPIO_ECHO)==0:
        start = time.time()

    while GPIO.input(GPIO_ECHO)==1:
        stop = time.time()

    elapsed = stop-start
    distance = (elapsed * speedSound)/2

    return distance

def measure_average():
    # This function takes 3 measurements and
    # returns the average.

    distance1=measure()
    time.sleep(0.1)
    distance2=measure()
    time.sleep(0.1)
    distance3=measure()
    distance = distance1 + distance2 + distance3
    distance = distance / 3
    return distance


def water_level():
    # Use BCM GPIO references
    # instead of physical pin numbers
    GPIO.setmode(GPIO.BCM)

    #print("Ultrasonic Measurement")
    #print("Speed of sound is",speedSound/100,"m/s at ",temperature,"deg")

    # Set pins as output and input
    GPIO.setup(GPIO_TRIGGER,GPIO.OUT)  # Trigger
    GPIO.setup(GPIO_ECHO,GPIO.IN)      # Echo

    # Set trigger to False (Low)
    GPIO.output(GPIO_TRIGGER, False)

    # Allow module to settle
    time.sleep(0.5)

    # Wrap main content in a try block so we can
    # catch the user pressing CTRL-C and run the
    # GPIO cleanup function. This will also prevent
    # the user seeing lots of unnecessary error
    # messages.
    try:
        while True:
            distance = measure_average()
            water_lvl = max(0, TANK_HEIGHT - distance) / TANK_HEIGHT
            #print("Distance : {0:5.1f}".format(distance))
            if len(values) > MAX_DATA_POINTS:
                values.popleft()
            values.append((time.time(), water_lvl))
            time.sleep(1)

    except KeyboardInterrupt:
        # User pressed CTRL-C
        # Reset GPIO settings
        GPIO.cleanup()


#-----------------------------------------------------------------------------


# -----------------------
# Main App Script
# -----------------------

@app.route('/')
def home():
    return html.render()


@app.route('/data')
def data():
    # * 1000 to convert to javascript time
    return jsonify(values=[(int(t)*1000, val) for t, val in list(values)])


def main(argv=None):
    # global stock

    import sys


    thr = Thread(target=poll_data)
    thr.daemon = True
    thr.start()

    # stock = args.stock  # For html template
    # debug will reload server on code changes
    # 0.0.0.0 means listen on all interfaces
    app.run(host='0.0.0.0', debug=True)


if __name__ == '__main__':
    main()

