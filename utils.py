"""
Utility to setup some environment
"""
import time
import utime
import machine
import network
import urandom
import ssd1306
from umqtt_simple import MQTTClient
import settings


class Connection:
    """Handle MQTT and WIFI connections"""

    def __init__(self):
        self.control_data_via_mqtt = None
        self.pressure_setting_via_mqtt = []
        self.wlan = network.WLAN(network.STA_IF)
        self.mqtt_client = None
        self.ping_broker_ms = 0

    def wifi_setup(self):
        """run WIFI module and connect to wifi router"""
        try:
            if not self.wlan.isconnected():
                print("Setup wifi connection...")
                self.wlan.active(True)
                self.wlan.connect(settings.WIFI_SSID, settings.WIFI_PASSWORD)
        except OSError as e:
            print("WIFI setup Exception: {}".format(e))

    def check_wifi_connection(self):
        """check that wifi is connected"""
        if not self.wlan.isconnected():
            self.wifi_setup()
            return False
        else:
            return True

    def mqtt_setup_callback(self, topic, msg):
        """setup callback for income messages"""
        if topic.decode() == settings.MQTT_SERVER_INFO_SETTINGS:
            data = msg.decode().split("|")
            if len(data) == 2 and float(data[0]) > 0.0 and float(data[1]) > 0.0:
                self.pressure_setting_via_mqtt = data

        elif topic.decode() == settings.MQTT_SERVER_INFO_CONTROL:
            # 1 - on - 0 - off
            data = msg.decode()
            if int(data) is not None:
                self.control_data_via_mqtt = int(data)

    def mqtt_setup(self):
        """setup MQTT bridge"""
        try:
            self.mqtt_client = MQTTClient(
                settings.MQTT_CLIENT_ID,
                settings.MQTT_SERVER_URL,
                port=settings.MQTT_SERVER_PORT,
                user=settings.MQTT_SERVER_USERNAME,
                password=settings.MQTT_SERVER_USERPASSWORD,
            )
            self.mqtt_client.set_callback(self.mqtt_setup_callback)
            self.mqtt_client.connect()
            self.publish_data(
                settings.MQTT_SERVER_INFO_TOPIC,
                "working"
            )

            self.mqtt_client.subscribe(settings.MQTT_SERVER_INFO_CONTROL)  # topic to control relay
            self.mqtt_client.subscribe(settings.MQTT_SERVER_INFO_SETTINGS)  # topic for income settings low|high values
        except OSError as e:
            self.mqtt_client = None
            print("MQTT Exception setup: {}".format(e))

    def check_mqtt_updates(self):
        """Check mqtt channel command, updates, control commands"""
        # check mqtt messages
        self.mqtt_client.check_msg()

    def publish_data(self, topic, message):
        """Send message to mqtt"""
        # and send data to mqtt broker in case if we have a new value only
        if self.mqtt_client:
            self.mqtt_client.publish(topic, message, retain=True)


# Other small utils methods
def i2c_setup():
    """setup i2c interface"""
    i2c = machine.I2C(-1, scl=machine.Pin(settings.I2C_SCL), sda=machine.Pin(settings.I2C_SDA))
    lcd = ssd1306.SSD1306_I2C(settings.LCD_WIDTH, settings.LCD_HEIGHT, i2c)
    lcd.fill(0)  # clear screen
    lcd.text('lcd init!', (int(settings.LCD_WIDTH / 2)) - 30, int(settings.LCD_HEIGHT / 2))
    lcd.show()
    utime.sleep_ms(200)
    return lcd


def adc_setup():
    adc = machine.ADC(settings.ADC_PIN)
    return adc


def adc_read_data(adc):
    return adc.read()


def module_reset():
    time.sleep(1)
    machine.reset()


def randint(min, max):
    val = 0
    try:
        span = max - min + 1
        div = 0x3fffffff // span
        offset = urandom.getrandbits(30) // div
        val = min + offset
    except OSError as e:
        print("generate number error: {}".format(e))
    return val
