#!/usr/bin/env python
# -*- coding: utf-8 -*-

# if you want to use gevent, you do NOT need to monkey patch
# thanks to the uwsgi option gevent-monkey-patch = true in the INI
# from gevent import monkey
# monkey.patch_all()

import beanstalkc
import consulate

from flask import Flask
from flask import render_template

beanstalk = beanstalkc.Connection(connect_timeout=5)
consul = consulate.Consul()
ep2015 = Flask(__name__)

try:
    datacenter = consul.agent._get(['self'])['Config']['Datacenter']
except Exception:
    datacenter = 'unknown'


def get_data_from_consul():
    """Return the color configuration and the count/ sum of all
    datacenters from the consul k/v store.
    """
    all_counts = consul.kv.find('count/')
    color = consul.kv.get('color', 'white')
    total_count = 0
    for v in all_counts.values():
        try:
            total_count += int(v)
        except Exception as err:
            pass
    return all_counts, color, total_count


@ep2015.route('/aws_elb_check')
def elb():
    """AWS Elastic Load Balancer health check.
    """
    return 'OK'


@ep2015.route('/')
def show_count():
    """Main page displays the counter with the configured color background.
    """
    # insert a hit count job in beanstalkd
    beanstalk.put('hit')

    # get the global hit count and the configured color from consul
    all_counts, color, count = get_data_from_consul()

    # render the page to the user
    return render_template('index.html',
                           all_counts=all_counts,
                           color=color,
                           count=count,
                           datacenter=datacenter)


@ep2015.route('/set_kv/<string:key>/<string:value>')
def set_kv(key, value):
    """Main page displays the counter with the configured color background.
    Here we use beanstalkd priority mechanism to make sure that those k/v
    jobs are processed ASAP whatever the load on hit jobs.
    """
    beanstalk.put('key|{}|{}'.format(key, value), priority=1)
    return 'OK'
