#!/usr/bin/env python
# coding=utf-8

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
import logging
import os, sys

"""
    Import in this module should be done as late as possible to prevent side effect with the monkey patching
"""


def load_configuration(app):
    app.config.from_object('jormungandr.default_settings')
    if 'JORMUNGANDR_CONFIG_FILE' in os.environ:
        app.config.from_envvar('JORMUNGANDR_CONFIG_FILE')


def logger(app):
    if 'LOGGER' in app.config:
        logging.config.dictConfig(app.config['LOGGER'])
    else:  # Default is std out
        handler = logging.StreamHandler(stream=sys.stdout)
        app.logger.addHandler(handler)
        app.logger.setLevel('INFO')


def patch_http():
    logger = logging.getLogger(__name__)
    logger.info(
        "Warning! You'are patching socket with gevent, parallel http/https calling by requests is activated"
    )

    from gevent import monkey

    monkey.patch_ssl()
    monkey.patch_socket()
