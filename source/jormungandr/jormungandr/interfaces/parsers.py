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
from dateutil import parser
from navitiacommon import parser_args_type

# TODO: to be moved completely into navitiacommon
depth_argument = parser_args_type.depth_argument

float_gt_0 = parser_args_type.float_gt_0

true_false = parser_args_type.true_false

option_value = parser_args_type.option_value

default_count_arg_type = parser_args_type.default_count_arg_type


def parse_input_date(date):
    """
    datetime parse date seems broken, '155' with format '%H%M%S' is not
    rejected but parsed as 1h, 5mn, 5s...
    so use use for the input date parse dateutil even if the 'guess'
    mechanism seems a bit dangerous
    """
    return parser.parse(date, dayfirst=False, yearfirst=True)


def date_time_format(value):
    """
    we want to valid the date format
    """
    try:
        d = parse_input_date(value)
        if d.year < 1970:
            raise ValueError('date is too early!')

        return d
    except ValueError as e:
        raise ValueError("Unable to parse datetime, {}".format(e))


def unsigned_integer(value):
    try:
        d = int(value)
        if d < 0:
            raise ValueError('invalid positive int')

        return d
    except ValueError as e:
        raise ValueError("Unable to evaluate, {}".format(e))


def coord_format(coord):
    """
    Validate coordinates format (lon;lat)
    """
    lon_lat_splitted = coord.split(";")
    if len(lon_lat_splitted) != 2:
        raise ValueError('Invalid coordinate parameter. It must be lon;lat where lon and lat are floats.')

    lon, lat = lon_lat_splitted
    lat = float(lat)
    if not (-90.0 <= lat <= 90.0):
        raise ValueError("lat should be between -90 and 90")
    lon = float(lon)
    if not (180.0 >= lon >= -180.0):
        raise ValueError("lon should be between -180 and 180")

    return coord
