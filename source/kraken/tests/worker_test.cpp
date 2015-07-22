/* Copyright © 2001-2015, Canal TP and/or its affiliates. All rights reserved.

This file is part of Navitia,
    the software to build cool stuff with public transport.

Hope you'll enjoy and contribute to this project,
    powered by Canal TP (www.canaltp.fr).
Help us simplify mobility and open public transport:
    a non ending quest to the responsive locomotion way of traveling!

LICENCE: This program is free software; you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program. If not, see <http://www.gnu.org/licenses/>.

Stay tuned using
twitter @navitia
IRC #navitia on freenode
https://groups.google.com/d/forum/navitia
www.navitia.io
*/

#define BOOST_TEST_DYN_LINK
#define BOOST_TEST_MODULE test_worker
#include <boost/test/unit_test.hpp>
#include "routing/raptor_api.h"
#include "ed/build_helper.h"
#include "tests/utils_test.h"
#include "kraken/data_manager.h"
#include "kraken/configuration.h"
#include "kraken/worker.h"
#include "type/pt_data.h"


struct logger_initialized {
    logger_initialized()   { init_logger(); }
};
BOOST_GLOBAL_FIXTURE( logger_initialized )


static pbnavitia::Request create_request(bool wheelchair, std::string destination) {
    pbnavitia::Request req;
    req.set_requested_api(pbnavitia::PLANNER);
    pbnavitia::JourneysRequest* j = req.mutable_journeys();
    j->set_clockwise(true);
    j->set_wheelchair(wheelchair);
    j->set_disruption_active(true);
    j->set_max_duration(std::numeric_limits<int32_t>::max());
    j->set_max_transfers(42);
    j->add_datetimes(navitia::test::to_posix_timestamp("20150314T080000"));
    auto sn_params = j->mutable_streetnetwork_params();
    sn_params->set_origin_mode("walking");
    sn_params->set_destination_mode("walking");
    pbnavitia::LocationContext* from = j->add_origin();
    from->set_place("A");
    from->set_access_duration(0);
    pbnavitia::LocationContext* to = j->add_destination();
    to->set_place(destination);
    to->set_access_duration(0);

    return req;
}

/**
  * Accessibility tests
  *
  *
  *          ,                        \/
  * Note:    |__    means accessible, /\ means not accessible
  *         ( )o|
  *
  *
  *  ,                    ,
  *  |__                  |__                   \/
  * ( )o|                ( )o|                  /\
  *
  *  A ------------------- B ------------------- C
  *
  *  9h        \/         9h
  *            /\
  *
  *            ,
  *  8h        |_         10h
  *           ( )o|
  *
  *                       ,
  * 10h                   |_                    11h
  *                      ( )o|
  *
  * Leaving at 8h with a wheelchair, we should only be able to arrive at B at 10 and it's impossible to go to C
  *
  */
struct fixture {
    fixture(): b("20150314"),
                 w(data_manager, navitia::kraken::Configuration()){
        b.sa("A", 0, 0, true, true);
        b.sa("B", 0, 0, true, true);
        b.sa("C", 0, 0, true, false); // C is not accessible
        b.vj("l1", "11111111", "", false)
                ("stop_point:A", "8:00"_t)("stop_point:B", "9:00"_t);
        b.vj("l2")
                ("stop_point:A", "9:00"_t)("stop_point:B", "10:00"_t);
        b.vj("l3")
                ("stop_point:A", "10:00"_t)("stop_point:C", "11:00"_t);

        b.finish();
        b.generate_dummy_basis();
        b.data->pt_data->index();
        b.data->build_raptor();
        b.data->build_uri();

        data_manager.set_data(b.data.release());
    }

    ed::builder b;
    DataManager<navitia::type::Data> data_manager;
    navitia::Worker w;
};

BOOST_FIXTURE_TEST_CASE(no_wheelchair_on_vj_tests, fixture) {
    // Note: we test this through the worker to check that the arguments
    // are correctly forwarded on the whole chain

    const auto no_wheelchair_request = create_request(false, "B");
    // we ask for a journey without a wheelchair, we arrive at 9h
    pbnavitia::Response resp = w.dispatch(no_wheelchair_request);

    BOOST_REQUIRE_EQUAL(resp.response_type(), pbnavitia::ITINERARY_FOUND);
    BOOST_REQUIRE_EQUAL(resp.journeys_size(), 1);
    pbnavitia::Journey journey = resp.journeys(0);

    BOOST_CHECK_EQUAL(journey.arrival_date_time(), navitia::test::to_posix_timestamp("20150314T090000"));
}

BOOST_FIXTURE_TEST_CASE(wheelchair_on_vj_tests, fixture) {
    const auto no_wheelchair_request = create_request(true, "B");
    // we ask for a journey without a wheelchair, we arrive at 9h
    pbnavitia::Response resp = w.dispatch(no_wheelchair_request);

    BOOST_REQUIRE_EQUAL(resp.response_type(), pbnavitia::ITINERARY_FOUND);
    BOOST_REQUIRE_EQUAL(resp.journeys_size(), 1);
    pbnavitia::Journey journey = resp.journeys(0);

    BOOST_CHECK_EQUAL(journey.arrival_date_time(), navitia::test::to_posix_timestamp("20150314T100000"));
}


BOOST_FIXTURE_TEST_CASE(wheelchair_on_stop_tests, fixture) {
    const auto no_wheelchair_request = create_request(true, "C");
    pbnavitia::Response resp = w.dispatch(no_wheelchair_request);

    BOOST_REQUIRE_EQUAL(resp.response_type(), pbnavitia::NO_SOLUTION);
}
