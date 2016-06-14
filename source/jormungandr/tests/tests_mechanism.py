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

from __future__ import absolute_import, print_function, unicode_literals, division
import os
# set default config file if not defined in other tests
from datetime import timedelta
from operator import itemgetter
from flask import logging
import mock
import retrying
from retrying import RetryError

if not 'JORMUNGANDR_CONFIG_FILE' in os.environ:
    os.environ['JORMUNGANDR_CONFIG_FILE'] = os.path.dirname(os.path.realpath(__file__)) \
        + '/integration_tests_settings.py'

import subprocess
from .check_utils import *
from jormungandr import app, i_manager
from jormungandr.stat_manager import StatManager
from navitiacommon.models import User
from jormungandr.instance import Instance

krakens_dir = os.environ['KRAKEN_BUILD_DIR'] + '/tests'


class FakeModel(object):
    def __init__(self, priority, is_free):
        self.priority = priority
        self.is_free = is_free
        self.scenario = 'default'


class AbstractTestFixture:
    """
    Mother class for all integration tests

    load the list of kraken defined with the @dataset decorator

    at the end of the tests, kill all kraken

    (the setup() and teardown() methods are called once at the initialization and destruction of the integration tests)
    """
    @classmethod
    def launch_all_krakens(cls):
        for (kraken_name, conf) in cls.data_sets.items():
            additional_args = conf.get('kraken_args', [])
            exe = os.path.join(krakens_dir, kraken_name)
            logging.debug("spawning " + exe)

            assert os.path.exists(exe), "cannot find the kraken {}".format(exe)

            args = [exe] + additional_args

            kraken = subprocess.Popen(args, stderr=None, stdout=None, close_fds=False)

            cls.krakens_pool[kraken_name] = kraken

        logging.debug("{} kraken spawned".format(len(cls.krakens_pool)))

    @classmethod
    def kill_all_krakens(cls):
        for name, kraken_process in cls.krakens_pool.items():
            logging.debug("killing " + name)
            if cls.data_sets[name].get('check_killed', True):
                kraken_process.poll()
                if kraken_process.returncode is not None:
                    logging.error('kraken is dead, check errors, return code = %s', kraken_process.returncode)
                    assert False, 'kraken is dead, check errors, return code'
            kraken_process.kill()

    @classmethod
    def create_dummy_json(cls):
        conf_template_str = ('{{ \n'
                             '    "key": "{instance_name}",\n'
                             '    "zmq_socket": "ipc:///tmp/{instance_name}",\n'
                             '    "realtime_proxies": {proxy_conf}\n'
                             '}}')
        for name in cls.krakens_pool:
            proxy_conf = cls.data_sets[name].get('proxy_conf', '[]')
            with open(os.path.join(krakens_dir, name) + '.json', 'w') as f:
                logging.debug("writing ini file {} for {}".format(f.name, name))
                r = conf_template_str.format(instance_name=name, proxy_conf=proxy_conf)
                f.write(r)

        #we set the env var that will be used to init jormun
        return [
            os.path.join(os.environ['KRAKEN_BUILD_DIR'], 'tests', k + '.json')
            for k in cls.krakens_pool
        ]

    @classmethod
    def setup_class(cls):
        cls.krakens_pool = {}
        logging.info("Initing the tests {}, let's pop the krakens".format(cls.__name__))
        cls.launch_all_krakens()
        instances_config_files = cls.create_dummy_json()
        i_manager.configuration_files = instances_config_files
        i_manager.initialisation()
        cls.mocks = []
        for name in cls.krakens_pool:
            priority = cls.data_sets[name].get('priority', 0)
            logging.info('instance %s has priority %s', name, priority)
            is_free = cls.data_sets[name].get('is_free', False)
            cls.mocks.append(mock.patch.object(i_manager.instances[name],
                                               'get_models',
                                               return_value=FakeModel(priority, is_free)))

        for m in cls.mocks:
            m.start()

        # we check that all instances are up
        for name in cls.krakens_pool:
            instance = i_manager.instances[name]
            try:
                retrying.Retrying(stop_max_delay=5000,
                                  wait_fixed=10,
                                  retry_on_result=lambda x: not instance.is_up).call(instance.init)
            except RetryError:
                logging.exception('impossible to start kraken {}'.format(name))
                assert False, 'impossible to start a kraken'

        #we block the stat manager not to send anything to rabbit mq
        def mock_publish(self, stat):
            pass

        #we don't want to initialize rabbit for test.
        def mock_init():
            pass

        StatManager.publish_request = mock_publish
        StatManager._init_rabbitmq = mock_init

        #we don't want to have anything to do with the jormun database either
        class bob:
            @classmethod
            def mock_get_token(cls, token, valid_until):
                #note, since get_from_token is a class method, we need to wrap it.
                #change that with a real mock framework
                pass
        User.get_from_token = bob.mock_get_token

        @property
        def mock_journey_order(self):
            return 'arrival_time'
        Instance.journey_order = mock_journey_order

    @classmethod
    def teardown_class(cls):
        logging.info("Tearing down the tests {}, time to hunt the krakens down"
                     .format(cls.__name__))
        cls.kill_all_krakens()
        for m in cls.mocks:
            m.stop()

    def __init__(self, *args, **kwargs):
        self.tester = app.test_client()

    # ==============================
    # helpers
    # ==============================
    def query(self, url, display=False, **kwargs):
        """
        Query the requested url, test url status code to 200
        and if valid format response as dict

        display param dumps the json (used only for debug)
        """
        response = check_url(self.tester, url, **kwargs)

        assert response.data
        json_response = json.loads(response.data)

        if display:
            logging.info("loaded response : " + json.dumps(json_response, indent=2))

        assert json_response
        return json_response

    def query_region(self, url, check=True, display=False, version="v1"):
        """
            helper if the test in only one region,
            to shorten the test url query /v1/coverage/{region}/url
        """
        assert len(self.krakens_pool) == 1, "the helper can only work with one region"
        str_url = "/v1/coverage"
        str_url += "/{region}/{url}"
        real_url = str_url.format(region=list(self.krakens_pool)[0], url=url)

        if check:
            return self.query(real_url, display)
        return self.query_no_assert(real_url, display)

    def query_no_assert(self, url, display=False):
        """
        query url without checking the status code
        used to test invalid url
        return tuple with response as dict and status
        """
        response = self.tester.get(url)

        json_response = json.loads(response.data)
        if display:
            logging.info("loaded response : " + json.dumps(json_response, indent=2))

        return json_response, response.status_code

    def check_journeys_links(self, response, query_dict):
        journeys_links = get_links_dict(response)
        for l in ["prev", "next", "first", "last"]:
            assert l in journeys_links
            url = journeys_links[l]['href']

            additional_args = query_from_str(url)
            for k, v in additional_args.items():
                if k == 'datetime':
                    if l == 'next':
                        self.check_next_datetime_link(get_valid_datetime(v), response)
                    elif l == 'prev':
                        self.check_previous_datetime_link(get_valid_datetime(v), response)
                    continue
                if k == 'datetime_represents':
                    query_dt_rep = query_dict.get('datetime_represents', 'departure')
                    if l in ['prev', 'last']:
                        # the datetime_represents is negated
                        if query_dt_rep == 'departure':
                            assert v == 'arrival'
                        else:
                            assert v == 'departure'
                    else:
                        assert query_dt_rep == v

                    continue

                eq_(query_dict[k], v)

    def is_valid_journey_response(self, response, query_str):
        """
        check that the journey's response is valid

        this method is inside AbstractTestFixture because it can be overloaded by not scenario test Fixture
        """
        if isinstance(query_str, basestring):
            query_dict = query_from_str(query_str)
        else:
            query_dict = query_str

        journeys = get_not_null(response, "journeys")

        all_sections = unique_dict('id')
        assert len(journeys) > 0, "we must at least have one journey"
        for j in journeys:
            is_valid_journey(j, self.tester, query_dict)

            for s in j['sections']:
                all_sections[s['id']] = s

        # check the fare section
        # the fares must be structurally valid and all link to sections must be ok
        all_tickets = unique_dict('id')
        fares = response['tickets']
        for f in fares:
            is_valid_ticket(f, self.tester)
            all_tickets[f['id']] = f

        check_internal_links(response, self.tester)

        #check other links
        check_links(response, self.tester)

        # more checks on links, we want the prev/next/first/last,
        # to have forwarded all params, (and the time must be right)
        self.check_journeys_links(response, query_dict)

        feed_publishers = get_not_null(response, "feed_publishers")
        for feed_publisher in feed_publishers:
            is_valid_feed_publisher(feed_publisher)

        if query_dict.get('debug', False):
            assert 'debug' in response
        else:
            assert 'debug' not in response

    @staticmethod
    def check_next_datetime_link(dt, response):
        if not response.get('journeys'):
            return
        """default next behaviour is 1 min after the best or the soonest"""
        j_to_compare = next((j for j in response.get('journeys', []) if j['type'] == 'best'), None) or\
             next((j for j in response.get('journeys', [])), None)

        j_departure = get_valid_datetime(j_to_compare['departure_date_time'])
        eq_(j_departure + timedelta(minutes=1), dt)

    @staticmethod
    def check_previous_datetime_link(dt, response):
        if not response.get('journeys'):
            return
        """default previous behaviour is 1 min before the best or the latest """
        j_to_compare = next((j for j in response.get('journeys', []) if j['type'] == 'best'), None) or\
             next((j for j in response.get('journeys', [])), None)

        j_departure = get_valid_datetime(j_to_compare['arrival_date_time'])
        eq_(j_departure - timedelta(minutes=1), dt)


def dataset(datasets):
    """
    decorator giving class attribute 'data_sets'

    each test should have this decorator to make clear the data set used for the tests

    each dataset can be either:
    just a string with the kraken name,
    or a pair with the kraken name and a list with additional arguments for the kraken
    """
    def deco(cls):
        cls.data_sets = datasets
        return cls
    return deco
