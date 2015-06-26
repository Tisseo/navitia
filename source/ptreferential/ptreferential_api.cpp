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

#include "ptreferential.h"
#include "ptreferential_api.h"
#include "type/pb_converter.h"
#include "type/data.h"
#include "type/pt_data.h"

namespace pt = boost::posix_time;

namespace navitia{ namespace ptref{

static pbnavitia::Response extract_data(const type::Data & data,
                                        type::Type_e requested_type,
                                        std::vector<type::idx_t> & rows,
                                        const int depth, const bool show_codes,
                                        boost::posix_time::ptime current_time) {
    pbnavitia::Response result;
    auto action_period = pt::time_period(current_time, pt::seconds(1));
    for(auto idx : rows){
        switch(requested_type){
        case Type_e::ValidityPattern:
            fill_pb_object(data.pt_data->validity_patterns[idx], data,
                           result.add_validity_patterns(), depth, current_time, action_period);
            break;
        case Type_e::Line:
            fill_pb_object(data.pt_data->lines[idx], data, result.add_lines(),
                           depth, current_time, action_period, show_codes);
            break;
        case Type_e::LineGroup:
            fill_pb_object(data.pt_data->line_groups[idx], data, result.add_line_groups(),
                           depth, current_time, action_period, show_codes);
            break;
        case Type_e::JourneyPattern:
            fill_pb_object(data.pt_data->journey_patterns[idx], data,
                           result.add_journey_patterns(), depth, current_time, action_period);
            break;
        case Type_e::StopPoint:
            fill_pb_object(data.pt_data->stop_points[idx], data,
                           result.add_stop_points(), depth, current_time, action_period, show_codes);
            break;
        case Type_e::StopArea:
            fill_pb_object(data.pt_data->stop_areas[idx], data,
                           result.add_stop_areas(), depth, current_time, action_period, show_codes);
            break;
        case Type_e::Network:
            fill_pb_object(data.pt_data->networks[idx], data,
                           result.add_networks(), depth, current_time, action_period, show_codes);
            break;
        case Type_e::PhysicalMode:
            fill_pb_object(data.pt_data->physical_modes[idx], data,
                           result.add_physical_modes(), depth, current_time, action_period);
            break;
        case Type_e::CommercialMode:
            fill_pb_object(data.pt_data->commercial_modes[idx], data,
                           result.add_commercial_modes(), depth, current_time, action_period);
            break;
        case Type_e::JourneyPatternPoint:
            fill_pb_object(data.pt_data->journey_pattern_points[idx], data,
                           result.add_journey_pattern_points(), depth, current_time, action_period);
            break;
        case Type_e::Company:
            fill_pb_object(data.pt_data->companies[idx], data,
                           result.add_companies(), depth, current_time, action_period);
            break;
        case Type_e::Route:
            fill_pb_object(data.pt_data->routes[idx], data,
                    result.add_routes(), depth, current_time, action_period, show_codes);
            break;
        case Type_e::POI:
            fill_pb_object(data.geo_ref->pois[idx], data,
                           result.add_pois(), depth, current_time, action_period);
            break;
        case Type_e::POIType:
            fill_pb_object(data.geo_ref->poitypes[idx], data,
                           result.add_poi_types(), depth, current_time, action_period);
            break;
        case Type_e::Connection:
            fill_pb_object(data.pt_data->stop_point_connections[idx], data,
                           result.add_connections(), depth, current_time, action_period);
            break;
        case Type_e::VehicleJourney:
            fill_pb_object(data.pt_data->vehicle_journeys[idx], data,
                           result.add_vehicle_journeys(), depth, current_time, action_period, show_codes);
            break;
        case Type_e::Calendar:
            fill_pb_object(data.pt_data->calendars[idx], data,
                           result.add_calendars(), depth, current_time, action_period, show_codes);
            break;
        default: break;
        }
    }
    return result;
}


pbnavitia::Response query_pb(type::Type_e requested_type,
                             const std::string& request,
                             const std::vector<std::string>& forbidden_uris,
                             const type::OdtLevel_e odt_level,
                             const int depth,
                             const bool show_codes,
                             const int startPage,
                             const int count,
                             const type::Data& data,
                             boost::posix_time::ptime current_time){
    std::vector<type::idx_t> final_indexes;
    pbnavitia::Response pb_response;
    int total_result;
    try {
        final_indexes = make_query(requested_type, request, forbidden_uris, odt_level, data);
    } catch(const parsing_error &parse_error) {
        fill_pb_error(pbnavitia::Error::unable_to_parse, "Unable to parse :" + parse_error.more, pb_response.mutable_error());
        return pb_response;
    } catch(const ptref_error &pt_error) {
        fill_pb_error(pbnavitia::Error::bad_filter, "ptref : " + pt_error.more, pb_response.mutable_error());
        return pb_response;
    }
    total_result = final_indexes.size();
    final_indexes = paginate(final_indexes, count, startPage);

    pb_response = extract_data(data, requested_type, final_indexes, depth, show_codes, current_time);
    auto pagination = pb_response.mutable_pagination();
    pagination->set_totalresult(total_result);
    pagination->set_startpage(startPage);
    pagination->set_itemsperpage(count);
    pagination->set_itemsonpage(final_indexes.size());
    return pb_response;
}


}}
