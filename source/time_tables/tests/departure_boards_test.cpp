/* Copyright © 2001-2014, Canal TP and/or its affiliates. All rights reserved.
  
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
#define BOOST_TEST_MODULE test_ed
#include <boost/test/unit_test.hpp>
#include "ed/build_helper.h"
#include "type/type.h"
#include "tests/utils_test.h"
#include "departure_board_test_data.h"
#include "routing/raptor.h"

struct logger_initialized {
    logger_initialized()   { init_logger(); }
};
BOOST_GLOBAL_FIXTURE( logger_initialized )

static int32_t time_to_int(int h, int m, int s) {
    auto dur = navitia::time_duration(h, m, s);
    return dur.total_seconds(); //time are always number of seconds from midnight
}

using namespace navitia::timetables;

static boost::gregorian::date date(std::string str) {
    return boost::gregorian::from_undelimited_string(str);
}

//for more concice test
static pt::ptime d(std::string str) {
    return boost::posix_time::from_iso_string(str);
}

BOOST_AUTO_TEST_CASE(departureboard_test1) {
    ed::builder b("20150615");
    b.vj("A", "110011000001", "", true, "vj1", "", "jp1")("stop1", 10*3600, 10*3600)("stop2", 10*3600 + 30*60,10*3600 + 30*60);
    b.vj("B", "110000001111", "", true, "vj2", "", "jp2")("stop1", 10*3600 + 10*60, 10*3600 + 10*60)("stop2", 10*3600 + 40*60,10*3600 + 40*60)("stop3", 10*3600 + 50*60,10*3600 + 50*60);

    const auto it1 = b.sas.find("stop2");
    b.data->pt_data->routes.front()->destination= it1->second; // Route A
    const auto it2 = b.sas.find("stop3");
    b.data->pt_data->routes.back()->destination= it2->second; // Route B
    b.finish();
    b.data->pt_data->index();
    b.data->build_raptor();

    boost::gregorian::date begin = boost::gregorian::date_from_iso_string("20150615");
    boost::gregorian::date end = boost::gregorian::date_from_iso_string("20150630");

    b.data->meta->production_date = boost::gregorian::date_period(begin, end);
    // normal departure board
    pbnavitia::Response resp = departure_board("stop_point.uri=stop1", {}, {}, d("20150615T094500"), 43200, 0, std::numeric_limits<int>::max(), 1, 10, 0, *(b.data), false);
    BOOST_REQUIRE_EQUAL(resp.stop_schedules_size(), 2);
    BOOST_REQUIRE_EQUAL(resp.stop_schedules(0).date_times_size(),1);
    BOOST_REQUIRE_EQUAL(resp.stop_schedules(1).date_times_size(),1);

    // no departure for route "A"
    resp = departure_board("stop_point.uri=stop1", {}, {}, d("20150616T094500"), 43200, 0, std::numeric_limits<int>::max(), 1, 10, 0, *(b.data), false);
    BOOST_REQUIRE_EQUAL(resp.stop_schedules_size(), 2);
    BOOST_REQUIRE_EQUAL(resp.stop_schedules(0).date_times_size(),0);
    BOOST_REQUIRE_EQUAL(resp.stop_schedules(0).route().name(), "A");
    BOOST_CHECK_EQUAL(resp.stop_schedules(0).response_status(), pbnavitia::ResponseStatus::no_departure_this_day);
    BOOST_REQUIRE_EQUAL(resp.stop_schedules(1).route().name(), "B");
    BOOST_REQUIRE_EQUAL(resp.stop_schedules(1).date_times_size(),1);

    // no departure for all routes
    resp = departure_board("stop_point.uri=stop1", {}, {}, d("20150619T094500"), 43200, 0, std::numeric_limits<int>::max(), 1, 10, 0, *(b.data), false);
    BOOST_REQUIRE_EQUAL(resp.stop_schedules_size(), 2);
    BOOST_REQUIRE_EQUAL(resp.stop_schedules(0).date_times_size(),0);
    BOOST_REQUIRE_EQUAL(resp.stop_schedules(0).route().name(), "A");
    BOOST_CHECK_EQUAL(resp.stop_schedules(0).response_status(), pbnavitia::ResponseStatus::no_departure_this_day);
    BOOST_REQUIRE_EQUAL(resp.stop_schedules(1).route().name(), "B");
    BOOST_REQUIRE_EQUAL(resp.stop_schedules(1).date_times_size(),0);
    BOOST_CHECK_EQUAL(resp.stop_schedules(1).response_status(), pbnavitia::ResponseStatus::no_departure_this_day);

    // no departure for route "B"
    resp = departure_board("stop_point.uri=stop1", {}, {}, d("20150621T094500"), 43200, 0, std::numeric_limits<int>::max(), 1, 10, 0, *(b.data), false);
    BOOST_REQUIRE_EQUAL(resp.stop_schedules_size(), 2);
    BOOST_REQUIRE_EQUAL(resp.stop_schedules(0).date_times_size(),1);
    BOOST_REQUIRE_EQUAL(resp.stop_schedules(0).route().name(), "A");
    BOOST_REQUIRE_EQUAL(resp.stop_schedules(1).route().name(), "B");
    BOOST_CHECK_EQUAL(resp.stop_schedules(1).response_status(), pbnavitia::ResponseStatus::no_departure_this_day);

    // Terminus for route "A"
    resp = departure_board("stop_point.uri=stop2", {}, {}, d("20150615T094500"), 43200, 0, std::numeric_limits<int>::max(), 1, 10, 0, *(b.data), false);
    BOOST_REQUIRE_EQUAL(resp.stop_schedules_size(), 2);
    BOOST_REQUIRE_EQUAL(resp.stop_schedules(0).route().name(), "A");
    BOOST_CHECK_EQUAL(resp.stop_schedules(0).response_status(), pbnavitia::ResponseStatus::terminus);
    BOOST_REQUIRE_EQUAL(resp.stop_schedules(1).route().name(), "B");
    BOOST_CHECK_EQUAL(resp.stop_schedules(1).date_times_size(), 1);

    // Terminus for route "B"
    resp = departure_board("stop_point.uri=stop3", {}, {}, d("20150615T094500"), 43200, 0, std::numeric_limits<int>::max(), 1, 10, 0, *(b.data), false);
    BOOST_REQUIRE_EQUAL(resp.stop_schedules_size(), 1);
    BOOST_REQUIRE_EQUAL(resp.stop_schedules(0).route().name(), "B");
    BOOST_CHECK_EQUAL(resp.stop_schedules(0).response_status(), pbnavitia::ResponseStatus::terminus);

    resp = departure_board("stop_point.uri=stop2", {}, {}, d("20120701T094500"), 86400, 0, std::numeric_limits<int>::max(), 1, 10, 0, *(b.data), false);
    BOOST_REQUIRE_EQUAL(resp.error().id(), pbnavitia::Error::date_out_of_bounds);
}


BOOST_AUTO_TEST_CASE(partial_terminus_test1) {
    /*
     * Check partial terminus tag
     *
     * 2VJ on the line, one A->B->C and one A->B
     *
     * stop schedule for B must say it is a partial_terminus and stop_schedule on C must say it is a real terminus
     * */
    ed::builder b("20150615");
    b.vj("A", "11111111", "", true, "vj1", "", "jp1")("stop1", 10*3600, 10*3600)
                                                     ("stop2", 10*3600 + 30*60, 10*3600 + 30*60);
    b.vj("A", "10111111", "", true, "vj2", "", "jp2")("stop1", 10*3600 + 30*60, 10*3600 + 30*60)
                                                     ("stop2", 11*3600,11*3600)
                                                     ("stop3", 11*3600 + 30*60,36300 + 30*60);
    const auto it = b.sas.find("stop3");
    b.data->pt_data->routes.front()->destination= it->second;

    b.finish();
    b.data->pt_data->index();
    b.data->build_raptor();

    boost::gregorian::date begin = boost::gregorian::date_from_iso_string("20150615");
    boost::gregorian::date end = boost::gregorian::date_from_iso_string("20150630");

    b.data->meta->production_date = boost::gregorian::date_period(begin, end);

    pbnavitia::Response resp = departure_board("stop_point.uri=stop1", {}, {}, d("20150615T094500"), 86400, 0, std::numeric_limits<int>::max(), 1, 10, 0, *(b.data), false);
    BOOST_REQUIRE_EQUAL(resp.stop_schedules_size(), 1);
    pbnavitia::StopSchedule stop_schedule = resp.stop_schedules(0);
    BOOST_CHECK(stop_schedule.date_times_size() == 2);
    BOOST_CHECK_EQUAL(stop_schedule.date_times(0).properties().destination().destination(), "stop2");
    BOOST_CHECK_EQUAL(stop_schedule.date_times(0).properties().vehicle_journey_id(), "vj1");
    BOOST_CHECK_EQUAL(stop_schedule.date_times(0).dt_status(), pbnavitia::ResponseStatus::partial_terminus);

}


BOOST_FIXTURE_TEST_CASE(test_data_set, calendar_fixture) {
    //simple test on the data set creation

    //we check that each vj is associated with the right calendar
    //NOTE: this is better checked in the UT for associated cal
    BOOST_REQUIRE_EQUAL(b.data->pt_data->meta_vj["week"]->associated_calendars.size(), 1);
    BOOST_REQUIRE(b.data->pt_data->meta_vj["week"]->associated_calendars["week_cal"]);
    BOOST_REQUIRE_EQUAL(b.data->pt_data->meta_vj["week_bis"]->associated_calendars.size(), 1);
    BOOST_REQUIRE(b.data->pt_data->meta_vj["week_bis"]->associated_calendars["week_cal"]);
    BOOST_REQUIRE_EQUAL(b.data->pt_data->meta_vj["weekend"]->associated_calendars.size(), 1);
    BOOST_REQUIRE(b.data->pt_data->meta_vj["weekend"]->associated_calendars["weekend_cal"]);
    BOOST_REQUIRE_EQUAL(b.data->pt_data->meta_vj["all"]->associated_calendars.size(), 2);
    BOOST_REQUIRE(b.data->pt_data->meta_vj["all"]->associated_calendars["week_cal"]);
    BOOST_REQUIRE(b.data->pt_data->meta_vj["all"]->associated_calendars["weekend_cal"]);
    BOOST_REQUIRE(b.data->pt_data->meta_vj["wednesday"]->associated_calendars.empty());
}

/*
 * unknown calendar in request => error
 */
BOOST_FIXTURE_TEST_CASE(test_no_weekend, calendar_fixture) {

    //when asked on non existent calendar, we get an error
    const boost::optional<const std::string> calendar_id{"bob_the_calendar"};

    pbnavitia::Response resp = departure_board("stop_point.uri=stop1", calendar_id, {}, d("20120615T080000"), 86400, 0, std::numeric_limits<int>::max(), 1, 10, 0, *(b.data), false);

    BOOST_REQUIRE(resp.has_error());
    BOOST_REQUIRE(! resp.error().message().empty());
}

/*
 * For this test we want to get the schedule for the week end
 * we thus will get the 'week end' vj + the 'all' vj
 */
BOOST_FIXTURE_TEST_CASE(test_calendar_weekend, calendar_fixture) {
    const boost::optional<const std::string> calendar_id{"weekend_cal"};

    pbnavitia::Response resp = departure_board("stop_point.uri=stop1", calendar_id, {}, d("20120615T080000"), 86400, 0, std::numeric_limits<int>::max(), 1, 10, 0, *(b.data), false);

    BOOST_REQUIRE(! resp.has_error());
    BOOST_CHECK_EQUAL(resp.stop_schedules_size(), 1);
    pbnavitia::StopSchedule stop_schedule = resp.stop_schedules(0);
    BOOST_REQUIRE_EQUAL(stop_schedule.date_times_size(), 2);
    auto stop_date_time = stop_schedule.date_times(0);
    BOOST_CHECK_EQUAL(stop_date_time.time(), time_to_int(15, 10, 00));
    BOOST_CHECK_EQUAL(stop_date_time.date(), 0); //no date

    stop_date_time = stop_schedule.date_times(1);
    BOOST_CHECK_EQUAL(stop_date_time.time(), time_to_int(20, 10, 00));
    BOOST_CHECK_EQUAL(stop_date_time.date(), 0); //no date
    //the vj 'wednesday' is never matched
}

/*
 * For this test we want to get the schedule for the week
 * we thus will get the 2 'week' vj + the 'all' vj
 */
BOOST_FIXTURE_TEST_CASE(test_calendar_week, calendar_fixture) {
    boost::optional<const std::string> calendar_id{"week_cal"};

    pbnavitia::Response resp = departure_board("stop_point.uri=stop1", calendar_id, {}, d("20120615T080000"), 86400, 0, std::numeric_limits<int>::max(), 1, 10, 0, *(b.data), false);

    BOOST_REQUIRE(! resp.has_error());
    BOOST_CHECK_EQUAL(resp.stop_schedules_size(), 1);
    pbnavitia::StopSchedule stop_schedule = resp.stop_schedules(0);
    BOOST_REQUIRE_EQUAL(stop_schedule.date_times_size(), 3);
    auto stop_date_time = stop_schedule.date_times(0);
    BOOST_CHECK_EQUAL(stop_date_time.time(), time_to_int(10, 10, 00));
    BOOST_CHECK_EQUAL(stop_date_time.date(), 0); //no date
    stop_date_time = stop_schedule.date_times(1);
    BOOST_CHECK_EQUAL(stop_date_time.time(), time_to_int(11, 10, 00));
    BOOST_CHECK_EQUAL(stop_date_time.date(), 0); //no date
    stop_date_time = stop_schedule.date_times(2);
    BOOST_CHECK_EQUAL(stop_date_time.time(), time_to_int(15, 10, 00));
    BOOST_CHECK_EQUAL(stop_date_time.date(), 0); //no date
    //the vj 'wednesday' is never matched
}

/*
 * when asked with a calendar not associated with the line, we got an empty schedule
 */
BOOST_FIXTURE_TEST_CASE(test_not_associated_cal, calendar_fixture) {
    boost::optional<const std::string> calendar_id{"not_associated_cal"};

    pbnavitia::Response resp = departure_board("stop_point.uri=stop1", calendar_id, {}, d("20120615T080000"), 86400, 0, std::numeric_limits<int>::max(), 1, 10, 0, *(b.data), false);

    BOOST_REQUIRE(! resp.has_error());
    BOOST_CHECK_EQUAL(resp.stop_schedules_size(), 1);
    pbnavitia::StopSchedule stop_schedule = resp.stop_schedules(0);
    BOOST_REQUIRE_EQUAL(stop_schedule.date_times_size(), 0);
}

BOOST_FIXTURE_TEST_CASE(test_calendar_with_exception, calendar_fixture) {
    //we add a new calendar that nearly match a vj
    auto nearly_cal = new navitia::type::Calendar(b.data->meta->production_date.begin());
    nearly_cal->uri = "nearly_cal";
    nearly_cal->active_periods.push_back({beg, end_of_year});
    nearly_cal->week_pattern = std::bitset<7>{"1111100"};
    //we add 2 exceptions (2 add), one by week
    navitia::type::ExceptionDate exception_date;
    exception_date.date = date("20120618");
    exception_date.type = navitia::type::ExceptionDate::ExceptionType::add;
    nearly_cal->exceptions.push_back(exception_date);
    exception_date.date = date("20120619");
    exception_date.type = navitia::type::ExceptionDate::ExceptionType::add;
    nearly_cal->exceptions.push_back(exception_date);

    b.data->pt_data->calendars.push_back(nearly_cal);
    b.lines["line:A"]->calendar_list.push_back(nearly_cal);

    // load metavj calendar association from database (association is tested in ed/tests/associated_calendar_test.cpp)
    navitia::type::AssociatedCalendar* associated_nearly_calendar = new navitia::type::AssociatedCalendar();
    associated_nearly_calendar->calendar = nearly_cal;
    exception_date.date = date("20120618");
    exception_date.type = navitia::type::ExceptionDate::ExceptionType::sub;
    associated_nearly_calendar->exceptions.push_back(exception_date);
    exception_date.date = date("20120619");
    exception_date.type = navitia::type::ExceptionDate::ExceptionType::sub;
    associated_nearly_calendar->exceptions.push_back(exception_date);
    b.data->pt_data->associated_calendars.push_back(associated_nearly_calendar);
    b.data->pt_data->meta_vj["week"]->associated_calendars[nearly_cal->uri] = associated_nearly_calendar;
    b.data->pt_data->meta_vj["week_bis"]->associated_calendars[nearly_cal->uri] = associated_nearly_calendar;
    b.data->pt_data->meta_vj["all"]->associated_calendars[nearly_cal->uri] = associated_nearly_calendar;

    //call all the init again
    b.finish();
    b.data->build_uri();
    b.data->pt_data->index();
    b.data->build_raptor();

    b.data->complete();

    boost::optional<const std::string> calendar_id{"nearly_cal"};

    pbnavitia::Response resp = departure_board("stop_point.uri=stop1", calendar_id, {}, d("20120615T080000"), 86400, 0, std::numeric_limits<int>::max(), 1, 10, 0, *(b.data), false);

    //it should match only the 'all' vj
    BOOST_REQUIRE(! resp.has_error());
    BOOST_CHECK_EQUAL(resp.stop_schedules_size(), 1);
    pbnavitia::StopSchedule stop_schedule = resp.stop_schedules(0);
    BOOST_REQUIRE_EQUAL(stop_schedule.date_times_size(), 3);
    auto stop_date_time = stop_schedule.date_times(0);
    BOOST_CHECK_EQUAL(stop_date_time.time(), time_to_int(10, 10, 00));
    BOOST_CHECK_EQUAL(stop_date_time.date(), 0); //no date

    auto properties = stop_date_time.properties();
    BOOST_REQUIRE_EQUAL(properties.exceptions_size(), 2);
    auto exception = properties.exceptions(0);
    BOOST_REQUIRE_EQUAL(exception.uri(), "exception:120120618");
    BOOST_REQUIRE_EQUAL(exception.date(), "20120618");
    BOOST_REQUIRE_EQUAL(exception.type(), pbnavitia::ExceptionType::Remove);

    exception = properties.exceptions(1);
    BOOST_REQUIRE_EQUAL(exception.uri(), "exception:120120619");
    BOOST_REQUIRE_EQUAL(exception.date(), "20120619");
    BOOST_REQUIRE_EQUAL(exception.type(), pbnavitia::ExceptionType::Remove);
}

struct small_cal_fixture {
    ed::builder b;
    small_cal_fixture(): b("20120614") {
        //vj1 has stoptimes all day from 00:10 every hour
        b.frequency_vj("line:A", 60*10, 24*60*60 + 60*10 - 1, 60*60, "network:R", "1111111", "", true, "vj1")
                ("stop1", 0, 0)
                ("stop2", 10, 20); //we need stop1 not to be the terminus

        //we add a calendar that match the vj
        auto cal = new navitia::type::Calendar(b.data->meta->production_date.begin());
        cal->uri = "cal";
        cal->active_periods.emplace_back(boost::gregorian::from_undelimited_string("20120614"),
                                         boost::gregorian::from_undelimited_string("20120621"));
        cal->week_pattern = std::bitset<7>{"1111111"};

        b.data->pt_data->calendars.push_back(cal);
        b.lines["line:A"]->calendar_list.push_back(cal);

        //we add a calendar with no activity
        auto empty_cal = new navitia::type::Calendar(b.data->meta->production_date.begin());
        empty_cal->uri = "empty_cal";
        empty_cal->active_periods.emplace_back(boost::gregorian::from_undelimited_string("20120614"),
                                         boost::gregorian::from_undelimited_string("20120621"));
        empty_cal->week_pattern = std::bitset<7>{"0000000"};

        b.data->pt_data->calendars.push_back(empty_cal);
        b.lines["line:A"]->calendar_list.push_back(empty_cal);

        // load metavj calendar association from database
        navitia::type::AssociatedCalendar* associated_calendar = new navitia::type::AssociatedCalendar();
        associated_calendar->calendar = cal;
        b.data->pt_data->associated_calendars.push_back(associated_calendar);
        b.data->pt_data->meta_vj["vj1"]->associated_calendars[cal->uri] = associated_calendar;

        //call all the init again
        b.finish();
        b.data->build_uri();
        b.data->pt_data->index();
        b.data->build_raptor();

        b.data->complete();
    }
};

/**
 * test that when asked for a schedule from a given time in the day
 * we have the schedule from this time and 'cycling' to the next day
 */

BOOST_FIXTURE_TEST_CASE(test_calendar_start_time, small_cal_fixture) {

    pbnavitia::Response resp = departure_board("stop_point.uri=stop1", std::string("cal"), {}, d("20120615T080000"),
                                                86400, 0, std::numeric_limits<int>::max(),
                                                1, 10, 0, *(b.data), false);

    //we should get a nice schedule, first stop at 08:10, last at 07:10
    BOOST_REQUIRE(! resp.has_error());

    BOOST_CHECK_EQUAL(resp.stop_schedules_size(), 1);
    pbnavitia::StopSchedule stop_schedule = resp.stop_schedules(0);
    BOOST_REQUIRE_EQUAL(stop_schedule.date_times_size(), 24);

    for (size_t i = 0; i < 24; ++i) {
        auto hour = (i + 8) % 24;
        auto stop_date_time = stop_schedule.date_times(i);

        BOOST_CHECK_EQUAL(stop_date_time.time(), time_to_int(hour, 10, 00));
        BOOST_CHECK_EQUAL(stop_date_time.date(), 0); //no date
    }
}

/**
 * test the departarture board with a calenday without activity
 * No board must be returned
 */

BOOST_FIXTURE_TEST_CASE(test_not_matched_cal, small_cal_fixture) {

    pbnavitia::Response resp = departure_board("stop_point.uri=stop1", std::string("empty_cal"), {}, d("20120615T080000"),
                                                86400, 0, std::numeric_limits<int>::max(),
                                                1, 10, 0, *(b.data), false);

    BOOST_REQUIRE(! resp.has_error());
    //no error but no results
    BOOST_CHECK_EQUAL(resp.stop_schedules_size(), 1);
    pbnavitia::StopSchedule stop_schedule = resp.stop_schedules(0);
    BOOST_REQUIRE_EQUAL(stop_schedule.date_times_size(), 0);
}

/**
 * test that when asked for a schedule from a given *period* in a day
 * we have the schedule from this time and finishing at the end of the period
 */
BOOST_FIXTURE_TEST_CASE(test_calendar_start_time_period, small_cal_fixture) {

    size_t nb_hour = 5;
    auto duration = nb_hour*60*60;
    pbnavitia::Response resp = departure_board("stop_point.uri=stop1", std::string("cal"), {}, d("20120615T080000"),
                                               duration, 0, std::numeric_limits<int>::max(),
                                               1, 10, 0, *(b.data), false);

    //we should get a nice schedule, first stop at 08:10, last at 13:10
    BOOST_REQUIRE(! resp.has_error());

    BOOST_CHECK_EQUAL(resp.stop_schedules_size(), 1);
    pbnavitia::StopSchedule stop_schedule = resp.stop_schedules(0);
    BOOST_REQUIRE_EQUAL(stop_schedule.date_times_size(), nb_hour);

    for (size_t i = 0; i < nb_hour; ++i) {
        auto hour = i + 8;
        auto stop_date_time = stop_schedule.date_times(i);

        BOOST_CHECK_EQUAL(stop_date_time.time(), time_to_int(hour, 10, 00));
        BOOST_CHECK_EQUAL(stop_date_time.date(), 0); //no date
    }
}

/**
 * test that when asked for a schedule from a given *period* in a day,
 * it works even if the period extend to the next day
 * we have the schedule from this time and finishing at the end of the period
 */
BOOST_FIXTURE_TEST_CASE(test_calendar_start_time_period_before, small_cal_fixture) {

    //we ask for a schedule from 20:00 to 04:00
    size_t nb_hour = 8;
    auto duration = nb_hour*60*60;
    pbnavitia::Response resp = departure_board("stop_point.uri=stop1", std::string("cal"), {}, d("20120615T200000"),
                                               duration, 0, std::numeric_limits<int>::max(),
                                               1, 10, 0, *(b.data), false);

    //we should get a nice schedule, first stop at 20:10, last at 04:10
    BOOST_REQUIRE(! resp.has_error());

    BOOST_CHECK_EQUAL(resp.stop_schedules_size(), 1);
    pbnavitia::StopSchedule stop_schedule = resp.stop_schedules(0);
    BOOST_REQUIRE_EQUAL(stop_schedule.date_times_size(), nb_hour);

    for (size_t i = 0; i < nb_hour; ++i) {
        auto hour = (i + 20)%24;
        auto stop_date_time = stop_schedule.date_times(i);

        BOOST_CHECK_EQUAL(stop_date_time.time(), time_to_int(hour, 10, 00));
        BOOST_CHECK_EQUAL(stop_date_time.date(), 0); //no date
    }
}


BOOST_FIXTURE_TEST_CASE(test_journey, calendar_fixture) {
    // some jormungandr test use the calendar_fixture for simple journey computation, so we add a simple test on journey
    navitia::routing::RAPTOR raptor(*(b.data));
    navitia::type::PT_Data& d = *b.data->pt_data;

    auto res1 = raptor.compute(d.stop_areas_map["stop1"], d.stop_areas_map["stop2"], 8*60*60, 0, navitia::DateTimeUtils::inf, false, true);

    //we must have a journey
    BOOST_REQUIRE_EQUAL(res1.size(), 1);
}
