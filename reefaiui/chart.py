#!/usr/bin/env python
'''Show streaming graph of stock.'''

from jinja2 import Template
from flask import Flask, jsonify
from six.moves.urllib.request import urlopen
from six.moves.urllib.parse import urlencode

from collections import deque
from threading import Thread
from time import time, sleep
import csv
import codecs
import pymongo
import ConfigParser
from pymongo import MongoClient
from pymongo import ASCENDING, DESCENDING
from datetime import datetime
from bson.json_util import dumps


html = Template('''\
<!DOCTYPE html>
<html>
  <head>
    <title>Reef Ai Temp and Ph readings</title>
    <style>
      .chart {
        min-height: 300px;
      }
    </style>
    <link
      rel="stylesheet"
      href="//maxcdn.bootstrapcdn.com/bootstrap/3.2.0/css/bootstrap.min.css">
  </head>
  <body>
    <div class="container">
    <div id="latest">
      <label>Latest pH</label> <label id="latestph" class="label label-primary"></label>
      <br>
      <label>Latest Temp</label> <label id="latesttemp" class="label label-primary"></label>
      <br>
      <label>Last Reading</label> <label id="latestts" class="label label-primary"></label>
    </div>

    <p>

    <div>
      <label class="label label-default">Combined</label>
      <div id="combinedchart" class="chart"></div>
      
      <br>

      <label class="label label-default">Temp</label>
      <div id="tempchart" class="chart"></div>

      <br>

      <label class="label label-default">Temp</label>
      <div id="phchart" class="chart"></div>
    </div>
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
  var tempchart;
  var phchart;
  var combinedchart;

  function get_data() {
    $.ajax({
        url: '/data',
        type: 'GET',
        dataType: 'json',
        success: on_data
    });
  }

  function on_data(data) {
    combinedchart.setData([
      {label: 'pH', data: data.phvalues, yaxis:1, color: 'red'}, 
      {label: 'temp', data: data.tempvalues, yaxis:2, color: 'blue'}
    ]);

    combinedchart.setupGrid();
    combinedchart.draw();

    phchart.setData([
      {label: 'pH', data: data.phvalues, color: 'red'}, 
    ]);

    phchart.setupGrid();
    phchart.draw();

    tempchart.setData([
      {label: 'temp', data: data.tempvalues, color: 'blue'}, 
    ]);

    tempchart.setupGrid();
    tempchart.draw();

    $('#latestph').text(data.latestph);
    $('#latesttemp').text(data.latesttemp);
    $('#latestts').text(data.latestts);

    setTimeout(get_data, 120000);
  }

  $(function() {
    $("<div id='tooltip'></div>").css({
      position: "absolute",
      display: "none",
      border: "1px solid #fdd",
      padding: "2px",
      "background-color": "#fee",
      opacity: 0.80
    }).appendTo("body");


    combinedchart = $.plot("#combinedchart", [], 
      {xaxis: {mode: "time"},
       yaxes: [{ labelWidth: 40,
                  autoscaleMargin: 0.07,
                  position: 'right'
                },
                { labelWidth: 40,
                  autoscaleMargin: 0.07,
                  position: 'right'
                }
              ],
      grid: {hoverable: true, autoHighlight: true },
      selection:{mode:"x"}
    });
    $("#combinedchart").bind("plothover", detailhover);

    phchart = $.plot("#phchart", [], 
      {xaxis: {mode: "time"},
       yaxes: [{ labelWidth: 40,
                  autoscaleMargin: 0.07,
                  position: 'right'
                },
              ],
      grid: {hoverable: true, autoHighlight: true },
      selection:{mode:"x"}
    });
    $("#phchart").bind("plothover", detailhover);

    tempchart = $.plot("#tempchart", [], 
      {xaxis: {mode: "time"},
       yaxes: [{ labelWidth: 40,
                  autoscaleMargin: 0.07,
                  position: 'right'
                },
              ],
      grid: {hoverable: true, autoHighlight: true },
      selection:{mode:"x"}
    });
    $("#tempchart").bind("plothover", detailhover);

    get_data();
  });

  function detailhover(event, pos, item) {
      if (item) {
        var x = item.datapoint[0],
            y = item.datapoint[1].toFixed(2);

        $("#tooltip").html(item.series.label + " at " + new Date(x) + ": " + y)
          .css({top: item.pageY+5, left: item.pageX+5})
          .fadeIn(200);
      } else {
        $("#tooltip").hide();
      }
  }

    </script>
</html>
''')

app = Flask(__name__)


config = ConfigParser.RawConfigParser()
config.read('../config/config.cfg')

mongo = MongoClient(config.get('main', 'mongo'))
#mongo = MongoClient()

@app.route('/')
def home():
    return html.render()

@app.route('/data')
def data():
    global mongo

    pipeline = [
      {'$project' : {'time' : {'$dateToString' : {'format' : "%Y-%m-%dT%H:%M:00", 'date' : "$ts"}}, 'temp' : 1, 'ph' : 1}},
      {'$group' : {'_id' : "$time", 'ph' : {'$avg' : "$ph"}, 'temp' : {'$avg' : "$temp"}}},
      {'$sort' : {'_id' : -1}},
      {'$limit' : 5000}
    ]

    entries = list(mongo['reef_ai']['readings'].aggregate(pipeline))
    #print entries

    parsedPh = [(int(datetime.strptime(row['_id'],'%Y-%m-%dT%H:%M:%S').strftime('%s')) * 1000 , row['ph']) for row in entries]
    parsedTemp = [(int(datetime.strptime(row['_id'],'%Y-%m-%dT%H:%M:%S').strftime('%s')) * 1000 , row['temp']) for row in entries]

    latestReading = mongo['reef_ai']['readings'].find({}).sort('ts', DESCENDING).limit(1)[0]

    #print latestReading

    return jsonify(phvalues=parsedPh, 
                   tempvalues=parsedTemp, 
                   latestph=format(latestReading['ph'], '.1f'), 
                   latesttemp=format(latestReading['temp'], '.1f'),
                   latestts=latestReading['ts'].strftime('%Y-%m-%dT%H:%M:%S'))


def main(argv=None):
    # debug will reload server on code changes
    # 0.0.0.0 means listen on all interfaces
    app.run(host='0.0.0.0', port=8085, debug=True)


if __name__ == '__main__':
    main()

