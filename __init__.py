"""
    lifx-mycroft: Mycroft interaction for Lifx smart-lights
    Copyright (C) 2018 Sawyer McLane

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

from adapt.intent import IntentBuilder
from mycroft.skills.core import MycroftSkill, intent_handler
from mycroft.util.log import LOG

import lifxlan
import lifxlan.utils
from fuzzywuzzy import fuzz
import webcolors

HUE, SATURATION, BRIGHTNESS, KELVIN = range(4)
MAX_VALUE = 65535
MAX_COLORTEMP = 9000
MIN_COLORTEMP = 2500


class LifxSkillExtended(MycroftSkill):

    def __init__(self):
        super(LifxSkillExtended, self).__init__(name="LifxSkillExtended")

        self.lifxlan = lifxlan.LifxLAN()
        self.targets = {}

    def initialize(self):
        try:
            for light in self.lifxlan.get_lights():
                light = light
                self.targets[light.get_label()] = light
                self.register_vocabulary(light.label, "Target")
                LOG.info("{} was found".format(light.label))
                group_label = light.get_group_label()
                if not (group_label in self.targets.keys()):
                    self.targets[group_label] = self.lifxlan.get_devices_by_group(group_label)
                    self.register_vocabulary(group_label, "Target")
                    LOG.info("Group {} was found".format(group_label))
        except Exception as e:
            self.log.warning("ERROR DISCOVERING LIFX LIGHTS. FUNCTIONALITY MIGHT BE WONKY.\n{}".format(str(e)))
        if len(self.targets.items()) == 0:
            self.log.warn("NO LIGHTS FOUND DURING SEARCH. FUNCTIONALITY MIGHT BE WONKY.")
        for color_name in webcolors.CSS3_HEX_TO_NAMES.values():
            self.register_vocabulary(color_name, "Color")

    @property
    def transition_time_ms(self):
        return int(self.settings.get("transition_time", 1250))

    @staticmethod
    def get_fuzzy_value_from_dict(key, dict_):
        if key is None:
            raise KeyError("Key cannot be None")

        best_score = 0
        best_item = None

        for k, v in dict_.items():
            score = fuzz.ratio(key, k)
            if score > best_score:
                best_score = score
                best_item = v

        if best_item is None:
            raise KeyError("No values matching key {} in dict {{ {} }}".format(str(key), str(dict_)))

        return best_item

    def get_target_from_message(self, message):
        name = message.data["Target"]
        target = self.get_fuzzy_value_from_dict(name, self.targets)

        return target, name

    @intent_handler(IntentBuilder("GoodNightLightsIntent").require("GoodNightAllKeyword"))
    def handle_turn_off_all_intent(self, message):

        for k, v in self.targets:
            v.set_power(False, duration=self.transition_time_ms)

        self.speak_dialog("All lights turned off good night")

    @intent_handler(IntentBuilder("GoodMorningLightsIntent").require("GoodMorningAllKeyword"))
    def handle_turn_on_all_intent(self, message):
        for k, v in self.targets:
            v.set_power(True, duration=self.transition_time_ms)

        self.speak_dialog("All lights turned on good morning")

    @intent_handler(IntentBuilder("").require("Turn").require("All").one_of("Off", "On")
                    .optionally("_TestRunner").build())
    def handle_toggle_all_intent(self, message):
        if "Off" in message.data:
            power_status = False
            status_str = "Turning off all lights"
        elif "On" in message.data:
            power_status = True
            status_str = "Turning on all lights"
        else:
            assert False, "Triggered toggle intent without On/Off keyword."

        for k, v in self.targets:
            v.set_power(power_status, duration=self.transition_time_ms)

        self.speak_dialog(status_str)

    @intent_handler(IntentBuilder("").require("Turn").require("Target").require("On").require("Color")
                    .optionally("_TestRunner").build())
    def handle_color_and_toggle_intent(self, message):
        power_status = False
        status_str = "Off"

        color_str = message.data["Color"]
        rgb = webcolors.name_to_rgb(color_str)
        hsbk = lifxlan.utils.RGBtoHSBK(rgb)

        target, name = self.get_target_from_message(message)

        self.speak_dialog('SwitchAndColor', {'name': name,
                                             'color': color_str,
                                             'status_str': status_str})

        if not message.data.get("_TestRunner"):
            target.set_color(hsbk, duration=self.transition_time_ms)
            target.set_power(power_status, duration=self.transition_time_ms)

        self.set_context("Target", name)


def create_skill():
    return LifxSkillExtended()
