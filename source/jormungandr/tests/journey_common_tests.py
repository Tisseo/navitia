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
from .tests_mechanism import AbstractTestFixture, dataset
from jormungandr import i_manager
import mock
from .check_utils import *


def check_journeys(resp):
    assert not resp.get('journeys') or sum((1 for j in resp['journeys'] if j['type'] == "best")) == 1


@dataset({"main_routing_test": {}})
class JourneyCommon(object):

    """
    Test the structure of the journeys response
    """

    def test_journeys(self):
        #NOTE: we query /v1/coverage/main_routing_test/journeys and not directly /v1/journeys
        #not to use the jormungandr database
        response = self.query_region(journey_basic_query, display=True)
        check_journeys(response)
        self.is_valid_journey_response(response, journey_basic_query)

        feed_publishers = get_not_null(response, "feed_publishers")
        assert (len(feed_publishers) == 1)
        feed_publisher = feed_publishers[0]
        assert (feed_publisher["id"] == "builder")
        assert (feed_publisher["name"] == 'routing api data')
        assert (feed_publisher["license"] == "ODBL")
        assert (feed_publisher["url"] == "www.canaltp.fr")

    def test_error_on_journeys(self):
        """ if we got an error with kraken, an error should be returned"""

        query_out_of_production_bound = "journeys?from={from_coord}&to={to_coord}&datetime={datetime}"\
            .format(from_coord="0.0000898312;0.0000898312",  # coordinate of S in the dataset
            to_coord="0.00188646;0.00071865",  # coordinate of R in the dataset
            datetime="20110614T080000")  # 2011 should not be in the production period

        response, status = self.query_region(query_out_of_production_bound, check=False)

        assert status != 200, "the response should not be valid"
        check_journeys(response)
        assert response['error']['id'] == "date_out_of_bounds"
        assert response['error']['message'] == "date is not in data production period"

        #and no journey is to be provided
        assert 'journeys' not in response or len(response['journeys']) == 0

    def test_missing_params(self):
        """we should at least provide a from or a to on the /journeys api"""
        query = "journeys?datetime=20120614T080000"

        response, status = self.query_no_assert("v1/coverage/main_routing_test/" + query)

        assert status == 400
        get_not_null(response, 'message')

    def test_best_filtering(self):
        """Filter to get the best journey, we should have only one journey, the best one"""
        query = "{query}&type=best".format(query=journey_basic_query)
        response = self.query_region(query)
        check_journeys(response)
        self.is_valid_journey_response(response, query)
        assert len(response['journeys']) == 1

        assert response['journeys'][0]["type"] == "best"
        assert response['journeys'][0]['durations']['total'] == 99
        assert response['journeys'][0]['durations']['walking'] == 97

    def test_other_filtering(self):
        """the basic query return a non pt walk journey and a best journey. we test the filtering of the non pt"""

        response = self.query_region("{query}&type=non_pt_walk".
                                     format(query=journey_basic_query))

        assert len(response['journeys']) == 1
        assert response['journeys'][0]["type"] == "non_pt_walk"

    def test_speed_factor_direct_path(self):
        """We test the coherence of the non pt walk solution with a speed factor"""

        response = self.query_region("{query}&type=non_pt_walk&walking_speed=1.5".
                                     format(query=journey_basic_query))

        journeys = response['journeys']
        assert journeys
        non_pt_walk_j = next((j for j in journeys if j['type'] == 'non_pt_walk'), None)
        assert non_pt_walk_j
        assert non_pt_walk_j['duration'] == non_pt_walk_j['sections'][0]['duration']
        assert non_pt_walk_j['duration'] == 205
        assert non_pt_walk_j['durations']['total'] == 205
        assert non_pt_walk_j['durations']['walking'] == 205

        assert non_pt_walk_j['departure_date_time'] == non_pt_walk_j['sections'][0]['departure_date_time']
        assert non_pt_walk_j['departure_date_time'] == '20120614T080000'
        assert non_pt_walk_j['arrival_date_time'] == non_pt_walk_j['sections'][0]['arrival_date_time']
        assert non_pt_walk_j['arrival_date_time'] == '20120614T080325'

    def test_not_existent_filtering(self):
        """if we filter with a real type but not present, we don't get any journey, but we got a nice error"""

        response = self.query_region("{query}&type=car".
                                     format(query=journey_basic_query))

        assert not 'journeys' in response or len(response['journeys']) == 0
        assert 'error' in response
        assert response['error']['id'] == 'no_solution'
        assert response['error']['message'] == 'No journey found, all were filtered'

    def test_dumb_filtering(self):
        """if we filter with non existent type, we get an error"""

        response, status = self.query_region("{query}&type=sponge_bob"
                                             .format(query=journey_basic_query), check=False)

        assert status == 400, "the response should not be valid"

        assert response['message'].startswith("The type argument must be in list")

    def test_journeys_no_bss_and_walking(self):
        query = journey_basic_query + "&first_section_mode=walking&first_section_mode=bss"
        response = self.query_region(query)

        check_journeys(response)
        self.is_valid_journey_response(response, query)
        #Note: we need to mock the kraken instances to check that only one call has been made and not 2
        #(only one for bss because walking should not have been added since it duplicate bss)

        # we explicitly check that we find both mode in the responses link
        # (is checked in is_valid_journey, but never hurts to check twice)
        links = get_links_dict(response)
        for l in ["prev", "next", "first", "last"]:
            assert l in links
            url = links[l]['href']
            url_dict = query_from_str(url)
            assert url_dict['first_section_mode'] == ['walking', 'bss']

    def test_datetime_represents_arrival(self):
        """
        Checks journeys when datetime == start date of production datetime.
        """
        query = "journeys?from={from_coord}&to={to_coord}&datetime={datetime}&"\
                "min_nb_journeys=3&_night_bus_filter_base_factor=86400&"\
                "datetime_represents=arrival"\
                .format(from_coord=s_coord, to_coord=r_coord, datetime="20120614T185500")
        response = self.query_region(query)
        check_journeys(response)
        self.is_valid_journey_response(response, query)
        assert len(response["journeys"]) >= 3

    def test_min_nb_journeys(self):
        """Checks if min_nb_journeys works.

        _night_bus_filter_base_factor is used because we need to find
        2 journeys, and we can only take the bus the day after.
        datetime is modified because, as the bus begins at 8, we need
        to check that we don't do the next on the direct path starting
        datetime.
        """
        query = "journeys?from={from_coord}&to={to_coord}&datetime={datetime}&"\
                "min_nb_journeys=3&_night_bus_filter_base_factor=86400"\
                .format(from_coord=s_coord, to_coord=r_coord, datetime="20120614T075500")
        response = self.query_region(query)
        check_journeys(response)
        self.is_valid_journey_response(response, query)
        assert len(response["journeys"]) >= 3

    """
    test on date format
    """
    def test_journeys_no_date(self):
        """
        giving no date, we should have a response
        BUT, since without date we take the current date, it will not be in the production period,
        so we have a 'not un production period error'
        """

        query = "journeys?from={from_coord}&to={to_coord}"\
            .format(from_coord=s_coord, to_coord=r_coord)

        response, status_code = self.query_no_assert("v1/coverage/main_routing_test/" + query)

        assert status_code != 200, "the response should not be valid"

        assert response['error']['id'] == "date_out_of_bounds"
        assert response['error']['message'] == "date is not in data production period"

    def test_journeys_date_no_second(self):
        """giving no second in the date we should not be a problem"""

        query = "journeys?from={from_coord}&to={to_coord}&datetime={d}"\
            .format(from_coord=s_coord, to_coord=r_coord, d="20120614T0800")

        response = self.query_region(query)
        check_journeys(response)
        self.is_valid_journey_response(response, journey_basic_query)

        #and the second should be 0 initialized
        journeys = get_not_null(response, "journeys")
        assert journeys[0]["requested_date_time"] == "20120614T080000"

    def test_journeys_date_no_minute_no_second(self):
        """giving no minutes and no second in the date we should not be a problem"""

        query = "journeys?from={from_coord}&to={to_coord}&datetime={d}"\
            .format(from_coord=s_coord, to_coord=r_coord, d="20120614T08")

        response = self.query_region(query)
        check_journeys(response)
        self.is_valid_journey_response(response, journey_basic_query)

        #and the second should be 0 initialized
        journeys = get_not_null(response, "journeys")
        assert journeys[0]["requested_date_time"] == "20120614T080000"

    def test_journeys_date_too_long(self):
        """giving an invalid date (too long) should be a problem"""

        query = "journeys?from={from_coord}&to={to_coord}&datetime={d}"\
            .format(from_coord=s_coord, to_coord=r_coord, d="20120614T0812345")

        response, status_code = self.query_no_assert("v1/coverage/main_routing_test/" + query)

        assert not 'journeys' in response
        assert 'message' in response
        eq_(response['message'].lower(), "unable to parse datetime, unknown string format")

    def test_journeys_date_invalid(self):
        """giving the date with mmsshh (56 45 12) should be a problem"""

        query = "journeys?from={from_coord}&to={to_coord}&datetime={d}"\
            .format(from_coord=s_coord, to_coord=r_coord, d="20120614T564512")

        response, status_code = self.query_no_assert("v1/coverage/main_routing_test/" + query)

        assert not 'journeys' in response
        assert 'message' in response
        assert response['message'] == "Unable to parse datetime, hour must be in 0..23"

    def test_journeys_date_valid_invalid(self):
        """some format of date are bizarrely interpreted, and can result in date in 800"""

        query = "journeys?from={from_coord}&to={to_coord}&datetime={d}"\
            .format(from_coord=s_coord, to_coord=r_coord, d="T0800")

        response, status_code = self.query_no_assert("v1/coverage/main_routing_test/" + query)

        assert not 'journeys' in response
        assert 'message' in response
        assert response['message'] == "Unable to parse datetime, date is too early!"

    def test_journeys_bad_speed(self):
        """speed <= 0 is invalid"""

        for speed in ["0", "-1"]:
            for sn in ["walking", "bike", "bss", "car"]:
                query = "journeys?from={from_coord}&to={to_coord}&datetime={d}&{sn}_speed={speed}"\
                    .format(from_coord=s_coord, to_coord=r_coord, d="20120614T133700", sn=sn, speed=speed)

                response, status_code = self.query_no_assert("v1/coverage/main_routing_test/" + query)

                assert not 'journeys' in response
                assert 'message' in response
                assert response['message'] == \
                    "The {sn}_speed argument has to be > 0, you gave : {speed}"\
                        .format(sn=sn, speed=speed)

    def test_journeys_date_valid_not_zeropadded(self):
        """giving the date with non zero padded month should be a problem"""

        query = "journeys?from={from_coord}&to={to_coord}&datetime={d}"\
            .format(from_coord=s_coord, to_coord=r_coord, d="2012614T081025")

        response, status_code = self.query_no_assert("v1/coverage/main_routing_test/" + query)

        assert not 'journeys' in response
        assert 'message' in response
        assert response['message'] == "Unable to parse datetime, year is out of range"

    def test_journeys_do_not_loose_precision(self):
        """do we have a good precision given back in the id"""

        # this id was generated by giving an id to the api, and
        # copying it here the resulting id
        id = "8.98311981954709e-05;0.000898311281954"
        response = self.query_region("journeys?from={id}&to={id}&datetime={d}"
                                     .format(id=id, d="20120614T080000"))
        assert(len(response['journeys']) > 0)
        for j in response['journeys']:
            assert(j['sections'][0]['from']['id'] == id)
            assert(j['sections'][0]['from']['address']['id'] == id)
            assert(j['sections'][-1]['to']['id'] == id)
            assert(j['sections'][-1]['to']['address']['id'] == id)

    def test_journeys_wheelchair_profile(self):
        """
        Test a query with a wheelchair profile.
        We want to go from S to R after 8h as usual, but between S and R, the first VJ is not accessible,
        so we have to wait for the bus at 18h to leave
        """

        response = self.query_region(journey_basic_query + "&traveler_type=wheelchair")
        assert(len(response['journeys']) == 2)
        #Note: we do not test order, because that can change depending on the scenario
        eq_(sorted(get_used_vj(response)), sorted([[], ['vjB']]))
        eq_(sorted(get_arrivals(response)), sorted(['20120614T080612', '20120614T180250']))

        # same response if we just give the wheelchair=True
        response = self.query_region(journey_basic_query + "&traveler_type=wheelchair&wheelchair=True")
        assert(len(response['journeys']) == 2)
        eq_(sorted(get_used_vj(response)), sorted([[], ['vjB']]))
        eq_(sorted(get_arrivals(response)), sorted(['20120614T080612', '20120614T180250']))

        # but with the wheelchair profile, if we explicitly accept non accessible solutions (not very
        # consistent, but anyway), we should take the non accessible bus that arrive at 08h
        response = self.query_region(journey_basic_query + "&traveler_type=wheelchair&wheelchair=False")
        assert(len(response['journeys']) == 2)
        eq_(sorted(get_used_vj(response)), sorted([['vjA'], []]))
        eq_(sorted(get_arrivals(response)), sorted(['20120614T080250', '20120614T080612']))

    def test_journeys_float_night_bus_filter_max_factor(self):
        """night_bus_filter_max_factor can be a float (and can be null)"""

        query = "journeys?from={from_coord}&to={to_coord}&datetime={d}&" \
                         "_night_bus_filter_max_factor={_night_bus_filter_max_factor}"\
            .format(from_coord=s_coord, to_coord=r_coord, d="20120614T080000",
                    _night_bus_filter_max_factor=2.8)

        response = self.query_region(query)
        check_journeys(response)
        self.is_valid_journey_response(response, query)

        query = "journeys?from={from_coord}&to={to_coord}&datetime={d}&" \
                         "_night_bus_filter_max_factor={_night_bus_filter_max_factor}"\
            .format(from_coord=s_coord, to_coord=r_coord, d="20120614T080000",
                    _night_bus_filter_max_factor=0)

        response = self.query_region(query)
        self.is_valid_journey_response(response, query)

    def test_sp_to_sp(self):
        """
        Test journeys from stop point to stop point
        """
        query = "journeys?from=stop_point:uselessA&to=stop_point:stopB&datetime=20120615T080000"

        # with street network desactivated
        response = self.query_region(query + "&max_duration_to_pt=0")
        assert('journeys' not in response)

        # with street network activated
        response = self.query_region(query + "&max_duration_to_pt=1")
        eq_(len(response['journeys']), 1)
        eq_(response['journeys'][0]['sections'][0]['from']['id'], 'stop_point:uselessA')
        eq_(response['journeys'][0]['sections'][0]['to']['id'], 'stop_point:stopA')
        eq_(response['journeys'][0]['sections'][0]['type'], 'street_network')
        eq_(response['journeys'][0]['sections'][0]['mode'], 'walking')
        eq_(response['journeys'][0]['sections'][0]['duration'], 0)

    @mock.patch.object(i_manager, 'dispatch')
    def test_max_duration_to_pt(self, mock):
        q = "v1/coverage/main_routing_test/journeys?max_duration_to_pt=0&from=toto&to=tata"
        self.query(q)
        max_walking = i_manager.dispatch.call_args[0][0]["max_walking_duration_to_pt"]
        max_bike = i_manager.dispatch.call_args[0][0]['max_bike_duration_to_pt']
        max_bss = i_manager.dispatch.call_args[0][0]['max_bss_duration_to_pt']
        max_car = i_manager.dispatch.call_args[0][0]['max_car_duration_to_pt']
        assert max_walking == 0
        assert max_bike == 0
        assert max_bss == 0
        assert max_car == 0

    def test_traveler_type(self):
        q_fast_walker = journey_basic_query + "&traveler_type=fast_walker"
        response_fast_walker = self.query_region(q_fast_walker)
        basic_response = self.query_region(journey_basic_query)

        def bike_in_journey(fast_walker):
            return any(sect_fast_walker["mode"] == 'bike' for sect_fast_walker in fast_walker['sections']
                       if 'mode' in sect_fast_walker)

        def no_bike_in_journey(journey):
            return all(section['mode'] != 'bike' for section in journey['sections'] if 'mode' in section)

        assert any(bike_in_journey(journey_fast_walker) for journey_fast_walker in response_fast_walker['journeys'])
        assert all(no_bike_in_journey(journey) for journey in basic_response['journeys'])

    def test_shape_in_geojson(self):
        """
        Test if, in the first journey, the second section:
         - is public_transport
         - len of stop_date_times is 2
         - len of geojson/coordinates is 3 (and thus,
           stop_date_times is not used to create the geojson)
        """
        response = self.query_region(journey_basic_query, display=False)
        #print response['journeys'][0]['sections'][1]
        eq_(len(response['journeys']), 2)
        eq_(len(response['journeys'][0]['sections']), 3)
        eq_(response['journeys'][0]['co2_emission']['value'], 0.58)
        eq_(response['journeys'][0]['co2_emission']['unit'], 'gEC')
        eq_(response['journeys'][0]['sections'][1]['type'], 'public_transport')
        eq_(len(response['journeys'][0]['sections'][1]['stop_date_times']), 2)
        eq_(len(response['journeys'][0]['sections'][1]['geojson']['coordinates']), 3)
        eq_(response['journeys'][0]['sections'][1]['co2_emission']['value'], 0.58)
        eq_(response['journeys'][0]['sections'][1]['co2_emission']['unit'], 'gEC')
        eq_(response['journeys'][1]['duration'], 275)
        eq_(response['journeys'][1]['durations']['total'], 275)
        eq_(response['journeys'][1]['durations']['walking'], 275)


    def test_max_duration_to_pt_equals_to_0(self):
        query = journey_basic_query + \
            "&first_section_mode[]=bss" + \
            "&first_section_mode[]=walking" + \
            "&first_section_mode[]=bike" + \
            "&first_section_mode[]=car" + \
            "&debug=true"
        response = self.query_region(query)
        check_journeys(response)
        eq_(len(response['journeys']), 4)

        query += "&max_duration_to_pt=0"
        response, status = self.query_no_assert(query)
        # pas de solution
        assert status == 404
        assert('journeys' not in response)

    def test_max_duration_to_pt_equals_to_0_from_stop_point(self):
        query = "journeys?from=stop_point%3AstopA&to=stop_point%3AstopC&datetime=20120614T080000"
        response = self.query_region(query)
        check_journeys(response)
        eq_(len(response['journeys']), 2)

        query += "&max_duration_to_pt=0"
        #There is no direct_path but a journey using Metro
        response = self.query_region(query)
        check_journeys(response)
        jrnys = response['journeys']
        assert len(jrnys) == 1
        section = jrnys[0]['sections'][0]
        assert section['type'] == 'public_transport'
        assert section['from']['id'] == 'stop_point:stopA'
        assert section['to']['id'] == 'stop_point:stopC'

    def test_max_duration_equals_to_0(self):
        query = journey_basic_query + \
            "&first_section_mode[]=bss" + \
            "&first_section_mode[]=walking" + \
            "&first_section_mode[]=bike" + \
            "&first_section_mode[]=car" + \
            "&debug=true"
        response = self.query_region(query)
        check_journeys(response)
        eq_(len(response['journeys']), 4)

        query += "&max_duration=0"
        response = self.query_region(query)
        # the pt journey is eliminated
        eq_(len(response['journeys']), 3)

        check_journeys(response)

        # first is bike
        assert('bike' in response['journeys'][0]['tags'])
        ok_(response['journeys'][0]['debug']['internal_id'])
        eq_(len(response['journeys'][0]['sections']), 1)

        # second is car
        assert('car' in response['journeys'][1]['tags'])
        ok_(response['journeys'][1]['debug']['internal_id'])
        eq_(len(response['journeys'][1]['sections']), 3)

        # last is walking
        assert('walking' in response['journeys'][-1]['tags'])
        ok_(response['journeys'][-1]['debug']['internal_id'])
        eq_(len(response['journeys'][-1]['sections']), 1)

    def test_journey_stop_area_to_stop_point(self):
        """
        When the departure is stop_area:A and the destination is stop_point:B belonging to stop_area:B
        """
        query = "journeys?from={from_sa}&to={to_sa}&datetime={datetime}"\
            .format(from_sa='stopA', to_sa='stop_point:stopB', datetime="20120614T080000")
        response = self.query_region(query)
        check_journeys(response)
        jrnys = response['journeys']

        j = next((j for j in jrnys if j['type'] == 'non_pt_walk'), None)
        assert j
        assert j['sections'][0]['from']['id'] == 'stopA'
        assert j['sections'][0]['to']['id'] == 'stop_point:stopB'
        assert 'walking' in j['tags']

    def test_crow_fly_sections(self):
        """
        When the departure is a stop_area...
        """
        query = "journeys?from={from_sa}&to={to_sa}&datetime={datetime}"\
            .format(from_sa='stopA', to_sa='stopB', datetime="20120614T080000")
        response = self.query_region(query)
        check_journeys(response)
        jrnys = response['journeys']
        assert len(jrnys) == 2
        section_0 = jrnys[0]['sections'][0]
        assert section_0['type'] == 'crow_fly'
        assert section_0['from']['id'] == 'stopA'
        assert section_0['to']['id'] == 'stop_point:stopA'

        section_2 = jrnys[0]['sections'][2]
        assert section_2['type'] == 'crow_fly'
        assert section_2['from']['id'] == 'stop_point:stopB'
        assert section_2['to']['id'] == 'stopB'


@dataset({"main_routing_test": {}})
class DirectPath(object):
    def test_journey_direct_path(self):
        query = journey_basic_query + \
                "&first_section_mode[]=bss" + \
                "&first_section_mode[]=walking" + \
                "&first_section_mode[]=bike" + \
                "&first_section_mode[]=car" + \
                "&debug=true"
        response = self.query_region(query)
        check_journeys(response)
        eq_(len(response['journeys']), 4)

        # first is bike
        assert('bike' in response['journeys'][0]['tags'])
        eq_(len(response['journeys'][0]['sections']), 1)

        # second is car
        assert('car' in response['journeys'][1]['tags'])
        eq_(len(response['journeys'][1]['sections']), 3)

        # last is walking
        assert('walking' in response['journeys'][-1]['tags'])
        eq_(len(response['journeys'][-1]['sections']), 1)


@dataset({})
class JourneysNoRegion():
    """
    If no region loaded we must have a polite error while asking for a journey
    """

    def test_with_region(self):
        response, status = self.query_no_assert("v1/coverage/non_existent_region/" + journey_basic_query)

        assert status != 200, "the response should not be valid"

        assert response['error']['id'] == "unknown_object"
        assert response['error']['message'] == "The region non_existent_region doesn't exists"

    def test_no_region(self):
        response, status = self.query_no_assert("v1/" + journey_basic_query)

        assert status != 200, "the response should not be valid"

        assert response['error']['id'] == "unknown_object"

        error_regexp = re.compile('^No region available for the coordinates.*')
        assert error_regexp.match(response['error']['message'])


@dataset({"basic_routing_test": {}})
class OnBasicRouting():
    """
    Test if the filter on long waiting duration is working
    """

    def test_novalidjourney_on_first_call(self):
        """
        On this call the first call to kraken returns a journey
        with a too long waiting duration.
        The second call to kraken must return a valid journey
        """
        query = "journeys?from={from_sa}&to={to_sa}&datetime={datetime}"\
            .format(from_sa="A", to_sa="D", datetime="20120614T080000")

        response = self.query_region(query, display=False)
        eq_(len(response['journeys']), 1)
        logging.getLogger(__name__).info("arrival date: {}".format(response['journeys'][0]['arrival_date_time']))
        eq_(response['journeys'][0]['arrival_date_time'],  "20120614T160000")
        eq_(response['journeys'][0]['type'], "best")

        assert len(response["disruptions"]) == 0
        feed_publishers = response["feed_publishers"]
        assert len(feed_publishers) == 1
        for feed_publisher in feed_publishers:
            is_valid_feed_publisher(feed_publisher)

        feed_publisher = feed_publishers[0]
        assert (feed_publisher["id"] == "base_contributor")
        assert (feed_publisher["name"] == "base contributor")
        assert (feed_publisher["license"] == "L-contributor")
        assert (feed_publisher["url"] == "www.canaltp.fr")

    def test_novalidjourney_on_first_call_debug(self):
        """
        On this call the first call to kraken returns a journey
        with a too long waiting duration.
        The second call to kraken must return a valid journey
        We had a debug argument, hence 2 journeys are returned, only one is typed
        """
        query = "journeys?from={from_sa}&to={to_sa}&datetime={datetime}&debug=true"\
            .format(from_sa="A", to_sa="D", datetime="20120614T080000")

        response = self.query_region(query, display=False)
        eq_(len(response['journeys']), 2)
        eq_(response['journeys'][0]['arrival_date_time'], "20120614T150000")
        assert('to_delete' in response['journeys'][0]['tags'])
        eq_(response['journeys'][1]['arrival_date_time'], "20120614T160000")
        eq_(response['journeys'][1]['type'], "fastest")

    def test_datetime_error(self):
        """
        datetime invalid, we got an error
        """
        datetimes = ["20120614T080000Z", "2012-06-14T08:00:00.222Z"]
        for datetime in datetimes:
            query = "journeys?from={from_sa}&to={to_sa}&datetime={datetime}&debug=true"\
                .format(from_sa="A", to_sa="D", datetime=datetime)

            response, error_code = self.query_region(query, check=False)

            assert error_code == 400

            error = get_not_null(response, "error")

            assert error["message"] == "Unable to parse datetime, Not naive datetime (tzinfo is already set)"
            assert error["id"] == "unable_to_parse"

    def test_journeys_without_show_codes(self):
        '''
        Test journeys api without show_codes.
        The API's response contains the codes
        '''
        query = "journeys?from={from_sa}&to={to_sa}&datetime={datetime}"\
            .format(from_sa="A", to_sa="D", datetime="20120614T080000")

        response = self.query_region(query, display=False)
        eq_(len(response['journeys']), 1)
        eq_(len(response['journeys'][0]['sections']), 4)
        first_section = response['journeys'][0]['sections'][0]
        eq_(first_section['from']['stop_point']['codes'][0]['type'], 'external_code')
        eq_(first_section['from']['stop_point']['codes'][0]['value'], 'stop_point:A')
        eq_(first_section['from']['stop_point']['codes'][1]['type'], 'source')
        eq_(first_section['from']['stop_point']['codes'][1]['value'], 'Ain')
        eq_(first_section['from']['stop_point']['codes'][2]['type'], 'source')
        eq_(first_section['from']['stop_point']['codes'][2]['value'], 'Aisne')

    def test_journeys_with_show_codes(self):
        '''
        Test journeys api with show_codes = false.
        The API's response contains the codes
        '''
        query = "journeys?from={from_sa}&to={to_sa}&datetime={datetime}&show_codes=false"\
            .format(from_sa="A", to_sa="D", datetime="20120614T080000")

        response = self.query_region(query, display=False)
        eq_(len(response['journeys']), 1)
        eq_(len(response['journeys'][0]['sections']), 4)
        first_section = response['journeys'][0]['sections'][0]
        eq_(first_section['from']['stop_point']['codes'][0]['type'], 'external_code')
        eq_(first_section['from']['stop_point']['codes'][0]['value'], 'stop_point:A')
        eq_(first_section['from']['stop_point']['codes'][1]['type'], 'source')
        eq_(first_section['from']['stop_point']['codes'][1]['value'], 'Ain')
        eq_(first_section['from']['stop_point']['codes'][2]['type'], 'source')
        eq_(first_section['from']['stop_point']['codes'][2]['value'], 'Aisne')

    def test_remove_one_journey_from_batch(self):
        """
        Kraken returns two journeys, the earliest arrival one returns a too
        long waiting duration, therefore it must be deleted.
        The second one must be returned
        """
        query = "journeys?from={from_sa}&to={to_sa}&datetime={datetime}"\
            .format(from_sa="A", to_sa="D", datetime="20120615T080000")

        response = self.query_region(query, display=False)
        eq_(len(response['journeys']), 1)
        eq_(response['journeys'][0]['arrival_date_time'], u'20120615T151000')
        eq_(response['journeys'][0]['type'], "best")

    def test_max_attemps(self):
        """
        Kraken always retrieves journeys with non_pt_duration > max_non_pt_duration
        No journeys should be typed, but get_journeys should stop quickly
        """
        query = "journeys?from={from_sa}&to={to_sa}&datetime={datetime}"\
            .format(from_sa="E", to_sa="H", datetime="20120615T080000")

        response = self.query_region(query, display=False)
        assert(not "journeys" in response or len(response['journeys']) ==  0)

    def test_max_attemps_debug(self):
        """
        Kraken always retrieves journeys with non_pt_duration > max_non_pt_duration
        No journeys should be typed, but get_journeys should stop quickly
        We had the debug argument, hence a non-typed journey is returned
        """
        query = "journeys?from={from_sa}&to={to_sa}&datetime={datetime}&debug=true"\
            .format(from_sa="E", to_sa="H", datetime="20120615T080000")

        response = self.query_region(query, display=False)
        eq_(len(response['journeys']), 1)

    def test_sp_to_sp(self):
        """
        Test journeys from stop point to stop point without street network
        """
        query = "journeys?from=stop_point:uselessA&to=stop_point:B&datetime=20120615T080000"

        # with street network desactivated
        response = self.query_region(query + "&max_duration_to_pt=0")
        assert('journeys' not in response)

        # with street network activated
        response = self.query_region(query + "&max_duration_to_pt=1")
        eq_(len(response['journeys']), 1)
        eq_(response['journeys'][0]['sections'][0]['from']['id'], 'stop_point:uselessA')
        eq_(response['journeys'][0]['sections'][0]['to']['id'], 'A')
        eq_(response['journeys'][0]['sections'][0]['type'], 'crow_fly')
        eq_(response['journeys'][0]['sections'][0]['mode'], 'walking')
        eq_(response['journeys'][0]['sections'][0]['duration'], 0)

    def test_isochrone(self):
        response = self.query_region("journeys?from=I1&datetime=20120615T070000&max_duration=36000")
        assert(len(response['journeys']) == 2)

    def test_odt_admin_to_admin(self):
        """
        Test journeys from admin to admin using odt
        """
        query = "journeys?from=admin:93700&to=admin:75000&datetime=20120615T145500"

        response = self.query_region(query)
        eq_(len(response['journeys']), 1)
        eq_(response['journeys'][0]['sections'][0]['from']['id'], 'admin:93700')
        eq_(response['journeys'][0]['sections'][0]['to']['id'], 'admin:75000')
        eq_(response['journeys'][0]['sections'][0]['type'], 'public_transport')
        eq_(response['journeys'][0]['sections'][0]['additional_informations'][0], 'odt_with_zone')


@dataset({"main_routing_test": {},
          "basic_routing_test": {'check_killed': False}})
class OneDeadRegion():
    """
    Test if we still responds when one kraken is dead
    """

    def test_one_dead_region(self):
        self.krakens_pool["basic_routing_test"].kill()

        response = self.query("v1/journeys?from=stop_point:stopA&"
            "to=stop_point:stopB&datetime=20120614T080000&debug=true&max_duration_to_pt=0")
        eq_(len(response['journeys']), 1)
        eq_(len(response['journeys'][0]['sections']), 1)
        eq_(response['journeys'][0]['sections'][0]['type'], 'public_transport')
        eq_(len(response['debug']['regions_called']), 1)
        eq_(response['debug']['regions_called'][0], "main_routing_test")


@dataset({"main_routing_without_pt_test": {'priority': 42}, "main_routing_test": {'priority': 10}})
class WithoutPt():
    """
    Test if we still responds when one kraken has no pt solution
    """
    def test_one_region_without_pt(self):
        response = self.query("v1/"+journey_basic_query+"&debug=true",
                              display=False)
        eq_(len(response['journeys']), 2)
        eq_(len(response['journeys'][0]['sections']), 3)
        eq_(response['journeys'][0]['sections'][1]['type'], 'public_transport')
        eq_(len(response['debug']['regions_called']), 2)
        eq_(response['debug']['regions_called'][0], "main_routing_without_pt_test")
        eq_(response['debug']['regions_called'][1], "main_routing_test")

    """
    Test if we still responds when one kraken has no pt solution using new_default
    """
    def test_one_region_without_pt_new_default(self):
        response = self.query("v1/"+journey_basic_query+"&debug=true",
                              display=False)
        eq_(len(response['journeys']), 2)
        eq_(len(response['journeys'][0]['sections']), 3)
        eq_(response['journeys'][0]['sections'][1]['type'], 'public_transport')
        eq_(len(response['debug']['regions_called']), 2)
        eq_(response['debug']['regions_called'][0], "main_routing_without_pt_test")
        eq_(response['debug']['regions_called'][1], "main_routing_test")


@dataset({"main_ptref_test": {}})
class JourneysWithPtref():
    """
    Test all scenario with ptref_test data
    """
    def test_strange_line_name(self):
        response = self.query_region("journeys?from=stop_area:stop2&to=stop_area:stop1&datetime=20140107T100000")
        check_journeys(response)
        eq_(len(response['journeys']), 1)
