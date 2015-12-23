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
#include "timezone_manager.h"
#include "type.h"
#include "meta_data.h"

namespace navitia {
namespace type {

TimeZoneHandler::TimeZoneHandler(const std::string& name, const MetaData& meta_data,
                                 const dst_periods& offsets_periods):
tz_name(name) {
    for (const auto& utc_shift_and_periods: offsets_periods) {
        ValidityPattern vp(meta_data.production_date.begin());

        auto offset = utc_shift_and_periods.first;
        for (const auto& period: utc_shift_and_periods.second) {
            for (boost::gregorian::day_iterator it(period.begin()); it < period.end(); ++it) {
                vp.add(*it);
            }
        }
        time_changes.push_back({std::move(vp), offset});
    }
}

int16_t TimeZoneHandler::get_utc_offset(boost::gregorian::date day) const {
    for (const auto& vp_shift: time_changes) {
        if (vp_shift.first.check(day)) { return vp_shift.second; }
    }
    // the time_changes should be a partition of the production period, so this should not happen
    throw navitia::recoverable_exception("day " + boost::gregorian::to_iso_string(day) + " not in production period");
}

int16_t TimeZoneHandler::get_utc_offset(int day) const {
    for (const auto& vp_shift: time_changes) {
        if (vp_shift.first.check(day)) { return vp_shift.second; }
    }
    // the time_changes should be a partition of the production period, so this should not happen
    throw navitia::recoverable_exception("day " + std::to_string(day) + " not in production period");
}

int16_t TimeZoneHandler::get_first_utc_offset(const ValidityPattern& vp) const {
    if (vp.days.none()) {
        return 0; // vp is empty, utc shift is not important
    }
    for (const auto& vp_shift: time_changes) {
        // we check if the vj intersect
        if ((vp_shift.first.days & vp.days).any()) { return vp_shift.second; }
    }
    // by construction, this should not be possible
    throw navitia::recoverable_exception("no intersection with a timezone found");
}

TimeZoneHandler::dst_periods TimeZoneHandler::get_periods_and_shift() const {
    dst_periods dst;
    namespace bg = boost::gregorian;
    for (const auto& vp_shift: time_changes) {
        const auto& bitset = vp_shift.first.days;
        const auto& beg_of_period = vp_shift.first.beginning_date;
        std::vector<bg::date_period> periods;
        bg::date last_period_beg;
        for (size_t i = 0; i < bitset.size(); ++i) {
            if (bitset.test(i)) {
                if (last_period_beg.is_not_a_date()) {
                    // begining of a period, we store the date
                    last_period_beg = beg_of_period + bg::days(i);
                }
            } else {
                // if we had a begin, we can add a period
                if (! last_period_beg.is_not_a_date()) {
                    periods.push_back({last_period_beg, beg_of_period + bg::days(i)});
                }
                last_period_beg = bg::date();
            }
        }
        // we add the last build period
        if (! last_period_beg.is_not_a_date()) {
            periods.push_back({last_period_beg, beg_of_period + bg::days(bitset.size())});
        }
        dst[vp_shift.second] = periods;
    }

    return dst;
}

const TimeZoneHandler*
TimeZoneManager::get_or_create(const std::string& name, const MetaData& meta,
                               const std::map<int16_t, std::vector<boost::gregorian::date_period>>& offsets) {
    auto it = tz_handlers.find(name);

    if (it == std::end(tz_handlers)) {
        tz_handlers[name] = std::make_unique<TimeZoneHandler>(name, meta, offsets);
        return tz_handlers[name].get();
    }
    return it->second.get();
}

const TimeZoneHandler* TimeZoneManager::get(const std::string& name) const {
    auto it = tz_handlers.find(name);
    if (it == std::end(tz_handlers)) {
        return nullptr;
    }
    return it->second.get();
}

const TimeZoneHandler* TimeZoneManager::get_first_timezone() const {
    if (tz_handlers.empty()) { return nullptr; }
    return tz_handlers.begin()->second.get();
}
}
}
