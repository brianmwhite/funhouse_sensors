import adafruit_funhouse
import wifi
import time
import board
import analogio


mqtt_publish_frequency_in_seconds = 1
sensor_read_frequency_in_seconds = 0.02
low_light_threshold = 400
day_light_threshold = 600

try:
    from secrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")
    raise

print("Connecting to %s" % secrets["ssid"])
wifi.radio.connect(secrets["ssid"], secrets["password"])
print("Connected to %s!" % secrets["ssid"])

mqtt_light_level_topic = secrets["mqtt_lightlevel_topic"]

funhouse = adafruit_funhouse.FunHouse(default_bg=0x0F0F00, scale=2)
photocell = analogio.AnalogIn(board.A0)

# turn off display
funhouse.display.brightness = 0.25

# turn off dotstars
# funhouse.peripherals.dotstars.brightness = 0.0


def mqtt_connected(mqtt_client, userdata, flags, rc):
    print("Connected to MQTT Broker!")
    print("Flags: {0}\n RC: {1}".format(flags, rc))
    print("Subscribing to %s" % mqtt_light_level_topic)
    mqtt_client.subscribe(mqtt_light_level_topic)


def mqtt_disconnected(mqtt_client, userdata, rc):
    # This method is called when the mqtt_client disconnects
    # from the broker.
    print("Disconnected from MQTT Broker!")


def mqtt_subscribed(mqtt_client, userdata, topic, granted_qos):
    # This method is called when the mqtt_client subscribes to a new feed.
    print("Subscribed to {0} with QOS level {1}".format(topic, granted_qos))


def mqtt_unsubscribed(mqtt_client, userdata, topic, pid):
    # This method is called when the mqtt_client unsubscribes from a feed.
    print("Unsubscribed from {0} with PID {1}".format(topic, pid))


def mqtt_published(mqtt_client, userdata, topic, pid):
    # This method is called when the mqtt_client publishes data to a feed.
    # print("Published to {0} with PID {1}".format(topic, pid))
    pass


def mqtt_message_received(client, topic, message):
    # Method called when a client's subscribed feed has a new value.
    # print("New message on topic {0}: {1}".format(topic, message))
    pass


funhouse.network.init_mqtt(broker=secrets["mqtt_broker"], port=secrets["mqtt_port"])

funhouse.network.on_mqtt_connect = mqtt_connected
funhouse.network.on_mqtt_disconnect = mqtt_disconnected
funhouse.network.on_mqtt_subscribe = mqtt_subscribed
funhouse.network.on_mqtt_unsubscribe = mqtt_unsubscribed
funhouse.network.on_mqtt_publish = mqtt_published
funhouse.network.on_mqtt_message = mqtt_message_received

print("Attempting to connect to %s" % secrets["mqtt_broker"])
funhouse.network.mqtt_connect()


last_publish = None
last_read_sensor = None
light_sensor_samples = []


def get_light_sensor_value():
    # return funhouse.peripherals.light
    return photocell.value


last_average_light_level = None
# funhouse.display.show(None)
light_level_label = funhouse.add_text(
    text="l:", text_position=(50, 30), text_color=0x606060
)
last_triggered_status_label = funhouse.add_text(
    text="*", text_position=(50, 50), text_color=0x606060
)

while True:
    try:
        if (
            last_read_sensor is None
            or time.monotonic() > last_read_sensor + sensor_read_frequency_in_seconds
        ):
            light_level = get_light_sensor_value()
            adjusted_light_level = light_level
            light_sensor_samples.append(adjusted_light_level)
            last_read_sensor = time.monotonic()

        if (
            last_publish is None
            or time.monotonic() > last_publish + mqtt_publish_frequency_in_seconds
        ):
            N = len(light_sensor_samples)
            total = sum(light_sensor_samples)
            average_light_level = total / N
            print("%d" % (average_light_level))
            funhouse.set_text("l: %d" % average_light_level, light_level_label)

            if last_average_light_level is None:
                if average_light_level >= day_light_threshold:
                    funhouse.network.mqtt_publish(
                        mqtt_light_level_topic, "OFF", retain=True
                    )
                    print("day light triggered with value %d" % (average_light_level))
                    funhouse.set_text("bright", last_triggered_status_label)

                else:
                    funhouse.network.mqtt_publish(
                        mqtt_light_level_topic, "ON", retain=True
                    )
                    print("low light triggered with value %d" % (average_light_level))
                    funhouse.set_text("low light", last_triggered_status_label)

            elif (
                last_average_light_level >= low_light_threshold
                and average_light_level <= low_light_threshold
            ):
                # turn on low light switch to on
                funhouse.network.mqtt_publish(mqtt_light_level_topic, "ON", retain=True)
                print("low light triggered with value %d" % (average_light_level))
                funhouse.set_text("low light", last_triggered_status_label)
            elif (
                last_average_light_level <= day_light_threshold
                and average_light_level >= day_light_threshold
            ):
                # turn off low light switch
                funhouse.network.mqtt_publish(
                    mqtt_light_level_topic, "OFF", retain=True
                )
                print("day light triggered with value %d" % (average_light_level))
                funhouse.set_text("bright", last_triggered_status_label)

            last_average_light_level = average_light_level

            # delete first half of list
            del light_sensor_samples[: int(N / 2)]
            last_publish = time.monotonic()

        funhouse.network.mqtt_loop(0.5)

    except Exception as e:
        print("Error: ", e)
        time.sleep(5)
        continue
