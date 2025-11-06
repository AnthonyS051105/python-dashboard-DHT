from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
import random
import threading
import time
import os
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
socketio = SocketIO(app, cors_allowed_origins="*")

# In-memory sensor values and led state.
state = {
    'temperature': 24.0,
    'humidity': 55.0,
    'led': False,
    'last_update': None,
}

# MQTT configuration (override with env vars if needed)
MQTT_BROKER = os.getenv('MQTT_BROKER', 'localhost')
MQTT_PORT = int(os.getenv('MQTT_PORT', '1883'))
MQTT_TOPIC_SENSOR = os.getenv('MQTT_TOPIC_SENSOR', 'sensors/dht')
MQTT_TOPIC_LED_STATE = os.getenv('MQTT_TOPIC_LED_STATE', 'sensors/led/state')
MQTT_TOPIC_LED_CMD = os.getenv('MQTT_TOPIC_LED_CMD', 'sensors/led/cmd')
USE_MQTT = os.getenv('USE_MQTT', '1') != '0'

# MQTT client (optional)
mqtt_client = None


def sensor_simulator():
    """Background thread to slightly vary simulated sensor values (fallback)."""
    while True:
        state['temperature'] += random.uniform(-0.3, 0.3)
        state['humidity'] += random.uniform(-1.0, 1.0)
        state['temperature'] = max(-10, min(60, state['temperature']))
        state['humidity'] = max(0, min(100, state['humidity']))
        state['last_update'] = time.time()
        
        # Emit data via WebSocket
        socketio.emit('sensor_update', {
            'temperature': round(state['temperature'], 2),
            'humidity': round(state['humidity'], 2),
            'led': bool(state['led']),
            'last_update': state['last_update'],
        })
        
        time.sleep(2)


def try_setup_mqtt():
    """Try to import and setup MQTT client. Returns client or None."""
    global mqtt_client
    try:
        import paho.mqtt.client as mqtt
    except Exception as e:
        print('paho-mqtt not installed or failed to import:', e)
        return None

    client = mqtt.Client()

    def on_connect(client, userdata, flags, rc):
        print('MQTT connected with result code', rc)
        # subscribe to topics
        try:
            client.subscribe(MQTT_TOPIC_SENSOR)
            client.subscribe(MQTT_TOPIC_LED_STATE)
            print('Subscribed to', MQTT_TOPIC_SENSOR, 'and', MQTT_TOPIC_LED_STATE)
        except Exception as ex:
            print('Subscribe failed:', ex)

    def on_message(client, userdata, msg):
        try:
            payload = msg.payload.decode('utf-8')
            topic = msg.topic
            # Try parse JSON first
            try:
                data = json.loads(payload)
            except Exception:
                data = None

            if topic == MQTT_TOPIC_SENSOR:
                # payload may be JSON {"temperature":.., "humidity":..}
                if isinstance(data, dict):
                    if 'temperature' in data:
                        state['temperature'] = float(data['temperature'])
                    if 'humidity' in data:
                        state['humidity'] = float(data['humidity'])
                else:
                    # try simple CSV: "24.5,55"
                    parts = payload.split(',')
                    if len(parts) >= 2:
                        try:
                            state['temperature'] = float(parts[0])
                            state['humidity'] = float(parts[1])
                        except Exception:
                            pass
                state['last_update'] = time.time()
                
                # Emit data via WebSocket ketika menerima dari MQTT
                socketio.emit('sensor_update', {
                    'temperature': round(state['temperature'], 2),
                    'humidity': round(state['humidity'], 2),
                    'led': bool(state['led']),
                    'last_update': state['last_update'],
                })
                
            elif topic == MQTT_TOPIC_LED_STATE:
                # payload could be JSON {"led":true} or plain 'ON'/'OFF' or '1'/'0'
                if isinstance(data, dict) and 'led' in data:
                    state['led'] = bool(data['led'])
                else:
                    up = payload.strip().lower()
                    if up in ('on', '1', 'true', 'yes'):
                        state['led'] = True
                    elif up in ('off', '0', 'false', 'no'):
                        state['led'] = False
                state['last_update'] = time.time()
                
                # Emit LED status via WebSocket
                socketio.emit('led_update', {
                    'led': bool(state['led']),
                    'last_update': state['last_update'],
                })
        except Exception as e:
            print('Error handling MQTT message:', e)

    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        client.loop_start()
        mqtt_client = client
        return client
    except Exception as e:
        print('Failed to connect to MQTT broker at', MQTT_BROKER, MQTT_PORT, '-', e)
        return None


@app.route('/')
def home():
    return render_template('home.html')


@app.route('/api/data')
def api_data():
    # Return current readings
    return jsonify({
        'temperature': round(state['temperature'], 2),
        'humidity': round(state['humidity'], 2),
        'led': bool(state['led']),
        'last_update': state['last_update'],
    })


def mqtt_publish_led(cmd_payload):
    """Publish LED command via MQTT if available; otherwise update state locally."""
    global mqtt_client
    if mqtt_client:
        try:
            mqtt_client.publish(MQTT_TOPIC_LED_CMD, cmd_payload)
            return True
        except Exception as e:
            print('MQTT publish failed:', e)
            return False
    else:
        # fallback: change state locally
        state['led'] = (str(cmd_payload).strip().lower() in ('on', '1', 'true', 'yes'))
        state['last_update'] = time.time()
        return False


@app.route('/api/led/on', methods=['POST'])
def led_on():
    sent = mqtt_publish_led('ON')
    # Emit update via WebSocket
    socketio.emit('led_update', {
        'led': True,
        'last_update': state['last_update'],
    })
    return jsonify({'result': 'ok', 'led': True, 'sent_via_mqtt': bool(sent)})


@app.route('/api/led/off', methods=['POST'])
def led_off():
    sent = mqtt_publish_led('OFF')
    # Emit update via WebSocket
    socketio.emit('led_update', {
        'led': False,
        'last_update': state['last_update'],
    })
    return jsonify({'result': 'ok', 'led': False, 'sent_via_mqtt': bool(sent)})


if __name__ == '__main__':
    # Try to set up MQTT (if disabled via env or missing, fall back to simulator)
    started_mqtt = False
    if USE_MQTT:
        client = try_setup_mqtt()
        if client:
            print('MQTT client running, using broker:', MQTT_BROKER)
            started_mqtt = True
    if not started_mqtt:
        print('Using local sensor simulator (MQTT disabled or broker not available).')
        t = threading.Thread(target=sensor_simulator, daemon=True)
        t.start()

    # Use socketio.run instead of app.run for WebSocket support
    socketio.run(app, debug=True, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)
    