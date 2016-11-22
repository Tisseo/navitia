# Copyright (c) 2001-2016, Canal TP and/or its affiliates. All rights reserved.
#
# This file is part of Navitia,
# the software to build cool stuff with public transport.
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
import pytest
from jormungandr.street_network.valhalla import Valhalla
from jormungandr.exceptions import UnableToParse, InvalidArguments, TechnicalError, ApiNotFound
from navitiacommon import type_pb2, response_pb2
import pybreaker
from mock import MagicMock
import requests as requests
from jormungandr.utils import str_to_time_stamp
import requests_mock
import json

MOCKED_REQUEST = {'walking_speed': 1, 'bike_speed': 2}

def get_pt_object(type, lon, lat):
    pt_object = type_pb2.PtObject()
    pt_object.embedded_type = type
    if type == type_pb2.ADDRESS:
        pt_object.address.coord.lat = lat
        pt_object.address.coord.lon = lon
    return pt_object


def decode_func_test():
    valhalla = Valhalla(instance=None,
                        url='http://bob.com')
    assert valhalla._decode('qyss{Aco|sCF?kBkHeJw[') == [[2.439938, 48.572841],
                                                         [2.439938, 48.572837],
                                                         [2.440088, 48.572891],
                                                         [2.440548, 48.57307]]


def response_valid():
    return {
        "trip": {
            "summary": {
                "time": 6,
                "length": 0.052
            },
            "units": "kilometers",
            "legs": [
                {
                    "shape": "qyss{Aco|sCF?kBkHeJw[",
                    "summary": {
                        "time": 6,
                        "length": 0.052
                    },
                    "maneuvers": [
                        {
                            "end_shape_index": 3,
                            "time": 6,
                            "length": 0.052,
                            "begin_shape_index": 0
                        },
                        {
                            "begin_shape_index": 3,
                            "time": 0,
                            "end_shape_index": 3,
                            "length": 0
                        }
                    ]
                }
            ],
            "status_message": "Found route between points",
            "status": 0
        }
    }


def get_costing_options_func_with_empty_costing_options_test():
    instance = MagicMock()
    valhalla = Valhalla(instance=instance,
                        url='http://bob.com')
    valhalla.costing_options = None
    assert valhalla._get_costing_options('bib', MOCKED_REQUEST) == None


def get_costing_options_func_with_unkown_costing_options_test():
    instance = MagicMock()
    valhalla = Valhalla(instance=instance,
                        url='http://bob.com',
                        costing_options={'bib': 'bom'})
    assert valhalla._get_costing_options('bib', MOCKED_REQUEST) == {'bib': 'bom'}


def get_costing_options_func_test():
    instance = MagicMock()
    instance.walking_speed = 1
    instance.bike_speed = 2
    valhalla = Valhalla(instance=instance,
                        url='http://bob.com',
                        costing_options={'bib': 'bom'})
    pedestrian = valhalla._get_costing_options('pedestrian', MOCKED_REQUEST)
    assert len(pedestrian) == 2
    assert 'pedestrian' in pedestrian
    assert 'walking_speed' in pedestrian['pedestrian']
    assert pedestrian['pedestrian']['walking_speed'] == 3.6 * 1
    assert 'bib' in pedestrian

    bicycle = valhalla._get_costing_options('bicycle', MOCKED_REQUEST)
    assert len(bicycle) == 2
    assert 'bicycle' in bicycle
    assert 'cycling_speed' in bicycle['bicycle']
    assert bicycle['bicycle']['cycling_speed'] == 3.6 * 2
    assert 'bib' in bicycle


def format_coord_func_invalid_pt_object_test():
    instance = MagicMock()
    valhalla = Valhalla(instance=instance,
                        url='http://bob.com',
                        costing_options={'bib': 'bom'})
    with pytest.raises(InvalidArguments) as excinfo:
        valhalla._format_coord(MagicMock())
    assert '400: Bad Request' in str(excinfo.value)


def format_coord_func_invalid_api_test():
    instance = MagicMock()
    valhalla = Valhalla(instance=instance,
                        url='http://bob.com',
                        costing_options={'bib': 'bom'})
    with pytest.raises(ApiNotFound) as excinfo:
        valhalla._format_coord(get_pt_object(type_pb2.ADDRESS, 1.12, 13.15), 'aaa')
    assert '404: Not Found' in str(excinfo.value)
    assert 'ApiNotFound' in str(excinfo.typename)


def format_coord_func_valid_coord_one_to_many_test():
    instance = MagicMock()
    pt_object = get_pt_object(type_pb2.ADDRESS, 1.12, 13.15)
    valhalla = Valhalla(instance=instance,
                        url='http://bob.com',
                        costing_options={'bib': 'bom'})

    coord = valhalla._format_coord(pt_object, 'one_to_many')
    coord_res = {'lat': pt_object.address.coord.lat, 'lon': pt_object.address.coord.lon}
    assert len(coord) == 2
    for key, value in coord_res.items():
        assert coord[key] == value


def format_coord_func_valid_coord_test():
    instance = MagicMock()
    pt_object = get_pt_object(type_pb2.ADDRESS, 1.12, 13.15)
    valhalla = Valhalla(instance=instance,
                        url='http://bob.com',
                        costing_options={'bib': 'bom'})

    coord = valhalla._format_coord(pt_object)
    coord_res = {'lat': pt_object.address.coord.lat, 'type': 'break', 'lon': pt_object.address.coord.lon}
    assert len(coord) == 3
    for key, value in coord_res.items():
        assert coord[key] == value


def format_url_func_with_walking_mode_test():
    instance = MagicMock()
    instance.walking_speed = 1
    instance.bike_speed = 2
    origin = get_pt_object(type_pb2.ADDRESS, 1.0, 1.0)
    destination = get_pt_object(type_pb2.ADDRESS, 2.0, 2.0)
    valhalla = Valhalla(instance=instance,
                        url='http://bob.com',
                        costing_options={'bib': 'bom'})
    data = valhalla._make_data("walking", origin, [destination], MOCKED_REQUEST)
    assert json.loads(data) == json.loads('''{
                        "costing_options": {
                          "pedestrian": {
                              "walking_speed": 3.6
                            },
                            "bib": "bom"
                          },
                          "locations": [
                            {
                              "lat": 1,
                              "type": "break",
                              "lon": 1
                            },
                            {
                              "lat": 2,
                              "type": "break",
                              "lon": 2
                            }
                          ],
                          "costing": "pedestrian",
                          "directions_options": {
                            "units": "kilometers"
                          }
                        }''')

def format_url_func_with_bike_mode_test():
    instance = MagicMock()
    instance.walking_speed = 1
    instance.bike_speed = 2

    origin = get_pt_object(type_pb2.ADDRESS, 1.0, 1.0)
    destination = get_pt_object(type_pb2.ADDRESS, 2.0, 2.0)

    valhalla = Valhalla(instance=instance,
                        url='http://bob.com',
                        costing_options={'bib': 'bom'})
    valhalla.costing_options = None
    data = valhalla._make_data("bike", origin, [destination], MOCKED_REQUEST)
    assert json.loads(data) == json.loads('''
                                            {
                                              "costing_options": {
                                                "bicycle": {
                                                  "cycling_speed": 7.2
                                                }
                                              },
                                              "locations": [
                                                {
                                                  "lat": 1,
                                                  "type": "break",
                                                  "lon": 1
                                                },
                                                {
                                                  "lat": 2,
                                                  "type": "break",
                                                  "lon": 2
                                                }
                                              ],
                                              "costing": "bicycle",
                                              "directions_options": {
                                                "units": "kilometers"
                                              }
                                            }''')



def format_url_func_with_car_mode_test():
    instance = MagicMock()
    instance.walking_speed = 1
    instance.bike_speed = 2

    origin = get_pt_object(type_pb2.ADDRESS, 1.0, 1.0)
    destination = get_pt_object(type_pb2.ADDRESS, 2.0, 2.0)

    valhalla = Valhalla(instance=instance,
                        url='http://bob.com',
                        costing_options={'bib': 'bom'})
    valhalla.costing_options = None
    data = valhalla._make_data("car", origin, [destination], MOCKED_REQUEST)
    assert json.loads(data) == json.loads(''' {
                                      "locations": [
                                        {
                                          "lat": 1,
                                          "type": "break",
                                          "lon": 1
                                        },
                                        {
                                          "lat": 2,
                                          "type": "break",
                                          "lon": 2
                                        }
                                      ],
                                      "costing": "auto",
                                      "directions_options": {
                                        "units": "kilometers"
                                      }
                                    }''')


def format_url_func_invalid_mode_test():
    instance = MagicMock()
    valhalla = Valhalla(instance=instance,
                        url='http://bob.com',
                        costing_options={'bib': 'bom'})
    with pytest.raises(InvalidArguments) as excinfo:
        origin = get_pt_object(type_pb2.ADDRESS, 1.0, 1.0)
        destination = get_pt_object(type_pb2.ADDRESS, 2.0, 2.0)
        valhalla._make_data("bob", origin, [destination], MOCKED_REQUEST)
    assert '400: Bad Request' == str(excinfo.value)
    assert 'InvalidArguments' == str(excinfo.typename)


def call_valhalla_func_with_circuit_breaker_error_test():
    instance = MagicMock()
    valhalla = Valhalla(instance=instance,
                        url='http://bob.com',
                        costing_options={'bib': 'bom'})
    valhalla.breaker = MagicMock()
    valhalla.breaker.call = MagicMock(side_effect=pybreaker.CircuitBreakerError())
    assert valhalla._call_valhalla(valhalla.service_url) == None


def call_valhalla_func_with_unknown_exception_test():
    instance = MagicMock()
    valhalla = Valhalla(instance=instance,
                        url='http://bob.com',
                        costing_options={'bib': 'bom'})
    valhalla.breaker = MagicMock()
    valhalla.breaker.call = MagicMock(side_effect=ValueError())
    assert valhalla._call_valhalla(valhalla.service_url) == None


def get_response_func_with_unknown_exception_test():
    instance = MagicMock()
    valhalla = Valhalla(instance=instance,
                        url='http://bob.com',
                        costing_options={'bib': 'bom'})
    resp_json = response_valid()
    origin = get_pt_object(type_pb2.ADDRESS, 2.439938, 48.572841)
    destination = get_pt_object(type_pb2.ADDRESS, 2.440548, 48.57307)
    response = valhalla._get_response(resp_json, 'walking',
                                      origin,
                                      destination,
                                      str_to_time_stamp('20161010T152000'))
    assert response.status_code == 200
    assert response.response_type == response_pb2.ITINERARY_FOUND
    assert len(response.journeys) == 1
    assert response.journeys[0].duration == 6
    assert len(response.journeys[0].sections) == 1
    assert response.journeys[0].sections[0].type == response_pb2.STREET_NETWORK
    assert response.journeys[0].sections[0].type == response_pb2.STREET_NETWORK
    assert response.journeys[0].sections[0].length == 52
    assert response.journeys[0].sections[0].destination == destination


def direct_path_func_without_response_valhalla_test():
    instance = MagicMock()
    valhalla = Valhalla(instance=instance,
                        url='http://bob.com',
                        costing_options={'bib': 'bom'})
    valhalla.breaker = MagicMock()
    valhalla._call_valhalla = MagicMock(return_value=None)
    valhalla._make_data = MagicMock(return_value=None)
    with pytest.raises(TechnicalError) as excinfo:
        valhalla.direct_path(None, None, None, None, None, None)
    assert '500: Internal Server Error' == str(excinfo.value)
    assert 'TechnicalError' == str(excinfo.typename)


def direct_path_func_with_status_code_400_response_valhalla_test():
    instance = MagicMock()
    valhalla = Valhalla(instance=instance,
                        url='http://bob.com',
                        costing_options={'bib': 'bom'})
    valhalla.breaker = MagicMock()
    response = requests.Response()
    response.status_code = 400
    response.url = valhalla.service_url
    valhalla._call_valhalla = MagicMock(return_value=response)
    valhalla._make_data = MagicMock(return_value=None)
    with pytest.raises(TechnicalError) as excinfo:
        valhalla.direct_path(None, None, None, None, None, None)
    assert str(excinfo.value) == '500: Internal Server Error'
    assert str(excinfo.value.data['message']) == 'Valhalla service unavailable, impossible to query : http://bob.com'
    assert str(excinfo.typename) == 'TechnicalError'


def direct_path_func_with_valid_response_valhalla_test():
    instance = MagicMock()
    instance.walking_speed = 1.12
    valhalla = Valhalla(instance=instance,
                        url='http://bob.com',
                        costing_options={'bib': 'bom'})
    resp_json = response_valid()

    origin = get_pt_object(type_pb2.ADDRESS, 2.439938, 48.572841)
    destination = get_pt_object(type_pb2.ADDRESS, 2.440548, 48.57307)
    with requests_mock.Mocker() as req:
        req.post('http://bob.com/route', json=resp_json)
        valhalla_response = valhalla.direct_path('walking',
                                          origin,
                                          destination,
                                          str_to_time_stamp('20161010T152000'),
                                          True,
                                          MOCKED_REQUEST)
        assert valhalla_response.status_code == 200
        assert valhalla_response.response_type == response_pb2.ITINERARY_FOUND
        assert len(valhalla_response.journeys) == 1
        assert valhalla_response.journeys[0].duration == 6
        assert len(valhalla_response.journeys[0].sections) == 1
        assert valhalla_response.journeys[0].sections[0].type == response_pb2.STREET_NETWORK
        assert valhalla_response.journeys[0].sections[0].type == response_pb2.STREET_NETWORK
        assert valhalla_response.journeys[0].sections[0].length == 52
        assert valhalla_response.journeys[0].sections[0].destination == destination


def get_valhalla_mode_invalid_mode_test():
    instance = MagicMock()
    valhalla = Valhalla(instance=instance,
                        url='http://bob.com',
                        costing_options={'bib': 'bom'})
    with pytest.raises(InvalidArguments) as excinfo:
        valhalla._get_valhalla_mode('bss')
    assert '400: Bad Request' == str(excinfo.value)
    assert 'InvalidArguments' == str(excinfo.typename)


def get_valhalla_mode_valid_mode_test():
    instance = MagicMock()
    valhalla = Valhalla(instance=instance,
                        url='http://bob.com',
                        costing_options={'bib': 'bom'})
    map_mode = {
        "walking": "pedestrian",
        "car": "auto",
        "bike": "bicycle"
    }
    for kraken_mode, valhalla_mode in map_mode.items():
        assert valhalla._get_valhalla_mode(kraken_mode) == valhalla_mode
