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

#include "utils/init.h"
#include "routing/tests/routing_api_test_data.h"
#include "mock_kraken.h"
#include "type/type.h"

static boost::gregorian::date_period period(std::string beg, std::string end) {
    boost::gregorian::date start_date = boost::gregorian::from_undelimited_string(beg);
    boost::gregorian::date end_date = boost::gregorian::from_undelimited_string(end); //end is not in the period
    return {start_date, end_date};
}

struct data_set {

    data_set() : b("20140101") {
        //add calendar
        navitia::type::Calendar* wednesday_cal {new navitia::type::Calendar(b.data->meta->production_date.begin())};
        wednesday_cal->name = "the wednesday calendar";
        wednesday_cal->uri = "wednesday";
        wednesday_cal->active_periods.push_back(period("20140101", "20140911"));
        wednesday_cal->week_pattern = std::bitset<7>{"0010000"};
        for (int i = 1; i <= 3; ++i) {
            navitia::type::ExceptionDate exd;
            exd.date = boost::gregorian::date(2014, i, 10+i); //random date for the exceptions
            exd.type = navitia::type::ExceptionDate::ExceptionType::sub;
            wednesday_cal->exceptions.push_back(exd);
        }
        b.data->pt_data->calendars.push_back(wednesday_cal);

        navitia::type::Calendar* monday_cal {new navitia::type::Calendar(b.data->meta->production_date.begin())};
        monday_cal->name = "the monday calendar";
        monday_cal->uri = "monday";
        monday_cal->active_periods.push_back(period("20140105", "20140911"));
        monday_cal->week_pattern = std::bitset<7>{"1000000"};
        for (int i = 1; i <= 3; ++i) {
            navitia::type::ExceptionDate exd;
            exd.date = boost::gregorian::date(2014, i+3, 5+i); //random date for the exceptions
            exd.type = navitia::type::ExceptionDate::ExceptionType::sub;
            monday_cal->exceptions.push_back(exd);
        }
        b.data->pt_data->calendars.push_back(monday_cal);
        //add lines
        b.sa("stop_area:stop1", 9, 9, false, true)("stop_area:stop1", 9, 9);
        b.sa("stop_area:stop2", 10, 10, false, true)("stop_area:stop2", 10, 10);
        b.vj("line:A", "", "", true, "vj1", "", "", "physical_mode:Car")
                ("stop_area:stop1", 10 * 3600 + 15 * 60, 10 * 3600 + 15 * 60)
                ("stop_area:stop2", 11 * 3600 + 10 * 60, 11 * 3600 + 10 * 60);
        b.lines["line:A"]->calendar_list.push_back(wednesday_cal);
        b.lines["line:A"]->calendar_list.push_back(monday_cal);

        // we add a stop area with a strange name (with space and special char)
        b.sa("stop_with name bob \" , é", 20, 20);
        b.vj("line:B", "", "", true, "vj_b", "", "", "physical_mode:Car")
                ("stop_point:stop_with name bob \" , é", "8:00"_t)("stop_area:stop1", "9:00"_t);

        //add a mock shape
        b.lines["line:A"]->shape = {
                                    {{1,2}, {2,2}, {4,5}},
                                    {{10,20}, {20,20}, {40,50}}
                                   };

        for (auto r: b.lines["line:A"]->route_list) {
            r->shape = {
                {{1,2}, {2,2}, {4,5}},
                {{10,20}, {20,20}, {40,50}}
            };
            r->destination = b.sas.find("stop_area:stop2")->second;
        }
        for (auto r: b.lines["line:B"]->route_list) {
            r->destination = b.sas.find("stop_area:stop1")->second;
        }
        b.lines["line:A"]->codes["external_code"] = "A";
        b.lines["line:A"]->codes["codeB"] = "B";
        b.lines["line:A"]->codes["codeC"] = "C";

        b.data->build_uri();

        navitia::type::VehicleJourney* vj = b.data->pt_data->vehicle_journeys_map["vj1"];
        vj->validity_pattern->add(boost::gregorian::from_undelimited_string("20140101"),
                                  boost::gregorian::from_undelimited_string("20140111"), monday_cal->week_pattern);

        //we add some comments
        auto& comments = b.data->pt_data->comments;
        comments.add(b.data->pt_data->routes_map["line:A:0"], "I'm a happy comment");
        comments.add(b.lines["line:A"], "I'm a happy comment");
        comments.add(b.sas["stop_area:stop1"], "comment on stop A");
        comments.add(b.sas["stop_area:stop1"], "the stop is sad");
        comments.add(b.data->pt_data->stop_points_map["stop_area:stop2"], "hello bob");
        comments.add(b.data->pt_data->vehicle_journeys[0], "hello");
        comments.add(b.data->pt_data->vehicle_journeys[0]->stop_time_list.front(),
                                      "stop time is blocked");
       // Company added
        navitia::type::Company* cmp = new navitia::type::Company();
        cmp->line_list.push_back(b.lines["line:A"]);
        vj->company = cmp;
        b.data->pt_data->companies.push_back(cmp);
        cmp->idx = b.data->pt_data->companies.size();
        cmp->name = "CMP1";
        cmp->uri = "CMP1";
        b.lines["line:A"]->company_list.push_back(cmp);

        // LineGroup added
        navitia::type::LineGroup* lg = new navitia::type::LineGroup();
        lg->name = "A group";
        lg->uri = "group:A";
        lg->main_line = b.lines["line:A"];
        lg->line_list.push_back(b.lines["line:A"]);
        b.lines["line:A"]->line_group_list.push_back(lg);
        comments.add(lg, "I'm a happy comment");
        b.data->pt_data->line_groups.push_back(lg);

        b.data->complete();
        b.data->build_raptor();
    }

    ed::builder b;
};

int main(int argc, const char* const argv[]) {
    navitia::init_app();

    data_set data;

    mock_kraken kraken(data.b, "main_ptref_test", argc, argv);

    return 0;
}
