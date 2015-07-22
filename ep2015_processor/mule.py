#!/usr/bin/env python
# -*- coding: utf-8 -*-

import beanstalkc
import consulate
import signal

from time import sleep

run = True


def get_local_datacenter(consul_local):
    """Returns the name of the local datacenter.
    """
    datacenter = consul_local.agent._get(['self'])['Config']['Datacenter']
    return datacenter


def synchronize_datacenter(consul_local, datacenter):
    """Synchronize or bootstrap the local datacenter k/v store
    with all the other datacenters available.
    """
    color = 'white'
    count_key = 'count/{}'.format(datacenter)

    # acquire the lock
    sid = get_lock(consul_local, datacenter)

    # get all the remote datacenters available
    datacenters = get_datacenters_from_consul(consul_local)
    datacenters.remove(datacenter)
    for dc in datacenters:
        consul_dc = consulate.Consul(datacenter=dc)

        # synchronize the configured color locally
        color_dc = consul_dc.kv.get('color')
        if color_dc:
            print('({}) synchronized from={} color={}'.format(datacenter, dc,
                                                              color_dc))
            consul_local.kv['color'] = color_dc

        # synchronize the remote datacenter count locally
        count_dc_key = 'count/{}'.format(dc)
        count_dc = consul_dc.kv.get(count_dc_key, 0)
        consul_local.kv[count_dc_key] = count_dc
        print('({}) synchronized from={} {}={}'.format(datacenter, dc,
                                                       count_dc_key, count_dc))
        del consul_dc

    # (re)set local datacenter count value
    consul_local.kv[count_key] = consul_local.kv.get(count_key, 0)

    # release the lock
    release_lock(consul_local, datacenter, sid)


def get_datacenters_from_consul(consul_local):
    """Returns a list of all the datacenters from our topology.
    """
    # when there is only one datacenter, this returns a string
    datacenters = consul_local.catalog.datacenters()
    if isinstance(datacenters, list):
        datacenters = set(datacenters)
    else:
        datacenters = set([datacenters])
    return datacenters


def get_beanstalkd_from_consul(consul_local, datacenter, previous_beanstalkds):
    """Returns a list of all the beanstalkd services
    available in our datacenter.
    """
    beanstalkds = {}
    beanstalkds = consul_local.catalog.service('beanstalkd')
    if beanstalkds != previous_beanstalkds:
        print('({}) discovered {} beanstalkd services'.format(
            datacenter, len(beanstalkds)))
    return beanstalkds


def get_lock(consul_local, datacenter):
    """Create a consul session used to acquire a k/v lock.
    https://www.consul.io/docs/internals/sessions.html
    """
    lock_key = 'lock/{}'.format(datacenter)
    sid = consul_local.session.create(ttl='30s')
    while not consul_local.kv.acquire_lock(lock_key, sid):
        print('waiting for lock on {}...'.format(datacenter))
        sleep(0.2)
    print('lock acquired on {}'.format(datacenter))
    return sid


def release_lock(consul_local, datacenter, sid):
    """Release the lock and destroy the local session.
    """
    lock_key = 'lock/{}'.format(datacenter)
    consul_local.kv.release_lock(lock_key, sid)
    consul_local.session.destroy(sid)
    print('lock released')


def set_kv_count_or_key(consul_local, datacenter, jobs):
    """Safely increment the counter or set the given key/value.

    To speed up mass hit counter increase (heavy request load),
    we aggregate the count and set it once per job batch.
    """
    # acquire the lock
    sid = get_lock(consul_local, datacenter)

    # get the current count
    count_key = 'count/{}'.format(datacenter)
    count = int(consul_local.kv.get(count_key, 0))
    count_inc = 0

    # iterate over the jobs
    for job in jobs:
        # our operation depends on the job type
        if job.body == 'hit':
            count_inc += 1
        elif job.body[:3] == 'key':
            op, key, value = job.body.split('|', 2)
            set_kv_on_all_datacenters(consul_local, datacenter, key, value)
        job.delete()

    # set the count once (aggregated operation) for max performance
    # only when it was incremented by a hit job
    if count_inc > 0:
        count += count_inc
        set_kv_on_all_datacenters(consul_local, datacenter, count_key, count)

    # release the lock
    release_lock(consul_local, datacenter, sid)


def set_kv_on_all_datacenters(consul_local, datacenter, key, value):
    """Set the given key/value on every available datacenter.
    """
    datacenters = get_datacenters_from_consul(consul_local)
    for dc in datacenters:
        consul_dc = consulate.Consul(datacenter=dc)
        consul_dc.kv[key] = value
        print('({}) set k/v {}={}'.format(dc, key, value))
        del consul_dc


def graceful_reload(signum, traceback):
    """This will break the loop and gracefully reload this process.
    """
    global run
    print('graceful reload requested')
    run = False


def main():
    """The main logic is described here.
    NB: we process jobs in batch of 200 max. to handle heavy loads seamlessly.
    """
    # get a connection to our local agent
    consul_local = consulate.Consul()

    # get the name of our local datacenter
    datacenter = get_local_datacenter(consul_local)

    # ensure that our datacenter is in sync with all the others
    synchronize_datacenter(consul_local, datacenter)

    beanstalkds = {}
    while run:
        # discover all the beanstalkd services on our datacenter
        beanstalkds = get_beanstalkd_from_consul(consul_local, datacenter,
                                                 beanstalkds)

        # job polling over available beanstalkd services
        run_jobs_count = 0
        for node in beanstalkds:
            bh = node['Node']
            try:
                beanstalk = beanstalkc.Connection(host=bh, connect_timeout=2)
                jobs_count = min(
                    beanstalk.stats_tube('default')['current-jobs-ready'], 200)
                run_jobs_count += jobs_count
                jobs = []
                for _ in xrange(jobs_count):
                    job = beanstalk.reserve(timeout=0.1)
                    if job:
                        jobs.append(job)
                    else:
                        break
                if jobs:
                    print('({}) {}: {} jobs'.format(datacenter, bh, len(jobs)))
                    set_kv_count_or_key(consul_local, datacenter, jobs)
                beanstalk.close()
            except Exception as err:
                print('({}) {}: exception {}'.format(datacenter, bh, err))
            finally:
                # graceful reload requested, stop
                if not run:
                    break

        # slow down when idle (load control)
        if run_jobs_count == 0:
            sleep(1)

# uWSGI will send a SIGHUP to request shutdown
signal.signal(signal.SIGHUP, graceful_reload)

# run the mule
main()
