# Copyright (c) 2001-2014, Canal TP and/or its affiliates. All rights reserved.
#
# This file is part of Navitia,
#     the software to build cool stuff with public transport.
#
# Hope you'll enjoy and contribute to this project,
#     powered by Canal TP (www.canaltp.fr).
# Help us simplify mobility and open public transport:
#     a non ending quest to the responsive locomotion way of traveling!
#
# LICENCE: This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
# Stay tuned using
# twitter @navitia
# IRC #navitia on freenode
# https://groups.google.com/d/forum/navitia
# www.navitia.io

"""
Functions to launch the binaratisations
"""
import logging
import os
import zipfile
import datetime
import shutil
from functools import wraps

from flask import current_app
import kombu
from shapely.geometry import MultiPolygon
from shapely import wkt
import sqlalchemy

from navitiacommon.launch_exec import launch_exec
import navitiacommon.task_pb2
from tyr import celery, redis
from navitiacommon import models
from tyr.helper import get_instance_logger


def move_to_backupdirectory(filename, working_directory):
    """ If there is no backup directory it creates one in
        {instance_directory}/backup/{name}
        The name of the backup directory is the time when it's created
        formatted as %Y%m%d-%H%M%S
    """
    now = datetime.datetime.now()
    working_directory += "/" + now.strftime("%Y%m%d-%H%M%S%f")
    os.mkdir(working_directory, 0755)
    destination = working_directory + '/' + os.path.basename(filename)
    shutil.move(filename, destination)
    return destination


def make_connection_string(instance_config):
    """ Make a connection string connection from the config """
    connection_string = 'host=' + instance_config.pg_host
    connection_string += ' user=' + instance_config.pg_username
    connection_string += ' dbname=' + instance_config.pg_dbname
    connection_string += ' password=' + instance_config.pg_password
    return connection_string

class Lock(object):
    def __init__(self, timeout):
        self.timeout = timeout
    def __call__(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            job_id = None
            if 'job_id' in kwargs:
                job_id = kwargs['job_id']
            else:
                job_id = args[func.func_code.co_varnames.index('job_id')]
            logging.debug('args: %s -- kwargs: %s', args, kwargs)
            job = models.Job.query.get(job_id)
            logger = get_instance_logger(job.instance)
            lock = redis.lock('tyr.lock|' + job.instance.name, timeout=self.timeout)
            if not lock.acquire(blocking=False):
                logger.info('lock on %s retry %s in 300sec', job.instance.name, func.__name__)
                task = args[func.func_code.co_varnames.index('self')]
                task.retry(countdown=60, max_retries=10)
            else:
                try:
                    logger.debug('lock acquired on %s for %s', job.instance.name, func.__name__)
                    return func(*args, **kwargs)
                finally:
                    logger.debug('release lock on %s for %s', job.instance.name, func.__name__)
                    lock.release()
        return wrapper


#TODO bind task
@celery.task(bind=True)
@Lock(timeout=30*60)
def fusio2ed(self, instance_config, filename, job_id):
    """ Unzip fusio file and launch fusio2ed """

    job = models.Job.query.get(job_id)
    instance = job.instance

    logger = get_instance_logger(instance)
    try:
        working_directory = os.path.dirname(filename)

        zip_file = zipfile.ZipFile(filename)
        zip_file.extractall(path=working_directory)

        params = ["-i", working_directory]
        if instance_config.aliases_file:
            params.append("-a")
            params.append(instance_config.aliases_file)

        if instance_config.synonyms_file:
            params.append("-s")
            params.append(instance_config.synonyms_file)

        connection_string = make_connection_string(instance_config)
        params.append("--connection-string")
        params.append(connection_string)
        res = launch_exec("fusio2ed", params, logger)
        if res != 0:
            raise ValueError('fusio2ed failed')
    except:
        logger.exception('')
        job.state = 'failed'
        models.db.session.commit()
        raise


@celery.task(bind=True)
@Lock(30*60)
def gtfs2ed(self, instance_config, gtfs_filename, job_id):
    """ Unzip gtfs file launch gtfs2ed """

    job = models.Job.query.get(job_id)
    instance = job.instance

    logger = get_instance_logger(instance)
    try:
        working_directory = os.path.dirname(gtfs_filename)

        zip_file = zipfile.ZipFile(gtfs_filename)
        zip_file.extractall(path=working_directory)

        params = ["-i", working_directory]
        if instance_config.aliases_file:
            params.append("-a")
            params.append(instance_config.aliases_file)

        if instance_config.synonyms_file:
            params.append("-s")
            params.append(instance_config.synonyms_file)

        connection_string = make_connection_string(instance_config)
        params.append("--connection-string")
        params.append(connection_string)
        res = launch_exec("gtfs2ed", params, logger)
        if res != 0:
            raise ValueError('gtfs2ed failed')
    except:
        logger.exception('')
        job.state = 'failed'
        models.db.session.commit()
        raise


@celery.task(bind=True)
@Lock(timeout=30*60)
def osm2ed(self, instance_config, osm_filename, job_id):
    """ launch osm2ed """

    job = models.Job.query.get(job_id)
    instance = job.instance

    logger = get_instance_logger(instance)
    try:
        connection_string = make_connection_string(instance_config)
        res = launch_exec('osm2ed',
                ["-i", osm_filename, "--connection-string", connection_string],
                logger)
        if res != 0:
            #@TODO: exception
            raise ValueError('osm2ed failed')
    except:
        logger.exception('')
        job.state = 'failed'
        models.db.session.commit()
        raise

@celery.task(bind=True)
@Lock(timeout=30*60)
def geopal2ed(self, instance_config, filename, job_id):
    """ launch geopal2ed """

    job = models.Job.query.get(job_id)
    instance = job.instance
    logger = get_instance_logger(instance)
    try:
        working_directory = os.path.dirname(filename)

        zip_file = zipfile.ZipFile(filename)
        zip_file.extractall(path=working_directory)

        connection_string = make_connection_string(instance_config)
        res = launch_exec('geopal2ed',
                ["-i", working_directory, "--connection-string", connection_string],
                logger)
        if res != 0:
            #@TODO: exception
            raise ValueError('geopal2ed failed')
    except:
        logger.exception('')
        job.state = 'failed'
        models.db.session.commit()
        raise

@celery.task(bind=True)
@Lock(timeout=10*60)
def poi2ed(self, instance_config, filename, job_id):
    """ launch poi2ed """

    job = models.Job.query.get(job_id)
    instance = job.instance
    logger = get_instance_logger(instance)
    try:
        working_directory = os.path.dirname(filename)

        zip_file = zipfile.ZipFile(filename)
        zip_file.extractall(path=working_directory)

        connection_string = make_connection_string(instance_config)
        res = launch_exec('poi2ed',
                ["-i", working_directory, "--connection-string", connection_string],
                logger)
        if res != 0:
            #@TODO: exception
            raise ValueError('poi2ed failed')
    except:
        logger.exception('')
        job.state = 'failed'
        models.db.session.commit()
        raise

@celery.task(bind=True)
@Lock(timeout=10*60)
def synonym2ed(self, instance_config, filename, job_id):
    """ launch synonym2ed """

    job = models.Job.query.get(job_id)
    instance = job.instance

    logger = get_instance_logger(instance)
    try:
        connection_string = make_connection_string(instance_config)
        res = launch_exec('synonym2ed',
                ["-i", filename, "--connection-string", connection_string],
                logger)
        if res != 0:
            #@TODO: exception
            raise ValueError('synonym2ed failed')
    except:
        logger.exception('')
        job.state = 'failed'
        models.db.session.commit()
        raise


# from http://wiki.openstreetmap.org/wiki/Osmosis/Polygon_Filter_File_Python_Parsing
def parse_poly(lines):
    """ Parse an Osmosis polygon filter file.

        Accept a sequence of lines from a polygon file, return a shapely.geometry.MultiPolygon object.

        http://wiki.openstreetmap.org/wiki/Osmosis/Polygon_Filter_File_Format
    """
    in_ring = False
    coords = []

    for (index, line) in enumerate(lines):
        if index == 0:
            # first line is junk.
            continue

        elif index == 1:
            # second line is the first polygon ring.
            coords.append([[], []])
            ring = coords[-1][0]
            in_ring = True

        elif in_ring and line.strip() == 'END':
            # we are at the end of a ring, perhaps with more to come.
            in_ring = False

        elif in_ring:
            # we are in a ring and picking up new coordinates.
            ring.append(map(float, line.split()))

        elif not in_ring and line.strip() == 'END':
            # we are at the end of the whole polygon.
            break

        elif not in_ring and line.startswith('!'):
            # we are at the start of a polygon part hole.
            coords[-1][1].append([])
            ring = coords[-1][1][-1]
            in_ring = True

        elif not in_ring:
            # we are at the start of a polygon part.
            coords.append([[], []])
            ring = coords[-1][0]
            in_ring = True

    return MultiPolygon(coords)


def load_bounding_shape(instance_name, instance_conf, shape_path):
    logging.info("loading bounding shape for {} from = {}".format(instance_name, shape_path))

    if shape_path.endswith(".poly"):
        with open(shape_path, "r") as myfile:
            shape = parse_poly(myfile.readlines())
    elif shape_path.endswith(".wkt"):
        with open(shape_path, "r") as myfile:
            shape = wkt.loads(myfile.read())
    else:
        logging.error("bounding_shape: {} has an unknown extension.".format(shape_path))
        return

    connection_string = "postgres://{u}:{pw}@{h}/{db}"\
        .format(u=instance_conf.pg_username, pw=instance_conf.pg_password,
                h=instance_conf.pg_host, db=instance_conf.pg_dbname)
    engine = sqlalchemy.create_engine(connection_string)
    # create the line if it does not exists
    engine.execute("""
    INSERT INTO navitia.parameters (shape)
    SELECT NULL WHERE NOT EXISTS (SELECT * FROM navitia.parameters)
    """).close()
    # update the line, simplified to approx 100m
    engine.execute("""
    UPDATE navitia.parameters
    SET shape_computed = FALSE, shape = ST_Multi(ST_SimplifyPreserveTopology(ST_GeomFromText('{shape}'), 0.001))
    """.format(shape=wkt.dumps(shape))).close()


@celery.task(bind=True)
@Lock(timeout=10*60)
def shape2ed(self, instance_config, filename, job_id):
    """load a street network shape into ed"""
    job = models.Job.query.get(job_id)
    instance = job.instance
    logging.info("loading bounding shape for {} from = {}".format(instance.name, filename))
    load_bounding_shape(instance.name, instance_config, filename)


@celery.task(bind=True)
def reload_data(self, instance_config, job_id):
    """ reload data on all kraken of this instance"""
    job = models.Job.query.get(job_id)
    instance = job.instance
    logging.info("Unqueuing job {}, reload data of instance {}".format(job.id, instance.name))
    logger = get_instance_logger(instance)
    try:
        task = navitiacommon.task_pb2.Task()
        task.action = navitiacommon.task_pb2.RELOAD

        connection = kombu.Connection(current_app.config['CELERY_BROKER_URL'])
        exchange = kombu.Exchange(instance_config.exchange, 'topic',
                                  durable=True)
        producer = connection.Producer(exchange=exchange)

        logger.info("reload kraken")
        producer.publish(task.SerializeToString(),
                routing_key=instance.name + '.task.reload')
        connection.release()
    except:
        logger.exception('')
        job.state = 'failed'
        models.db.session.commit()
        raise


@celery.task(bind=True)
@Lock(10*60)
def ed2nav(self, instance_config, job_id, custom_output_dir):
    """ Launch ed2nav"""
    job = models.Job.query.get(job_id)
    instance = job.instance

    logger = get_instance_logger(instance)
    try:
        output_file = instance_config.target_file

        if custom_output_dir:
            # we change the target_filename to store it in a subdir
            target_path = os.path.join(os.path.dirname(output_file), custom_output_dir)
            output_file = os.path.join(target_path, os.path.basename(output_file))
            if not os.path.exists(target_path):
                os.makedirs(target_path)


        connection_string = make_connection_string(instance_config)
        argv = ["-o", output_file, "--connection-string", connection_string]
        if 'CITIES_DATABASE_URI' in current_app.config and current_app.config['CITIES_DATABASE_URI']:
            argv.extend(["--cities-connection-string", current_app.config['CITIES_DATABASE_URI']])

        res = launch_exec('ed2nav', argv, logger)
        if res != 0:
            raise ValueError('ed2nav failed')
    except:
        logger.exception('')
        job.state = 'failed'
        models.db.session.commit()
        raise

@celery.task(bind=True)
@Lock(timeout=10*60)
def fare2ed(self, instance_config, filename, job_id):
    """ launch fare2ed """

    job = models.Job.query.get(job_id)
    instance = job.instance

    logger = get_instance_logger(instance)
    try:
        working_directory = os.path.dirname(filename)

        zip_file = zipfile.ZipFile(filename)
        zip_file.extractall(path=working_directory)

        res = launch_exec("fare2ed", ['-f', working_directory,
                                      '--connection-string',
                                      make_connection_string(instance_config)],
                          logger)
        if res != 0:
            #@TODO: exception
            raise ValueError('fare2ed failed')
    except:
        logger.exception('')
        job.state = 'failed'
        models.db.session.commit()
        raise
