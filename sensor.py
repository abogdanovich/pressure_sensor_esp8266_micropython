"""
Pressure Sensor class handle methods that grab, parse and calculate pressure data
from digital pressure sensor.
"""
import machine
import utils
import settings
import utime


class PressureSensor:

    settings_file_name = "settings.txt"
    working_time_file_name = "working_data.txt"

    def __init__(self):
        # data files
        self.uptime = 0 # system uptime in minutes
        self.voltage_step = 0.004887  # 1023 / 5v - voltage_step
        self.low_pressure_value = 4.0  # low pressure level. water accumulator pressure should low_pressure - 10%
        self.high_pressure_value = 5.0  # high pressure - top to turn off relay \ water pump
        self.current_pressure = 0.0  # current one
        self.latest_pressure = 0.0
        self.raw_value = 0

        self.min_raw_value = 100  # min level for sensor - by default it's 130 - less is like error
        # shifting values
        self.pressure_shift_raw = 130  # 0.5v for sensor is output by default
        self.voltage_offset = 0.5

        # pump working seconds|hours|days
        self.working_seconds = 0
        self.working_minutes = 0
        self.working_hours = 0
        self.working_days = 0

        # timer for working seconds
        self.working_timer = 0

        # alert messages
        self.sensor_error = False

        # working status
        self.is_pump_working = False

        # board pins setup
        self.relay = machine.Pin(settings.RELAY, machine.Pin.OUT)
        self.adc = machine.ADC(settings.ADC_PIN)
        self.lcd = utils.i2c_setup()

    def read_settings_from_file(self):
        """Read file settings and set to variables"""
        # return value [low_pressure_value, high_pressure_value]
        try:
            with open(self.settings_file_name, mode="r") as f:
                data = f.read()
        except OSError as e:
            with open(self.settings_file_name, mode="w") as f:
                data = "{}|{}".format(self.low_pressure_value, self.high_pressure_value)
                f.write(data)

        # load values from settings file and update them
        pressure_thresholds = data.split("|")
        self.low_pressure_value = float(pressure_thresholds[0])
        self.high_pressure_value = float(pressure_thresholds[1])

    def read_working_time(self):
        """Read file with stored working minutes|hours|days"""
        try:
            with open(self.working_time_file_name, mode="r") as f:
                data = f.read()
        except OSError as e:
            data = "0|0|0"

        # load values from settings file and update them
        working_data = data.split("|")
        self.working_minutes = int(working_data[0])
        self.working_hours = int(working_data[1])
        self.working_days = int(working_data[2])

    def calc_pump_working_time(self):
        """Count working time and store into file"""
        pump_working_time = None
        save_to_file = False
        current_new_working_seconds = round((utime.ticks_ms() - self.working_timer) / 1000)
        self.working_seconds += current_new_working_seconds
        if self.working_seconds >= 60:
            self.working_minutes += 1
            self.working_seconds = 0
            # let's say that we can update our file to do not miss important update
            save_to_file = True

        if self.working_minutes >= 60:
            self.working_hours += 1
            self.working_minutes = 0

        if self.working_hours >= 24:
            self.working_days += 1
            self.working_hours = 0

        if save_to_file:
            pump_working_time = "{}|{}|{}".format(
                self.working_minutes,
                self.working_hours,
                self.working_days
            )
            self.write_working_time(pump_working_time)
        return pump_working_time

    def write_working_time(self, data):
        """Write working seconds"""
        try:
            with open(self.working_time_file_name, mode="w") as f:
                f.write(data)
        except OSError as e:
            print(e)

    def save_settings(self, data):
        """Save something into file. For example: save settings like low|high value in float format"""
        try:
            with open(self.settings_file_name, mode="w") as f:
                f.write(data)
        except OSError as e:
            with open(self.settings_file_name, mode="w") as f:
                data = "{}|{}".format(self.low_pressure_value, self.high_pressure_value)
                f.write(data)

    def turn_OFF_pump(self):
        self.relay.value(0)

    def turn_ON_pump(self):
        self.relay.value(1)

    def check_sensor_health(self):
        """Extra verification of water pump to safety switch off in any other non working parameters"""
        if self.raw_value <= self.min_raw_value:
            # switch off relay just to be sure that we're safe
            self.sensor_error = True
            self.turn_OFF_pump()
            return False
        return True

    def check_high_pressure_value(self):
        """That method terminates water pump if something goes wrong with other verification method"""
        if self.current_pressure > self.high_pressure_value:
            # if something goes wrong and we have a high pressure - let's stop the whole system
            self.turn_OFF_pump()
            return False
        return True

    def convert_pressure(self):
        """Pressure calculation rules"""
        # formula: Pbar=(VALadc*1/(1023*D)-Offset)*Vbar
        # https://forum.arduino.cc/index.php?topic=568567.0
        pressure_in_voltage = (self.raw_value * self.voltage_step)
        pressure_pascal = (3.0 * (pressure_in_voltage - self.voltage_offset)) * 1000000.0
        current_pressure_value = pressure_pascal / 10e5
        if current_pressure_value < 0.0:
            current_pressure_value = 0.0
        self.current_pressure = round(current_pressure_value, 1)

    def check_relay_with_pressure(self):
        """Check what to do with pressure - turnoff, turnon water pump, etc..."""
        pump_working_time = None
        if self.current_pressure < self.low_pressure_value and not self.is_pump_working:
            self.turn_ON_pump()
            self.is_pump_working = True
            # start working timer
            self.working_timer = utime.ticks_ms()

        if self.current_pressure >= self.high_pressure_value and self.is_pump_working:
            self.turn_OFF_pump()
            self.is_pump_working = False
            pump_working_time = self.calc_pump_working_time()
        return pump_working_time

    def draw_vline(self, x, y, width):
        for i in range(1, width):
            self.lcd.pixel(x, y + i, 1)

    def draw_hline(self, x, y, width):
        for i in range(1, width):
            self.lcd.pixel(x + i, y, 1)

    def update_display(self):
        """Update lcd screen and draw values"""
        msg1 = "{} bar".format(self.high_pressure_value)
        self.lcd.text(msg1, 0, 2)

        msg1 = "{} bar".format(self.current_pressure)
        self.lcd.text(msg1, 0, 12)

        msg1 = "{} bar".format(self.low_pressure_value)
        self.lcd.text(msg1, 0, 22)

        self.draw_vline(58, 0, width=settings.LCD_HEIGHT)
        # draw_hline(0, settings.LCD_HEIGHT-1, width=settings.LCD_WIDTH)

        msg1 = "{}|{}|{}".format(
            self.working_minutes,
            self.working_hours,
            self.working_days
        )
        self.lcd.text(msg1, 60, 2)

        msg1 = "m|h|d"
        self.lcd.text(msg1, 60, 12)

        msg1 = "up {}".format(round(self.uptime / 60, 2))
        self.lcd.text(msg1, 60, 22)

        if self.is_pump_working:
            self.lcd.invert(1)
        else:
            self.lcd.invert(0)

    def get_analog_data(self):
        """Return median for the list of values"""
        raw_data = []
        for i in range(1, 5):
            raw_data.append(self.adc.read())
            utime.sleep_ms(50)
        raw_data.sort()
        self.raw_value = raw_data[round(len(raw_data) / 2)]

    def check_mqtt_special_commands(self, connection):
        if connection.control_data_via_mqtt == 1:
            self.turn_ON_pump()
            connection.control_data_via_mqtt = None
        elif connection.control_data_via_mqtt == 0:
            self.turn_OFF_pump()
            connection.control_data_via_mqtt = None

    def check_mqtt_settings_update(self, connection):
        """Update settings via MQTT channel"""
        data_low_high = connection.pressure_setting_via_mqtt

        if data_low_high != [self.low_pressure_value, self.high_pressure_value] and len(data_low_high) == 2:
            self.low_pressure_value = float(data_low_high[0])
            self.high_pressure_value = float(data_low_high[1])
            self.save_settings("{}|{}".format(self.low_pressure_value, self.high_pressure_value))

    def clear_lcd(self):
        self.lcd.fill(0)

    def save_uptime(self):
        self.uptime += 1

    def is_pressure_updated(self):
        if self.latest_pressure != self.current_pressure:
            self.latest_pressure = self.current_pressure
            return True
        else:
            return False

