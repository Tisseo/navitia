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

import navitiacommon.type_pb2 as type_pb2
import navitiacommon.request_pb2 as request_pb2
import navitiacommon.response_pb2 as response_pb2
import itertools

pb_type = {
    'stop_area': type_pb2.STOP_AREA,
    'stop_point': type_pb2.STOP_POINT,
    'address': type_pb2.ADDRESS,
    'poi': type_pb2.POI,
    'administrative_region': type_pb2.ADMINISTRATIVE_REGION,
    'line': type_pb2.LINE
}


pt_object_type = {
    'network': type_pb2.NETWORK,
    'commercial_mode': type_pb2.COMMERCIAL_MODE,
    'line': type_pb2.LINE,
    'route': type_pb2.ROUTE,
    'stop_area': type_pb2.STOP_AREA,
    'line_group': type_pb2.LINE_GROUP
}


def compare(obj1, obj2, compare_generator):
    """
    To decide that 2 objects are equals, we loop through all values of the
    compare_generator and stop at the first non equals value

    Note: the fillvalue is the value used when a generator is consumed
    (if the 2 generators does not return the same number of elt).
    by setting it to object(), we ensure that it will be !=
    from any values returned by the other generator
    """
    return all(a == b for a, b in itertools.izip_longest(compare_generator(obj1),
                                                         compare_generator(obj2),
                                                         fillvalue=object()))


def are_equals(journey1, journey2):
    """
    To decide that 2 journeys are equals, we loop through all values of the
    compare_journey_generator and stop at the first non equals value
    """
    return compare(journey1, journey2, compare_journey_generator)


def compare_journey_generator(journey):
    """
    Generator used to compare journeys together

    2 journeys are equals if they share for all the sections the same :
     * departure time
     * arrival time
     * vj
     * type
     * departure location
     * arrival location
    """
    yield journey.departure_date_time
    yield journey.arrival_date_time
    yield journey.destination.uri if journey.destination else 'no_destination'
    for s in journey.sections:
        yield s.type
        yield s.begin_date_time
        yield s.end_date_time
        yield s.uris.vehicle_journey
        #NOTE: we want to ensure that we always yield the same number of elt
        yield s.origin.uri if s.origin else 'no_origin'
        yield s.destination.uri if s.destination else 'no_destination'


def count_typed_journeys(journeys):
        return sum(1 for journey in journeys if journey.type)


class JourneySorter(object):
    """
    abstract class for journey sorter
    """
    def __init__(self, clockwise):
        self.clockwise = clockwise

    def __call__(self, j1, j2):
        raise NotImplementedError()

    def sort_by_duration_and_transfert(self, j1, j2):
        """
        we compare the duration, hence it will indirectly compare
        the departure for clockwise, and the arrival for not clockwise
        """
        if j1.duration != j2.duration:
            return j2.duration - j1.duration

        if j1.nb_transfers != j2.nb_transfers:
            return j1.nb_transfers - j2.nb_transfers

        #afterward we compare the non pt duration
        non_pt_duration_j1 = non_pt_duration_j2 = None
        for journey in [j1, j2]:
            non_pt_duration = 0
            for section in journey.sections:
                if section.type != response_pb2.PUBLIC_TRANSPORT:
                    non_pt_duration += section.duration
            if non_pt_duration_j1 is None:
                non_pt_duration_j1 = non_pt_duration
            else:
                non_pt_duration_j2 = non_pt_duration
        return non_pt_duration_j1 - non_pt_duration_j2


class ArrivalJourneySorter(JourneySorter):
    """
    Journey comparator for sort, on clockwise the sort is done by arrival time

    the comparison is different if the query is for clockwise search or not
    """
    def __init__(self, clockwise):
        super(ArrivalJourneySorter, self).__init__(clockwise)

    def __call__(self, j1, j2):
        if self.clockwise:
            #for clockwise query, we want to sort first on the arrival time
            if j1.arrival_date_time != j2.arrival_date_time:
                return -1 if j1.arrival_date_time < j2.arrival_date_time else 1
        else:
            #for non clockwise the first sort is done on departure
            if j1.departure_date_time != j2.departure_date_time:
                return -1 if j1.departure_date_time > j2.departure_date_time else 1

        return self.sort_by_duration_and_transfert(j1, j2)


class DepartureJourneySorter(JourneySorter):
    """
    Journey comparator for sort, on clockwise the sort is done by departure time

    the comparison is different if the query is for clockwise search or not
    """
    def __init__(self, clockwise):
        super(DepartureJourneySorter, self).__init__(clockwise)

    def __call__(self, j1, j2):

        if self.clockwise:
            #for clockwise query, we want to sort first on the departure time
            if j1.departure_date_time != j2.departure_date_time:
                return -1 if j1.departure_date_time < j2.departure_date_time else 1
        else:
            #for non clockwise the first sort is done on arrival
            if j1.arrival_date_time != j2.arrival_date_time:
                return -1 if j1.arrival_date_time > j2.arrival_date_time else 1

        return self.sort_by_duration_and_transfert(j1, j2)


def build_pagination(request, resp):
    pagination = resp.pagination
    if pagination.totalResult > 0:
        query_args = ""
        for key, value in request.iteritems():
            if key != "startPage":
                if isinstance(value, type([])):
                    for v in value:
                        query_args += key + "=" + unicode(v) + "&"
                else:
                    query_args += key + "=" + unicode(value) + "&"
        if pagination.startPage > 0:
            page = pagination.startPage - 1
            pagination.previousPage = query_args
            pagination.previousPage += "start_page=%i" % page
        last_id_page = (pagination.startPage + 1) * pagination.itemsPerPage
        if last_id_page < pagination.totalResult:
            page = pagination.startPage + 1
            pagination.nextPage = query_args + "start_page=%i" % page

journey_sorter = {
    'arrival_time': ArrivalJourneySorter,
    'departure_time': DepartureJourneySorter
}


def get_or_default(request, val, default):
    """
    Flask add all API param in the request dict with None by default,
    so here is a simple helper to get the default value is the key
    is not in the dict or if the value is None
    """
    val = request.get(val, default)
    if val is not None:
        return val
    return default

def updated_request_with_default(request, instance):
    if request['max_walking_duration_to_pt'] is None:
        request['max_walking_duration_to_pt'] = instance.max_walking_duration_to_pt

    if request['max_bike_duration_to_pt'] is None:
        request['max_bike_duration_to_pt'] = instance.max_bike_duration_to_pt

    if request['max_bss_duration_to_pt'] is None:
        request['max_bss_duration_to_pt'] = instance.max_bss_duration_to_pt

    if request['max_car_duration_to_pt'] is None:
        request['max_car_duration_to_pt'] = instance.max_car_duration_to_pt

    if request['max_transfers'] is None:
        request['max_transfers'] = instance.max_nb_transfers

    if request['walking_speed'] is None:
        request['walking_speed'] = instance.walking_speed

    if request['bike_speed'] is None:
        request['bike_speed'] = instance.bike_speed

    if request['bss_speed'] is None:
        request['bss_speed'] = instance.bss_speed

    if request['car_speed'] is None:
        request['car_speed'] = instance.car_speed

def change_ids(new_journeys, journey_count):
    """
    we have to change some id's on the response not to have id's collision between response

    we need to change the fare id , the section id and the fare ref in the journey
    """
    #we need to change the fare id, the section id and the fare ref in the journey
    for ticket in new_journeys.tickets:
        ticket.id = ticket.id + '_' + str(journey_count)
        for i in range(len(ticket.section_id)):
            ticket.section_id[i] = ticket.section_id[i] + '_' + str(journey_count)

    for new_journey in new_journeys.journeys:
        for i in range(len(new_journey.fare.ticket_id)):
            new_journey.fare.ticket_id[i] = new_journey.fare.ticket_id[i] \
                                            + '_' + str(journey_count)

        for section in new_journey.sections:
            section.id = section.id + '_' + str(journey_count)


def fill_uris(resp):
    if not resp:
        return
    for journey in resp.journeys:
        for section in journey.sections:
            if section.type != response_pb2.PUBLIC_TRANSPORT:
                continue
            if section.HasField("pt_display_informations"):
                uris = section.uris
                pt_infos = section.pt_display_informations
                uris.vehicle_journey = pt_infos.uris.vehicle_journey
                uris.line = pt_infos.uris.line
                uris.route = pt_infos.uris.route
                uris.commercial_mode = pt_infos.uris.commercial_mode
                uris.physical_mode = pt_infos.uris.physical_mode
                uris.network = pt_infos.uris.network
