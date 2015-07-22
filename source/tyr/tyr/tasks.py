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

import glob
import logging
import os
import shutil

from celery import chain
from celery.signals import task_postrun
from flask import current_app
import kombu

from tyr.binarisation import gtfs2ed, osm2ed, ed2nav, fusio2ed, geopal2ed, fare2ed, poi2ed, synonym2ed, shape2ed, \
    load_bounding_shape
from tyr.binarisation import reload_data, move_to_backupdirectory
from tyr import celery
from navitiacommon import models, task_pb2, utils
from tyr.helper import load_instance_config, get_instance_logger
from navitiacommon.launch_exec import launch_exec


@celery.task()
def finish_job(job_id):
    """
    use for mark a job as done after all the required task has been executed
    """
    job = models.Job.query.get(job_id)
    job.state = 'done'
    models.db.session.commit()


def import_data(files, instance, backup_file, async=True, reload=True, custom_output_dir=None):
    """
    import the data contains in the list of 'files' in the 'instance'

    :param files: files to import
    :param instance: instance to receive the data
    :param backup_file: If True the files are moved to a backup directory, else they are not moved
    :param async: If True all jobs are run in background, else the jobs are run in sequence the function will only return when all of them are finish
    :param reload: If True kraken would be reload at the end of the treatment

    run the whole data import process:

    - data import in bdd (fusio2ed, gtfs2ed, poi2ed, ...)
    - export bdd to nav file
    - update the jormungandr db with the new data for the instance
    - reload the krakens
    """
    actions = []
    job = models.Job()
    instance_config = load_instance_config(instance.name)
    job.instance = instance
    job.state = 'pending'
    task = {
        'gtfs': gtfs2ed,
        'fusio': fusio2ed,
        'osm': osm2ed,
        'geopal': geopal2ed,
        'fare': fare2ed,
        'poi': poi2ed,
        'synonym': synonym2ed,
        'shape': shape2ed,
    }

    for _file in files:
        filename = None

        dataset = models.DataSet()
        # NOTE: for the moment we do not use the path to load the data here
        # but we'll need to refactor this to take it into account
        dataset.type, _ = utils.type_of_data(_file)
        dataset.family_type = utils.family_of_data(dataset.type)
        if dataset.type in task:
            if backup_file:
                filename = move_to_backupdirectory(_file,
                                                   instance_config.backup_directory)
            else:
                filename = _file
            actions.append(task[dataset.type].si(instance_config, filename))
        else:
            #unknown type, we skip it
            current_app.logger.debug("unknwn file type: {} for file {}"
                                     .format(dataset.type, _file))
            continue

        #currently the name of a dataset is the path to it
        dataset.name = filename
        models.db.session.add(dataset)
        job.data_sets.append(dataset)

    if actions:
        models.db.session.add(job)
        models.db.session.commit()
        for action in actions:
            action.kwargs['job_id'] = job.id
        #We pass the job id to each tasks, but job need to be commited for
        #having an id
        binarisation = [ed2nav.si(instance_config, job.id, custom_output_dir)]
        #We pass the job id to each tasks, but job need to be commited for
        #having an id
        actions.append(chain(*binarisation))
        if reload:
            actions.append(reload_data.si(instance_config, job.id))
        actions.append(finish_job.si(job.id))
        if async:
            chain(*actions).delay()
        else:
            # all job are run in sequence and import_data will only return when all the jobs are finish
            chain(*actions).apply()


@celery.task()
def update_data():
    for instance in models.Instance.query.all():
        current_app.logger.debug("Update data of : {}".format(instance.name))
        instance_config = load_instance_config(instance.name)
        files = glob.glob(instance_config.source_directory + "/*")
        import_data(files, instance, backup_file=True)

@celery.task()
def purge_instance(instance_id, nb_to_keep):
    instance = models.Instance.query.get(instance_id)
    logger = get_instance_logger(instance)
    logger.info('purge of backup directories for %s', instance.name)
    instance_config = load_instance_config(instance.name)
    backups = set(glob.glob('{}/*'.format(instance_config.backup_directory)))
    logger.info('backups are: %s', backups)
    # we add the realpath not to have problems with double / or stuff like that
    loaded = set(os.path.realpath(os.path.dirname(dataset.name))
                 for dataset in instance.last_datasets(nb_to_keep))
    logger.info('loaded  data are: %s', loaded)
    to_remove = [os.path.join(instance_config.backup_directory, f) for f in backups - loaded]

    missing = [l for l in loaded if l not in backups]
    if missing:
        logger.error("MISSING backup files! impossible to find %s in the backup dir, "
                     "we skip the purge, repair ASAP to fix the purge", missing)
        return

    logger.info('we remove: %s', to_remove)
    for path in to_remove:
        shutil.rmtree(path)




@celery.task()
def scan_instances():
    for instance_file in glob.glob(current_app.config['INSTANCES_DIR'] + '/*.ini'):
        instance_name = os.path.basename(instance_file).replace('.ini', '')
        instance = models.Instance.query.filter_by(name=instance_name).first()
        if not instance:
            current_app.logger.info('new instances detected: %s', instance_name)
            instance = models.Instance(name=instance_name)
            instance_config = load_instance_config(instance.name)
            instance.is_free = instance_config.is_free

            models.db.session.add(instance)
            models.db.session.commit()


@celery.task()
def reload_kraken(instance_id):
    instance = models.Instance.query.get(instance_id)
    job = models.Job()
    job.instance = instance
    job.state = 'pending'
    instance_config = load_instance_config(instance.name)
    models.db.session.add(job)
    models.db.session.commit()
    chain(reload_data.si(instance_config, job.id), finish_job.si(job.id)).delay()
    logging.info("Task reload kraken for instance {} queued".format(instance.name))


@celery.task()
def build_all_data():
    for instance in models.Instance.query.all():
        build_data(instance)


@celery.task()
def build_data(instance):
    job = models.Job()
    job.instance = instance
    job.state = 'pending'
    instance_config = load_instance_config(instance.name)
    models.db.session.add(job)
    models.db.session.commit()
    chain(ed2nav.si(instance_config, job.id, None), finish_job.si(job.id)).delay()
    current_app.logger.info("Job build data of : %s queued"%instance.name)


@celery.task()
def load_data(instance_id, data_dirs):
    instance = models.Instance.query.get(instance_id)
    files = [f for directory in data_dirs for f in glob.glob(directory + "/*")]

    import_data(files, instance, backup_file=False, async=False)


@celery.task()
def cities(osm_path):
    """ launch cities """
    res = -1
    try:
        res = launch_exec("cities", ['-i', osm_path,
                                      '--connection-string',
                                      current_app.config['CITIES_DATABASE_URI']],
                          logging)
        if res!=0:
            logging.error('cities failed')
    except:
        logging.exception('')
    logging.info('Import of cities finished')
    return res


@celery.task()
def bounding_shape(instance_name, shape_path):
    """ Set the bounding shape to a custom value """

    instance_conf = load_instance_config(instance_name)

    load_bounding_shape(instance_name, instance_conf, shape_path)


@task_postrun.connect
def close_session(*args, **kwargs):
    # Flask SQLAlchemy will automatically create new sessions for you from
    # a scoped session factory, given that we are maintaining the same app
    # context, this ensures tasks have a fresh session (e.g. session errors
    # won't propagate across tasks)
    models.db.session.remove()


@celery.task()
def heartbeat():
    """
    send a heartbeat to all kraken
    """
    logging.info('ping krakens!!')
    with kombu.Connection(current_app.config['CELERY_BROKER_URL']) as connection:
        instances = models.Instance.query.all()
        task = task_pb2.Task()
        task.action = task_pb2.HEARTBEAT

        for instance in instances:
            config = load_instance_config(instance.name)
            exchange = kombu.Exchange(config.exchange, 'topic', durable=True)
            producer = connection.Producer(exchange=exchange)
            producer.publish(task.SerializeToString(), routing_key='{}.task.heartbeat'.format(instance.name))

