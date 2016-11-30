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

#pragma once

//forward declare
namespace navitia{
namespace routing{
    struct RAPTOR;
}
}

#include "georef/street_network.h"
#include "type/type.pb.h"
#include "type/response.pb.h"
#include "type/request.pb.h"
#include "kraken/data_manager.h"
#include "utils/logger.h"
#include "kraken/configuration.h"
#include "type/pb_converter.h"

#include <memory>
#include <limits>

namespace navitia {

struct JourneysArg {
    std::vector<type::EntryPoint> origins;
    type::AccessibiliteParams accessibilite_params;
    std::vector<std::string> forbidden;
    type::RTLevel rt_level;
    std::vector<type::EntryPoint> destinations;
    std::vector<uint64_t> datetimes;
    JourneysArg(std::vector<type::EntryPoint> origins,
                type::AccessibiliteParams accessibilite_params,
                std::vector<std::string> forbidden,
                type::RTLevel rt_level,
                std::vector<type::EntryPoint> destinations,
                std::vector<uint64_t> datetimes);
    JourneysArg();
};

class Worker {
    private:
        std::unique_ptr<navitia::routing::RAPTOR> planner;
        std::unique_ptr<navitia::georef::StreetNetwork> street_network_worker;

        // we keep a reference to data_manager in each thread
        DataManager<navitia::type::Data>& data_manager;
        const kraken::Configuration conf;
        log4cplus::Logger logger;
        size_t last_data_identifier = std::numeric_limits<size_t>::max();// to check that data did not change, do not use directly
        boost::posix_time::ptime last_load_at;

    public:
        Worker(DataManager<navitia::type::Data>& data_manager, kraken::Configuration conf);
        //we override de destructor this way we can forward declare Raptor
        //see: https://stackoverflow.com/questions/6012157/is-stdunique-ptrt-required-to-know-the-full-definition-of-t
        ~Worker();

        pbnavitia::Response dispatch(const pbnavitia::Request & request);

        void init_worker_data(const boost::shared_ptr<const navitia::type::Data> data);

        void metadatas(pbnavitia::Response& response);
        void feed_publisher(pbnavitia::Response& response);
        pbnavitia::Response status();
        pbnavitia::Response geo_status();
        pbnavitia::Response autocomplete(const pbnavitia::PlacesRequest &request,
                                         const boost::posix_time::ptime& current_datetime);
        pbnavitia::Response place_uri(const pbnavitia::PlaceUriRequest &request,
                                      const boost::posix_time::ptime& current_datetime);
        pbnavitia::Response next_stop_times(const pbnavitia::NextStopTimeRequest &request, pbnavitia::API api,
                                            const boost::posix_time::ptime& current_datetime);
        pbnavitia::Response proximity_list(const pbnavitia::PlacesNearbyRequest &request,
                                           const boost::posix_time::ptime& current_datetime,
                                           const bool disable_feedpublisher);

        JourneysArg fill_journeys(const pbnavitia::JourneysRequest &request);
        pbnavitia::Response err_msg_isochron(const std::string& err_msg, navitia::PbCreator& pb_creator);
        pbnavitia::Response journeys(const pbnavitia::JourneysRequest &request, pbnavitia::API api,
                                     const boost::posix_time::ptime& current_datetime);
        pbnavitia::Response pt_ref(const pbnavitia::PTRefRequest &request,
                                   const boost::posix_time::ptime& current_datetime);
        pbnavitia::Response traffic_reports(const pbnavitia::TrafficReportsRequest &request,
                                            const boost::posix_time::ptime& current_datetime);
        pbnavitia::Response calendars(const pbnavitia::CalendarsRequest &request,
                                      const boost::posix_time::ptime& current_datetime);
        pbnavitia::Response pt_object(const pbnavitia::PtobjectRequest &request,
                                      const boost::posix_time::ptime& current_datetime);
        pbnavitia::Response place_code(const pbnavitia::PlaceCodeRequest &request);
        pbnavitia::Response nearest_stop_points(const pbnavitia::NearestStopPointsRequest& request);
        boost::optional<pbnavitia::Response> set_journeys_args(const pbnavitia::JourneysRequest& request,
                                                               const boost::posix_time::ptime& current_datetime,
                                                               JourneysArg& arg, const std::string& name);
        pbnavitia::Response graphical_isochrone(const pbnavitia::GraphicalIsochroneRequest& request,
                                                const boost::posix_time::ptime& current_datetime);
        pbnavitia::Response heat_map(const pbnavitia::HeatMapRequest& request,
                                     const boost::posix_time::ptime& current_datetime);
        pbnavitia::Response car_co2_emission_on_crow_fly(const pbnavitia::CarCO2EmissionRequest& request);
        pbnavitia::Response direct_path(const pbnavitia::Request& request);

        /*
         * Given N origins and M destinations and street network mode, it returns a NxM matrix which contains durations
         * from origin to destination by taking street network
         * */
        pbnavitia::Response street_network_routing_matrix(const pbnavitia::StreetNetworkRoutingMatrixRequest& request);
        pbnavitia::Response odt_stop_points(const pbnavitia::GeographicalCoord& request);
};

type::EntryPoint make_sn_entry_point(const std::string& place,
        const std::string& mode,
        const float speed,
        const int max_duration,
        const navitia::type::Data& data);

}
