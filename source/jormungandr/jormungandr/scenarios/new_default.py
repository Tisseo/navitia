# Copyright (c) 2001-2015, Canal TP and/or its affiliates. All rights reserved.
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
from copy import deepcopy
import itertools
import logging
from flask.ext.restful import abort
from jormungandr.scenarios import simple, journey_filter
from jormungandr.scenarios.utils import journey_sorter, change_ids, updated_request_with_default, get_or_default, \
    fill_uris, gen_all_combin, get_pseudo_duration
from navitiacommon import type_pb2, response_pb2, request_pb2
from jormungandr.scenarios.qualifier import min_from_criteria, arrival_crit, departure_crit, \
    duration_crit, transfers_crit, nonTC_crit, trip_carac, has_no_car, has_car, has_pt, \
    has_no_bike, has_bike, has_no_bss, has_bss, non_pt_journey, has_walk, and_filters
import numpy as np
import collections
from jormungandr.utils import date_to_timestamp

SECTION_TYPES_TO_RETAIN = {response_pb2.PUBLIC_TRANSPORT, response_pb2.STREET_NETWORK}
JOURNEY_TYPES_TO_RETAIN = ['best', 'comfort', 'non_pt_walk', 'non_pt_bike', 'non_pt_bss']
STREET_NETWORK_MODE_TO_RETAIN = {response_pb2.Car, response_pb2.Bike, response_pb2.Bss}


def get_kraken_calls(request):
    """
    return a list of tuple (departure fallback mode, arrival fallback mode)
    from the request dict.

    for the moment it's a simple stuff:
    if there is only one elt in {first|last}_section_mode we take those
    else we do the cartesian product and remove forbidden association.

    The good thing to do would be to have API param to be able to better handle this
    """
    dep_modes = request['origin_mode']
    arr_modes = request['destination_mode']

    if len(dep_modes) == len(arr_modes) == 1:
        return [(dep_modes[0], arr_modes[0])]

    # this allowed combination is temporary, it does not handle all the use cases at all
    allowed_combination = [('bss', 'bss'),
                           ('walking', 'walking'),
                           ('bike', 'walking'),
                           ('car', 'walking')]

    res = [c for c in allowed_combination if c in itertools.product(dep_modes, arr_modes)]

    if not res:
        abort(404, message='the asked first_section_mode[] ({}) and last_section_mode[] '
                           '({}) combination is not yet supported'.format(dep_modes, arr_modes))

    return res


def create_pb_request(requested_type, request, dep_mode, arr_mode):
    """Parse the request dict and create the protobuf version"""
    #TODO: bench if the creation of the request each time is expensive
    req = request_pb2.Request()
    req.requested_api = requested_type
    req._current_datetime = date_to_timestamp(request['_current_datetime'])

    if "origin" in request and request["origin"]:
        if requested_type != type_pb2.NMPLANNER:
            origins, durations = ([request["origin"]], [0])
        else:
            # in the n-m query, we have several origin points, with their corresponding access duration
            origins, durations = (request["origin"], request["origin_access_duration"])
        for place, duration in zip(origins, durations):
            location = req.journeys.origin.add()
            location.place = place
            location.access_duration = duration
    if "destination" in request and request["destination"]:
        if requested_type != type_pb2.NMPLANNER:
            destinations, durations = ([request["destination"]], [0])
        else:
            destinations, durations = (request["destination"], request["destination_access_duration"])
        for place, duration in zip(destinations, durations):
            location = req.journeys.destination.add()
            location.place = place
            location.access_duration = duration

    req.journeys.datetimes.append(request["datetime"])  #TODO remove this datetime list completly in another PR

    req.journeys.clockwise = request["clockwise"]
    sn_params = req.journeys.streetnetwork_params
    sn_params.max_walking_duration_to_pt = request["max_walking_duration_to_pt"]
    sn_params.max_bike_duration_to_pt = request["max_bike_duration_to_pt"]
    sn_params.max_bss_duration_to_pt = request["max_bss_duration_to_pt"]
    sn_params.max_car_duration_to_pt = request["max_car_duration_to_pt"]
    sn_params.walking_speed = request["walking_speed"]
    sn_params.bike_speed = request["bike_speed"]
    sn_params.car_speed = request["car_speed"]
    sn_params.bss_speed = request["bss_speed"]
    sn_params.origin_filter = request.get("origin_filter", "")
    sn_params.destination_filter = request.get("destination_filter", "")
    #we always want direct path, even for car
    sn_params.enable_direct_path = True

    #settings fallback modes
    sn_params.origin_mode = dep_mode
    sn_params.destination_mode = arr_mode

    req.journeys.max_duration = request["max_duration"]
    req.journeys.max_transfers = request["max_transfers"]
    if request["max_extra_second_pass"]:
        req.journeys.max_extra_second_pass = request["max_extra_second_pass"]
    req.journeys.wheelchair = request["wheelchair"] or False  # default value is no wheelchair
    if request['data_freshness'] == 'realtime':
        req.journeys.realtime_level = type_pb2.REALTIME
    elif request['data_freshness'] == 'adapted_schedule':
        req.journeys.realtime_level = type_pb2.ADAPTED_SCHEDULE
    else:
        req.journeys.realtime_level = type_pb2.BASE_SCHEDULE

    if "details" in request and request["details"]:
        req.journeys.details = request["details"]

    req.journeys.walking_transfer_penalty = request['_walking_transfer_penalty']

    for forbidden_uri in get_or_default(request, "forbidden_uris[]", []):
        req.journeys.forbidden_uris.append(forbidden_uri)

    return req


def _has_pt(j):
    return any(s.type == response_pb2.PUBLIC_TRANSPORT for s in j.sections)


def sort_journeys(resp, journey_order, clockwise):
    if resp.journeys:
        resp.journeys.sort(journey_sorter[journey_order](clockwise=clockwise))


def tag_journeys(resp):
    """
    qualify the journeys
    """
    pass


def _get_section_id(section):
    street_network_mode = None
    if section.type in SECTION_TYPES_TO_RETAIN:
        if getattr(section.street_network, 'mode', None) in STREET_NETWORK_MODE_TO_RETAIN:
            street_network_mode = section.street_network.mode
    return section.uris.line, street_network_mode, section.type


def _build_candidate_pool_and_sections_set(resp):
    sections_set = set()
    candidates_pool = list()
    idx_of_jrny_must_keep = list()

    for (i, jrny) in enumerate(resp.journeys):
        if jrny.type in JOURNEY_TYPES_TO_RETAIN:
            idx_of_jrny_must_keep.append(i)
        sections_set |= set([_get_section_id(s) for s in jrny.sections if s.type in SECTION_TYPES_TO_RETAIN])
        candidates_pool.append(jrny)

    return np.array(candidates_pool), sections_set, idx_of_jrny_must_keep


def _build_selected_sections_matrix(sections_set, candidates_pool):
    sections_2_index_dict = dict()
    for index, value in enumerate(sections_set):
        sections_2_index_dict[value] = index
    selected_sections_matrix = list()
    nb_sections = len(sections_set)

    for j in candidates_pool:
        section_select = np.zeros(nb_sections, dtype=int)

        def _gen_section_ind():
            for s in j.sections:
                ind = sections_2_index_dict.get(_get_section_id(s))
                if ind is not None:
                    yield ind
        selected_indexes = list(_gen_section_ind())
        section_select[selected_indexes] = 1
        selected_sections_matrix.append(section_select)
    return np.array(selected_sections_matrix)


def _get_sorted_solutions_indexes(selected_sections_matrix, nb_journeys_to_find, idx_of_jrny_must_keep):
    """
    The entry is a 2D array where its lines are journeys, its columns are (non) chosen sections
    """
    logger = logging.getLogger(__name__)
    """
    Get a matrix which illustrate all possible non ordered combinations of t elements from n elements where n >= t with
    their indexes.

    Let's say we'd like to find all combinations of 2 elements from a set of 3.

    selected_journeys_matrix will be like:

    [[0,1]
     [0,2]
     [1,2]]
    """
    selected_journeys_matrix = np.array(list(gen_all_combin(selected_sections_matrix.shape[0], nb_journeys_to_find)))

    """
    We should cut out those combinations that don't contain must-keep journeys
    """
    def _contains(idx_selected_jrny):
        return set(idx_selected_jrny).issuperset(idx_of_jrny_must_keep)

    selected_journeys_matrix = selected_journeys_matrix[np.apply_along_axis(_contains, 1, selected_journeys_matrix)]

    selection_matrix = np.zeros((selected_journeys_matrix.shape[0], selected_sections_matrix.shape[0]))

    """
    Given  selected_journeys_matrix:
    [[0,1]
     [0,2]
     [1,2]]

    selection_matrix will be like:
    [[1,1,0], -> the first one and the second are chosen, etc...
     [1,0,1],
     [0,1,1]]
    """
    # http://stackoverflow.com/questions/20103779/index-2d-numpy-array-by-a-2d-array-of-indices-without-loops
    selection_matrix[np.arange(selected_journeys_matrix.shape[0])[:, None], selected_journeys_matrix] = 1

    res_pool = np.dot(selection_matrix, selected_sections_matrix)

    """
    Get number of sections(or tranfers) for every solution
    """
    nb_sections = np.sum(res_pool, axis=1)

    """
    integrity shows at which point a solution(chosen journeys) covers sections.
    0 means a solution covers all sections
    1 means a solutions covers almost all sections but 1 is missing
    2 means 2 sections are missing
    .... etc
    """
    integrity = res_pool.shape[1] - np.array([np.count_nonzero(r) for r in res_pool])

    """
    We want to find the solutions covers as many sections as possible which has less sections(less transfer to do)
    """
    the_best_idx = np.lexsort((nb_sections, integrity))[0]  # sort by integrity then by nb_sections

    best_indexes = np.where(np.logical_and(nb_sections == nb_sections[the_best_idx],
                                           integrity == integrity[the_best_idx]))[0]

    logger.debug("Best Itegrity: {0}".format(integrity[the_best_idx]))
    logger.debug("Best Nb sections: {0}".format(nb_sections[the_best_idx]))

    return best_indexes, selection_matrix


def culling_journeys(resp, request):
    """
    Remove some journeys if there are too many of them to have max_nb_journeys journeys.
    
    resp.journeys should be sorted before this function is called

    The goal is to choose a bunch of journeys(max_nv_journeys) that covers as many as possible sections
    but have as few as possible sum(sections)

    Ex:

    From:

    Journey_1 : Line 1 -> Line 8 -> Bus 172
    Journey_2 : Line 14 -> Line 6 -> Bus 165
    Journey_3 : Line 14 -> Line 6 ->Line 8 -> Bus 165

    W'd like to choose two journeys. The algo will return Journey_1 and Journey2.

    Because
    With Journey_1 and Journey_3, they cover all lines but have 5 transfers in all
    With Journey_2 and Journey_3, they don't cover all lines(Line 1 is missing) and have 5 transfers in all

    With Journey_1 and Journey_2, they cover all lines and have only 4 transfers in all -> OK

    No removing done in debug
    """
    logger = logging.getLogger(__name__)

    if not request["max_nb_journeys"] or request["max_nb_journeys"] >= len(resp.journeys):
        logger.debug('No need to cull journeys')
        return

    logger.debug('Trying to culling the journeys')

    """
    To create a candidates pool, we choose only journeys that are NOT tagged as 'comfort' and 'best' and we create a
    section set from that pool

    Ex:
    Journey_1 (Best): Line 14 -> Line 8 -> Bus 172
    Journey_2 : Line 14 -> Line 6 -> Bus 165
    Journey_3 : Line 14 -> Line 8 -> Bus 165

    The candidate pool will be like [Journey_2, Journey_3]
    The sections set will be like set([Line 14, Line 6, Line 8, Bus 165])
    """
    candidates_pool, sections_set, idx_of_jrnys_must_keep = _build_candidate_pool_and_sections_set(resp)

    nb_journeys_must_have = len(idx_of_jrnys_must_keep)
    logger.debug("There are {0} journeys we must keep".format(nb_journeys_must_have))
    if (request["max_nb_journeys"] - nb_journeys_must_have) <= 0:
        # At this point, max_nb_journeys is smaller than nb_journeys_must_have, we have to make choices

        def _inverse_selection(d, indexes):
            select = np.in1d(range(d.shape[0]), indexes)
            return d[~select]

        # Here we mark all journeys as dead that are not must-have
        for jrny in _inverse_selection(candidates_pool, idx_of_jrnys_must_keep):
             journey_filter.mark_as_dead(jrny, 'Filtered by max_nb_journeys')

        if request["max_nb_journeys"] == nb_journeys_must_have:
            logger.debug('max_nb_journeys equals to nb_journeys_must_have')
            journey_filter.delete_journeys((resp,), request)
            return

        logger.debug('max_nb_journeys:{0} is smaller than nb_journeys_must_have:{1}'
                     .format(request["max_nb_journeys"], nb_journeys_must_have))

        # At this point, resp.journeys should contain only must-have journeys
        list_dict = collections.defaultdict(list)
        for jrny in resp.journeys:
            if 'to_delete' not in jrny.tags:
                list_dict[jrny.type].append(jrny)

        sorted_by_type_journeys = []
        for t in JOURNEY_TYPES_TO_RETAIN:
            sorted_by_type_journeys.extend(list_dict.get(t, []))

        for jrny in sorted_by_type_journeys[request["max_nb_journeys"]:]:
            journey_filter.mark_as_dead(jrny, 'Filtered by max_nb_journeys')

        journey_filter.delete_journeys((resp,), request)
        return

    nb_journeys_to_find = request["max_nb_journeys"]
    logger.debug('Trying to find {0} journeys from {1}'.format(nb_journeys_to_find,
                                                               candidates_pool.shape[0]))

    """
    Ex:
    Journey_2 : Line 14 -> Line 6 -> Bus 165
    Journey_3 : Line 14 -> Line 8 -> Bus 165

    The candidate pool will be like [Journey_2, Journey_3]
    The sections set will be like set([Line 14, Line 6, Line 8, Bus 165])

    selected_sections_matrix:
    [[1,1,0,1] -> journey_2
     [1,0,1,1] -> journey_3
    ]
    """
    selected_sections_matrix = _build_selected_sections_matrix(sections_set, candidates_pool)

    best_indexes, selection_matrix = _get_sorted_solutions_indexes(selected_sections_matrix,
                                                                   nb_journeys_to_find,
                                                                   idx_of_jrnys_must_keep)

    logger.debug("Nb best solutions: {0}".format(best_indexes.shape[0]))

    the_best_index = best_indexes[0]

    logger.debug("Trying to find the best of best")
    """
    Let's find the best of best :)
    """
    # If there're several solutions which have the same score of integrity and nb_sections
    if best_indexes.shape[0] != 1:
        requested_dt = request['datetime']
        is_clockwise = request.get('clockwise', True)

        def combinations_sorter(v):
            # Hoping to find We sort the solution by the sum of journeys' pseudo duration
            return np.sum((get_pseudo_duration(jrny, requested_dt, is_clockwise)
                           for jrny in np.array(candidates_pool)[np.where(selection_matrix[v, :])]))
        the_best_index = min(best_indexes, key=combinations_sorter)

    logger.debug('Removing non selected journeys')
    for jrny in candidates_pool[np.where(selection_matrix[the_best_index, :] == 0)]:
        journey_filter.mark_as_dead(jrny, 'Filtered by max_nb_journeys')

    journey_filter.delete_journeys((resp,), request)


def nb_journeys(responses):
    return sum(len(r.journeys) for r in responses)


def type_journeys(resp, req):
    """
    Set the type of the journeys
    """
    best_crit = arrival_crit if req["clockwise"] else departure_crit
    # first, we want a type for every journey. Just pick "rapid" by default.
    for j in resp.journeys:
        j.type = "rapid"

    # Then, we want something like the old types
    trip_caracs = [
        # comfort tends to limit the number of transfers and fallback
        ("comfort", trip_carac([
            has_no_car,
        ], [
            transfers_crit,
            nonTC_crit,
            best_crit,
            duration_crit
        ])),
        # for car we want at most one journey, the earliest one
        ("car", trip_carac([
            has_car,
            has_pt,  # We don't want car only solution, we MUST have PT
        ], [
            best_crit,
            transfers_crit,
            nonTC_crit,
            duration_crit
        ])),
        # less_fallback tends to limit the fallback while walking
        ("less_fallback_walk", trip_carac([
            has_no_car,
            has_no_bike,
        ], [
            nonTC_crit,
            transfers_crit,
            duration_crit,
            best_crit,
        ])),
        # less_fallback tends to limit the fallback for biking and bss
        ("less_fallback_bike", trip_carac([
            has_no_car,
            has_bike,
            has_no_bss,
        ], [
            nonTC_crit,
            transfers_crit,
            duration_crit,
            best_crit,
        ])),
        # less_fallback tends to limit the fallback for biking and bss
        ("less_fallback_bss", trip_carac([
            has_no_car,
            has_bss,
        ], [
            nonTC_crit,
            transfers_crit,
            duration_crit,
            best_crit,
        ])),
        # the fastest is quite explicit
        ("fastest", trip_carac([
            has_no_car,
        ], [
            duration_crit,
            transfers_crit,
            nonTC_crit,
            best_crit,
        ])),
        # the non_pt journeys is the earliest journey without any public transport
        ("non_pt_walk", trip_carac([
            non_pt_journey,
            has_no_car,
            has_walk
        ], [
            best_crit
        ])),
        # the non_pt journey is the earliest journey without any public transport
        # only walking, biking or driving
        ("non_pt_bike", trip_carac([
            non_pt_journey,
            has_no_car,
            has_bike
        ], [
            best_crit
        ])),
        ("non_pt_bss", trip_carac([
            non_pt_journey,
            has_no_car,
            has_bss,
        ], [
            best_crit
        ])),
        ("non_pt_car", trip_carac([
            non_pt_journey,
            has_car,
        ], [
            best_crit
        ])),
    ]

    for name, carac in trip_caracs:
        sublist = filter(and_filters(carac.constraints), resp.journeys)
        best = min_from_criteria(sublist, carac.criteria)
        if best is not None:
            best.type = name

    # Finally, we want exactly one best, the ASAP one
    best = min_from_criteria(resp.journeys, [best_crit, duration_crit, transfers_crit, nonTC_crit])
    if best is not None:
        best.type = "best"


def merge_responses(responses):
    """
    Merge all responses in one protobuf response
    """
    merged_response = response_pb2.Response()

    for r in responses:
        if r.HasField(b'error') or not r.journeys:
            # we do not take responses with error, but if all responses have errors, we'll aggregate them
            continue

        change_ids(r, len(merged_response.journeys))

        # we don't want to add a journey already there
        merged_response.journeys.extend(r.journeys)

        # we have to add the additional fares too
        # if at least one journey has the ticket we add it
        tickets_to_add = set(t for j in r.journeys for t in j.fare.ticket_id)
        merged_response.tickets.extend([t for t in r.tickets if t.id in tickets_to_add])

        initial_feed_publishers = {}
        for fp in merged_response.feed_publishers:
            initial_feed_publishers[fp.id] = fp
        merged_response.feed_publishers.extend([fp for fp in r.feed_publishers if fp.id not in initial_feed_publishers])

        # handle impacts
        for i in r.impacts:
            if any(other.uri == i.uri for other in merged_response.impacts):
                continue
            merged_response.impacts.extend([i])

    if not merged_response.journeys:
        # we aggregate the errors found

        errors = {r.error.id: r.error for r in responses if r.HasField(b'error')}
        if len(errors) == 1:
            merged_response.error.id = errors.values()[0].id
            merged_response.error.message = errors.values()[0].message
        else:
            # we need to merge the errors
            merged_response.error.id = response_pb2.Error.no_solution
            merged_response.error.message = "several errors occured: \n * {}"\
                .format("\n * ".join([m.message for m in errors.values()]))

    return merged_response


class Scenario(simple.Scenario):
    """
    TODO: a bit of explanation about the new scenario
    """

    def __init__(self):
        super(Scenario, self).__init__()
        self.nb_kraken_calls = 0

    def fill_journeys(self, request_type, api_request, instance):

        krakens_call = get_kraken_calls(api_request)

        request = deepcopy(api_request)
        min_asked_journeys = get_or_default(request, 'min_nb_journeys', 1)
        min_journeys_calls = get_or_default(request, '_min_journeys_calls', 1)

        responses = []
        nb_try = 0
        while request is not None and \
                ((nb_journeys(responses) < min_asked_journeys and nb_try < min_asked_journeys)
                 or nb_try < min_journeys_calls):
            nb_try = nb_try + 1

            tmp_resp = self.call_kraken(request_type, request, instance, krakens_call)
            responses.extend(tmp_resp)  # we keep the error for building the response
            if nb_journeys(tmp_resp) == 0:
                # no new journeys found, we stop
                break

            request = self.create_next_kraken_request(request, tmp_resp)

            # we filter unwanted journeys by side effects
            journey_filter.filter_journeys(responses, instance, api_request)

        journey_filter.final_filter_journeys(responses, instance, api_request)
        pb_resp = merge_responses(responses)

        sort_journeys(pb_resp, instance.journey_order, api_request['clockwise'])
        tag_journeys(pb_resp)
        type_journeys(pb_resp, api_request)
        culling_journeys(pb_resp, api_request)

        self._compute_pagination_links(pb_resp, instance)

        return pb_resp

    def call_kraken(self, request_type, request, instance, krakens_call):
        """
        For all krakens_call, call the kraken and aggregate the responses

        return the list of all responses
        """
        # TODO: handle min_alternative_journeys
        # TODO: call first bss|bss and do not call walking|walking if no bss in first results

        resp = []
        logger = logging.getLogger(__name__)
        for dep_mode, arr_mode in krakens_call:
            pb_request = create_pb_request(request_type, request, dep_mode, arr_mode)
            self.nb_kraken_calls += 1

            local_resp = instance.send_and_receive(pb_request)

            # for log purpose we put and id in each journeys
            for idx, j in enumerate(local_resp.journeys):
                j.internal_id = "{resp}-{j}".format(resp=self.nb_kraken_calls, j=idx)

            resp.append(local_resp)
            logger.debug("for mode %s|%s we have found %s journeys", dep_mode, arr_mode, len(local_resp.journeys))

        for r in resp:
            fill_uris(r)
        return resp

    def __on_journeys(self, requested_type, request, instance):
        updated_request_with_default(request, instance)

        # call to kraken
        resp = self.fill_journeys(requested_type, request, instance)
        return resp

    def journeys(self, request, instance):
        return self.__on_journeys(type_pb2.PLANNER, request, instance)

    def isochrone(self, request, instance):
        updated_request_with_default(request, instance)
        #we don't want to filter anything!
        krakens_call = get_kraken_calls(request)
        resp = merge_responses(self.call_kraken(type_pb2.ISOCHRONE, request, instance, krakens_call))
        if not request['debug']:
            # on isochrone we can filter the number of max journeys
            if request["max_nb_journeys"] and len(resp.journeys) > request["max_nb_journeys"]:
                del resp.journeys[request["max_nb_journeys"]:]

        return resp

    def create_next_kraken_request(self, request, responses):
        """
        modify the request to call the next (resp previous for non clockwise search) journeys in kraken

        to do that we find ask the next (resp previous) query datetime
        """
        if request["clockwise"]:
            request['datetime'] = self.next_journey_datetime([j for r in responses for j in r.journeys])
        else:
            request['datetime'] = self.previous_journey_datetime([j for r in responses for j in r.journeys])

        if request['datetime'] is None:
            return None

        #TODO forbid ODTs
        return request

    @staticmethod
    def __get_best_for_criteria(journeys, criteria):
        return min_from_criteria(filter(has_pt, journeys),
                                 [criteria, duration_crit, transfers_crit, nonTC_crit])

    def next_journey_datetime(self, journeys):
        """
        to get the next journey, we add one second to the departure of the 'best found' journey
        """
        best = self.__get_best_for_criteria(journeys, arrival_crit)
        if best is None:
            return None

        one_second = 1
        return best.departure_date_time + one_second

    def previous_journey_datetime(self, journeys):
        """
        to get the next journey, we add one second to the arrival of the 'best found' journey
        """
        best = self.__get_best_for_criteria(journeys, departure_crit)
        if best is None:
            return None

        one_second = 1
        return best.arrival_date_time - one_second
