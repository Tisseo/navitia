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
from jormungandr.parking_space_availability.bss.bss_provider import BssProvider
from jormungandr.parking_space_availability.bss.stands import Stands
from jormungandr import cache, app
import pybreaker
import requests as requests
import logging


class JcdecauxProvider(BssProvider):

    WS_URL_TEMPLATE = 'https://api.jcdecaux.com/vls/v1/stations/{}?contract={}&apiKey={}'
    OPERATOR = 'JCDecaux'

    def __init__(self, network, contract, api_key, timeout=10):
        self.network = network
        self.contract = contract
        self.api_key = api_key
        self.timeout = timeout
        self.breaker = pybreaker.CircuitBreaker(fail_max=app.config['CIRCUIT_BREAKER_MAX_JCDECAUX_FAIL'],
                                                reset_timeout=app.config['CIRCUIT_BREAKER_JCDECAUX_TIMEOUT_S'])

    def support_poi(self, poi):
        properties = poi.get('properties', {})
        return properties.get('operator') == self.OPERATOR and \
               properties.get('network') == self.network

    @cache.memoize(app.config['CACHE_CONFIGURATION'].get('TIMEOUT_JCDECAUX', 30))
    def _call_webservice(self, station_id):
        try:
            data = self.breaker.call(requests.get, self.WS_URL_TEMPLATE.format(station_id, self.contract, self.api_key), timeout=self.timeout)
            return data.json()
        except pybreaker.CircuitBreakerError as e:
            logging.getLogger(__name__).error('JCDecaux service dead (error: {})'.format(e))
        except requests.Timeout as t:
            logging.getLogger(__name__).error('JCDecaux service timeout (error: {})'.format(t))
        except:
            logging.getLogger(__name__).exception('JCDecaux error')
        return None

    def get_informations(self, poi):
        ref = poi.get('properties', {}).get('ref')
        data = self._call_webservice(ref)
        if data and 'available_bike_stands' in data and 'available_bikes' in data:
            return Stands(data['available_bike_stands'], data['available_bikes'])
