"""
Mechanical relay is replaced with esp8266 + SSD relay + micro-python logic
Using mqtt broker we send the data via data protocol and can see what we have
# Available pins are: 0, 1, 2, 3, 4, 5, 12, 13, 14, 15, 16, which correspond to
the actual GPIO pin numbers of ESP8266 controller
@author: Alex Bogdanovich bogdanovich.alex@gmail.com
"""
from sensor import PressureSensor
import utime
import utils
import settings


def uptime_save_and_send(sensor, connection):
    sensor.save_uptime()
    if connection.mqtt_client:
        try:
            uptime = "uptime\n{}".format(round(sensor.uptime / 60, 2))
            connection.publish_data(
                settings.MQTT_SERVER_INFO_TOPIC,
                uptime
            )
        except OSError as e:
            connection.mqtt_client = None
            print("Exception during sending MQTT data {}".format(e))


def check_wifi_and_mqtt(connection):
    connection.wifi_setup()
    if not connection.mqtt_client:
        print("Setup mqtt connection...")
        connection.mqtt_setup()


def send_data_via_mqtt(sensor, connection):
    if connection.mqtt_client:
        try:
            connection.check_mqtt_updates()

            if sensor.is_pressure_updated():
                connection.publish_data(
                    settings.MQTT_SERVER_DATA_TOPIC,
                    "{} bar".format(sensor.current_pressure)
                )
            working_pump_time = sensor.check_relay_with_pressure()
            if working_pump_time:
                connection.publish_data(
                    settings.MQTT_SERVER_INFO_WORKING_TIME,
                    working_pump_time
                )
        except OSError as e:
            connection.mqtt_client = None
            print("Exception during sending MQTT data {}".format(e))


def take_pressure_and_decide_what_to_do(sensor, connection):
    sensor.clear_lcd()

    if connection.mqtt_client:
        sensor.check_mqtt_special_commands(connection)
        sensor.check_mqtt_settings_update(connection)

    # read sensor analog data
    sensor.get_analog_data()
    # extra verification for high pressure outside of system error status
    sensor.check_high_pressure_value()
    sensor.check_sensor_health()

    if sensor.sensor_error:
        # something is wrong - need to inform and turn off pump
        display_message = "Error pressure!"
        sensor.lcd.text(display_message, 0, round(settings.LCD_HEIGHT / 2))
        # mark system error
        sensor.sensor_error = True

        try:
            if connection.mqtt_client:
                connection.publish_data(
                    settings.MQTT_SERVER_INFO_TOPIC,
                    display_message
                )
        except OSError as e:
            connection.mqtt_client = None
            print("Exception during sending MQTT data {}".format(e))

    else:
        # calculate pressure value
        sensor.convert_pressure()
        # check what to do with pump
        # todo remove it
        sensor.current_pressure = float(utils.randint(3, 6))
        # draw lcd value
        sensor.update_display()

    sensor.lcd.show()


def main():
    """Main method with loop"""
    sensor = PressureSensor()
    connection = utils.Connection()

    # read working time from file
    sensor.read_working_time()
    # load low and high pressure values
    sensor.read_settings_from_file()

    # timer ticks
    timer_pressure = utime.ticks_ms()
    system_uptime = utime.ticks_ms()
    check_mqtt = utime.ticks_ms()
    mqtt_time = utime.ticks_ms()

    try:
        connection.check_wifi_connection()
        connection.mqtt_setup()
    except OSError as e:
        print("OSError during wifi and mqtt setup: {}".format(e))

    while True:
        try:
            if utime.ticks_ms() - system_uptime > 60000:
                system_uptime = utime.ticks_ms()
                uptime_save_and_send(sensor, connection)

            if utime.ticks_ms() - check_mqtt > 5000:
                check_mqtt = utime.ticks_ms()
                check_wifi_and_mqtt(connection)

            if utime.ticks_ms() - mqtt_time > 2000:
                mqtt_time = utime.ticks_ms()
                send_data_via_mqtt(sensor, connection)

            if utime.ticks_ms() - timer_pressure > 200:
                timer_pressure = utime.ticks_ms()
                take_pressure_and_decide_what_to_do(sensor, connection)

        except OSError as e:
            utils.module_reset()


if __name__ == '__main__':
    main()
