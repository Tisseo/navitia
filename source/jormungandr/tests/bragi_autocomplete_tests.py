# coding=utf-8
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
import mock
from jormungandr.tests.utils_test import MockRequests, MockResponse
from tests.check_utils import is_valid_global_autocomplete
from .tests_mechanism import AbstractTestFixture, dataset

MOCKED_INSTANCE_CONF = {
    'instance_config': {
        'default_autocomplete': 'bragi'
    }
}


@dataset({'main_autocomplete_test': MOCKED_INSTANCE_CONF})
class TestBragiAutocomplete(AbstractTestFixture):

    def test_autocomplete_call(self):
        mock_requests = MockRequests({
        'https://host_of_bragi/autocomplete?q=bob&limit=10&pt_dataset=main_autocomplete_test':
            (
                {"features": [
                    {
                        "geometry": {
                            "coordinates": [
                                3.282103,
                                49.847586
                            ],
                            "type": "Point"
                        },
                        "properties": {
                            "geocoding": {
                                "city": "Bobtown",
                                "housenumber": "20",
                                "id": "49.847586;3.282103",
                                "label": "20 Rue Bob (Bobtown)",
                                "name": "Rue Bob",
                                "postcode": "02100",
                                "street": "Rue Bob",
                                "type": "house",
                                "citycode": "02000",
                                "administrative_regions": [
                                    {
                                        "id": "admin:fr:02000",
                                        "insee": "02000",
                                        "level": 8,
                                        "label": "Bobtown (02000)",
                                        "zip_codes": ["02000"],
                                        "weight": 1,
                                        "coord": {
                                            "lat": 48.8396154,
                                            "lon": 2.3957517
                                        }
                                    }
                                ],
                                }
                        },
                        "type": "Feature"
                    }
                ]
                }, 200)
        })
        with mock.patch('requests.get', mock_requests.get):
            response = self.query_region('places?q=bob&pt_dataset=main_autocomplete_test')

            is_valid_global_autocomplete(response, depth=1)
            r = response.get('places')
            assert len(r) == 1
            assert r[0]['name'] == '20 Rue Bob (Bobtown)'
            assert r[0]['embedded_type'] == 'address'
            assert r[0]['address']['name'] == 'Rue Bob'
            assert r[0]['address']['label'] == '20 Rue Bob (Bobtown)'

    def test_autocomplete_call_with_param_from(self):
        """
        test that the from param of the autocomplete is correctly given to bragi
        :return:
        """
        def http_get(url, *args, **kwargs):
            params = kwargs.pop('params')
            assert params
            assert params.get('lon') == '3.25'
            assert params.get('lat') == '49.84'
            return MockResponse({}, 200, '')
        with mock.patch('requests.get', http_get) as mock_method:
            self.query_region('places?q=bob&from=3.25;49.84')

    def test_autocomplete_call_override(self):
        """"
        test that the _autocomplete param switch the right autocomplete service
        """
        mock_requests = MockRequests({
        'https://host_of_bragi/autocomplete?q=bob&limit=10&pt_dataset=main_autocomplete_test':
            (
                {"features": [
                    {
                        "geometry": {
                            "coordinates": [
                                3.282103,
                                49.847586
                            ],
                            "type": "Point"
                        },
                        "properties": {
                            "geocoding": {
                                "city": "Bobtown",
                                "housenumber": "20",
                                "id": "49.847586;3.282103",
                                "label": "20 Rue Bob (Bobtown)",
                                "name": "Rue Bob",
                                "postcode": "02100",
                                "street": "Rue Bob",
                                "type": "house",
                                "citycode": "02000",
                                "administrative_regions": [
                                    {
                                        "id": "admin:fr:02000",
                                        "insee": "02000",
                                        "level": 8,
                                        "label": "Bobtown (02000)",
                                        "zip_codes": ["02000"],
                                        "weight": 1,
                                        "coord": {
                                            "lat": 48.8396154,
                                            "lon": 2.3957517
                                        }
                                    }
                                ],
                                }
                        },
                        "type": "Feature"
                    }
                ]
                }, 200)
        })
        with mock.patch('requests.get', mock_requests.get):
            response = self.query_region('places?q=bob')

            is_valid_global_autocomplete(response, depth=1)
            r = response.get('places')
            assert len(r) == 1
            assert r[0]['name'] == '20 Rue Bob (Bobtown)'
            assert r[0]['embedded_type'] == 'address'
            assert r[0]['address']['name'] == 'Rue Bob'
            assert r[0]['address']['label'] == '20 Rue Bob (Bobtown)'

            # with a query on kraken, the results should be different
            response = self.query_region("places?q=Gare&_autocomplete=kraken")
            r = response.get('places')
            assert len(r) == 1
            assert r[0]['name'] == 'Gare (Quimper)'
            assert r[0]['embedded_type'] == 'stop_area'
            assert r[0]['stop_area']['name'] == 'Gare'
            assert r[0]['stop_area']['label'] == 'Gare (Quimper)'
