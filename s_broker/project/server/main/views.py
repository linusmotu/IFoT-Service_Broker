from flask import render_template, jsonify, request, current_app, Blueprint
from flask import send_from_directory, url_for, redirect
import requests
from werkzeug.utils import secure_filename
from ..models.models import Node
from ..forms.upload_form import UploadForm, TextForm, Nuts2Form, DateForm, create_data_form
from rq import Queue, Connection
import redis
import os
from project.server.main.tasks import create_task
import json
from rq.registry import StartedJobRegistry, FinishedJobRegistry
import urllib.request, json
from flask_cors import CORS, cross_origin
import csv
from . import funcs

from datetime import datetime
from dateutil import tz
import time

#Move to constants file.
NODE_COUNT = '_node_count'
DONE_NODE_COUNT = '_done_node_count'
NODES = '_nodes'

main_blueprint = Blueprint('main', __name__,)

@main_blueprint.route('/', methods=['GET'])
def home():
  n = Node(name='Master')
  print(n)
  return render_template('main/home.html', debug=n)

#https://stackoverflow.com/questions/40963401/flask-dynamic-data-update-without-reload-page
#Add this step in dt.js and also here. so that it will reload

#also this: https://github.com/saltycrane/flask-jquery-ajax-example inside fjae folder
#https://stackoverflow.com/questions/34618956/javascript-ajax-to-dynamically-update-wtforms-select-field

#https://stackoverflow.com/questions/233553/how-do-i-pre-populate-a-jquery-datepicker-textbox-with-todays-date
#need to be able to populate the datefields on button press (jquery)
@main_blueprint.route('/dt', methods=['GET', 'POST'])
def dt():
  # form = DateForm()
  json = {"influx_ip": '163.221.68.206'}
  r = requests.get('http://163.221.68.242:5001/api/dt_get', json=json)
  time_first = r.text.split(";")[0]
  time_last = r.text.split(";")[1]

  from_zone = tz.tzutc()
  to_zone = tz.tzlocal()

  # 1537323289425,1533650065704

  ts = int(time_first)
  ts /= 1000
  utc = datetime.utcfromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
  first_local = datetime.strptime(utc, '%Y-%m-%d %H:%M:%S').replace(tzinfo=from_zone).astimezone(to_zone)
  time_first = first_local.strftime('%Y-%m-%d %H:%M:%S')

  ts = int(time_last)
  ts /= 1000
  utc = datetime.utcfromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
  last_local = datetime.strptime(utc, '%Y-%m-%d %H:%M:%S').replace(tzinfo=from_zone).astimezone(to_zone)
  time_last = last_local.strftime('%Y-%m-%d %H:%M:%S')

  # st = datetime.strptime("2012-10-10 10:20:40.005", '%Y-%m-%d %H:%M:%S.%f')

  form = create_data_form(first_local, last_local)
  # return "TEST"
  if form.is_submitted():
    print("success submit")
    if form.validate_on_submit():
      print("validate_on_submit")
      feature  = form.feature.data
  return render_template('main/datetime.html', form=form, time_first=time_first, time_last=time_last)

@main_blueprint.route('/upload', methods=['GET', 'POST'])
def upload():
  form = UploadForm()
  if form.validate_on_submit():
    file = form.file.data
    if file and funcs.allowed_file(file.filename):
      filename = secure_filename(file.filename)
      os.makedirs(os.path.join(current_app.instance_path, 'htmlfi'), exist_ok=True)
      file.save(os.path.join(current_app.instance_path, 'htmlfi', filename))

      return redirect(url_for('main.uploaded_file', filename=filename))
  return render_template('main/upload.html', form=form, result=None)

#https://stackoverflow.com/questions/19794695/flask-python-buttons
#https://stackoverflow.com/questions/43811779/use-many-submit-buttons-in-the-same-form
@main_blueprint.route('/iris_classifier', methods=['GET', 'POST'])
def iris_classifier():
  form = UploadForm()
  if request.method == 'POST':
    if form.validate_on_submit():
      file = form.file.data
      if file and funcs.allowed_file(file.filename):
        filename = secure_filename(file.filename)
        os.makedirs(os.path.join(current_app.instance_path, 'htmlfi'), exist_ok=True)
        file.save(os.path.join(current_app.instance_path, 'htmlfi', filename))
        print(filename)
        submit_val = request.form['action']
        print(submit_val)
        if submit_val == 'Single':
          return redirect(url_for('main.start_iris_process', filename=filename))
        elif submit_val == 'Distributed':
          return redirect(url_for('main.start_iris_dist_process', filename=filename))
        else:
          pass # unknown
  elif request.method == 'GET':
      return render_template('main/upload.html', form=form, result=None)

@main_blueprint.route('/nuts_classifier', methods=['GET', 'POST'])
def nuts_classifier():
  #form = TextForm(meta={'csrf_context': request.remote_addr})
  form = TextForm(meta={'csrf_context': 'secret_key'})
  if request.method == 'GET':
    return render_template('main/nuts.html', form=form)
  elif request.method == 'POST':
    if form.validate_on_submit():
      node_count = form.node_count.data
      chunk_count = form.chunk_count.data
      model_type = form.model_type.data
      if node_count > chunk_count:
        return render_template('main/nuts.html', form=form, error='node_count is greater than chunk_count')
      else:
        return jsonify(data={'node_count': node_count, 'chunk_count': chunk_count, 'model_type': model_type})
    elif form.csrf_token.errors:
      return "csrf token error"
      #pass # If we're here we suspect the user of cross-site request forgery
    else:
      return "Error"

#Later on add choice to control the number of nodes and/or the number of data points/chunks/queries at once
@main_blueprint.route('/nuts_dist_process', methods=['GET', 'POST'])
def start_nuts_dist_process():
  form = Nuts2Form()
  if request.method == 'GET':
    return render_template('main/nuts2.html', form=form)
  elif request.method == 'POST':
    if form.validate_on_submit():
      node_count = form.node_count.data
      chunk_count = form.chunk_count.data
      model_type = form.model_type.data
      cluster_address = form.cluster_address.data
      # node_count = request.args.get("node_count")
      # model_type = request.args.get("model_type")
      # chunk_count = request.args.get("chunk_count")

      json = {
              'node_count': node_count,
              'model_type': model_type,
              'chunk_count': chunk_count
              }

      #Can i not hardcode the link?
      res = ''
      if cluster_address == 'pi4':
        res = requests.post('http://163.221.68.242:5001/api/nuts2_classify', json=json)
      elif cluster_address == 'pi5':
        res = requests.post('http://163.221.68.211:5001/api/nuts2_classify', json=json)
      elif cluster_address == 'nuc':
        res = requests.post('http://163.221.68.206:5001/api/nuts2_classify', json=json) 

      #Trigger continuous updates here with time
      return res.text
    else:
      return "Error: validate on submit failed"

#Dist
@main_blueprint.route('/iris_dist_process', methods=['GET', 'POST'])
def start_iris_dist_process():
  # filename = secure_filename(request.args.get("filename"))
  # split(filename, 3)

  filename = secure_filename(request.args.get("filename"))
  redis_conn = redis.from_url(current_app.config['REDIS_URL'])
  print(filename)
  try:
    if filename and funcs.allowed_file(filename):
      u_ID = funcs.generate_unique_ID()
      with open(os.path.join(current_app.instance_path, 'htmlfi', filename)) as f:
        q = Queue(connection = redis_conn)
        nodes = 3
        #Split file into 3
        files = funcs.split(filename, 3)

        funcs.setRedisKV(redis_conn, u_ID, 'ongoing')
        funcs.setRedisKV(redis_conn, u_ID + NODE_COUNT, nodes)
        funcs.setRedisKV(redis_conn, u_ID + DONE_NODE_COUNT, 0)

        #assuming the files are in sequential order, we can send some sequence id to the queue
        for sequence_ID, file in enumerate(files):
          data = file.read()
          #Need to decode?
          #Race condition i think.
          task = q.enqueue('tasks.classify_iris_dist', data, nodes, u_ID, sequence_ID)

      return 'Classifying Distributedly...'
  except IOError:
    pass
  return "Unable to read file"


@main_blueprint.route('/iris_process', methods=['GET', 'POST'])
def start_iris_process():
  filename = secure_filename(request.args.get("filename"))
  redis_conn = redis.from_url(current_app.config['REDIS_URL'])
  print(filename)
  try:
    if filename and funcs.allowed_file(filename):
      with open(os.path.join(current_app.instance_path, 'htmlfi', filename)) as f:
        data = f.read()
        q = Queue(connection = redis_conn)
        task = q.enqueue('tasks.classify_iris', data)
      return 'Classifying...'
  except IOError:
    pass
  return "Unable to read file"

@main_blueprint.route('/uploads/<filename>')
def uploaded_file(filename):
  return send_from_directory(os.path.join(current_app.instance_path, 'htmlfi'), filename)

@main_blueprint.route('/tasks', methods=['POST'])
def run_task():
  task_type = request.form['type']
  #r = redis.StrictRedis(host="163.221.68.242", port=6379, password="", decode_responses=True)
  r = redis.from_url(current_app.config['REDIS_URL'])

  u_ID = funcs.generate_unique_ID()
  with Connection(redis.from_url(current_app.config['REDIS_URL'])):
    q = Queue()
    funcs.setRedisKV(r, u_ID, 'ongoing')
    funcs.setRedisKV(r, u_ID + NODE_COUNT, 1)
    funcs.setRedisKV(r, u_ID + DONE_NODE_COUNT, 0)

    task = q.enqueue('tasks.create_task', task_type, u_ID)
  response_object = {
      'status': 'success',
      'unique_ID': u_ID,
      'data': {
        'task_id': task.get_id()
    }
  }
  return jsonify(response_object), 202
