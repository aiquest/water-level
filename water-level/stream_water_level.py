#!/usr/bin/env python
'''Show streaming graph of water level.'''

from __future__ import print_function
import time
import os
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
import logging
import warnings


# Set time zone
TIME_ZONE =  'Asia/Kolkata'
os.environ['TZ'] = TIME_ZONE
time.tzset()


LOG_FILENAME = '../water-level.log'
logging.basicConfig(filename=LOG_FILENAME,level=logging.DEBUG)


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



#TANK_HEIGHT = 2000
SENSOR_DIST_FROM_TANK_TOP = 10 # cm
SENSOR_DIST_FROM_TANK_BOTTOM = 180 # cm
MAX_DATA_POINTS = 15000 # number of points on plot (history)
UPDATE_INTERVAL = 5 # seconds

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
    stop = time.time()
    elapsed = stop-start
    distance = (elapsed * speedSound)/2

    return distance


def measure_average_old():
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


def reject_outliers(data, m = 2.):
    d = np.abs(data - np.median(data))
    mdev = np.median(d)
    s = d/mdev if mdev else 0.
    return list(np.array(data)[s<m])


def measure_average():
    # This function takes 3 measurements and
    # returns the average.
    
    distance = None
    distances = []
    precision = 2
    for i in range(50):
        try:
            distances.append(measure())
            time.sleep(0.05)
        except Exception, e:
            warnings.warn(str(e))
            logging.debug(str(e))
            #raise
    distances = reject_outliers(distances)
    try:
        distance = np.mean(distances)
        # distance = np.median(distances)
    except Exception, e:
        warnings.warn(str(e))
        logging.info(str(e))
        #raise
        
    return distance


def holt_winters_second_order_ewma( x, span, beta ):
    N = len(x)
    x = np.array(x)
    span = min(N, span)
    alpha = 2.0 / ( 1 + span )
    s = np.zeros(( N, ))
    b = np.zeros(( N, ))
    s[0] = x[0]
    for i in range( 1, N ):
        s[i] = alpha * x[i] + ( 1 - alpha )*( s[i-1] + b[i-1] )
        b[i] = beta * ( s[i] - s[i-1] ) + ( 1 - beta ) * b[i-1]
    return list(np.ravel(s))


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
    last_distance = 0
    distance_history = deque(maxlen=10)
    try:
        while True:
            measured_distance = measure_average()
            if measured_distance is None:
                measured_distance = last_distance
            #elif last_distance > 0 and abs(distance - last_distance)/last_distance > .5:
            #    distance = last_distance
            else:    
                last_distance = measured_distance
            #distance_history.append(measured_distance)
            #distance = np.mean(distance_history)
            #distance = holt_winters_second_order_ewma(distance_history, 10, 0.3)

            distance = measured_distance
            #water_lvl = (max(0, min(SENSOR_DIST_FROM_TANK_BOTTOM 
            #                        - distance 
            #                        - SENSOR_DIST_FROM_TANK_TOP,
            #                        SENSOR_DIST_FROM_TANK_BOTTOM)
            #                )
            #             ) / (SENSOR_DIST_FROM_TANK_BOTTOM 
            #                 - SENSOR_DIST_FROM_TANK_TOP) * 100 

            PRECISION = 1
            #water_lvl = round(water_lvl, PRECISION)            
            
            water_lvl = round(distance, PRECISION) 
            #print("Distance : {0:5.1f}".format(distance))
            if len(values) > MAX_DATA_POINTS:
                values.popleft()
            values.append((time.time(), water_lvl))
            time.sleep(UPDATE_INTERVAL)

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
    app.run(host='0.0.0.0', debug=True, port=5000)


if __name__ == '__main__':
    main()

