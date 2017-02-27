# coding=utf-8

# Copyright (c) 2001-2016, Canal TP and/or its affiliates. All rights reserved.
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
import logging
from jormungandr import utils
from jormungandr.exceptions import ConfigException
import abc

# Using abc.ABCMeta in a way it is compatible both with Python 2.7 and Python 3.x
# http://stackoverflow.com/a/38668373/1614576
ABC = abc.ABCMeta(str("ABC"), (object,), {})


class AbstractStreetNetworkService(ABC):
    @abc.abstractmethod
    def get_street_network_routing_matrix(self, origins, destinations, street_network_mode, max_duration, request, **kwargs):
        pass

    @abc.abstractmethod
    def direct_path(self, mode, pt_object_origin, pt_object_destination, datetime, clockwise, request):
        pass


class StreetNetwork(object):

    @staticmethod
    def get_street_network_services(instance, street_network_configurations):
        log = logging.getLogger(__name__)
        street_network_services = {}
        for config in street_network_configurations:
            # Set default arguments
            if 'args' not in config:
                config['args'] = {}
            if 'service_url' not in config['args']:
                config['args'].update({'service_url': None})
            if 'instance' not in config['args']:
                config['args'].update({'instance': instance})

            modes = config.get('modes')
            if not modes:
                raise KeyError('impossible to build a StreetNetwork, missing mandatory field in configuration: modes')

            try:
                service = utils.create_object(config)
            except KeyError as e:
                raise KeyError('impossible to build a StreetNetwork, missing mandatory field in configuration: {}'
                               .format(e.message))
            except ConfigException as e:
                raise ConfigException("impossible to build StreetNetwork, wrongly formated class: {}"
                                      .format(e))

            for mode in modes:
                street_network_services[mode] = service
                log.info('** StreetNetwork {} used for direct_path with mode: {} **'
                         .format(type(service).__name__, mode))
        return street_network_services
