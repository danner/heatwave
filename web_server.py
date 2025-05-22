# Use gevent instead of eventlet for monkey patching
from gevent import monkey
monkey.patch_all()

from flask import Flask, render_template, jsonify, redirect, request, Response
from flask_socketio import SocketIO, emit
import gevent
# Only import from state.py - no circular dependencies
from state import (
    channels, register_update_callback, adjust_frequency as state_adjust_frequency,
    adjust_volume as state_adjust_volume, set_mute, handle_global_action
)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'heatwave-secret!'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')

# Reference to channels will be set from main.py
channels_ref = None

# Captive portal detection URLs
@app.route('/generate_204')  # Android
@app.route('/gen_204')  # Android
@app.route('/connecttest.txt')  # Windows
@app.route('/redirect')  # Windows
@app.route('/hotspot-detect.html')  # iOS
@app.route('/library/test/success.html')  # iOS
@app.route('/success.txt')  # MacOS
@app.route('/ncsi.txt')  # Windows
def captive_portal_check():
    # For iOS and MacOS, redirect to the main page
    user_agent = request.headers.get('User-Agent', '').lower()
    if 'cros' in user_agent or 'android' in user_agent:
        # For Android, return a 204 status without content
        return "", 204
    else:
        # For other devices, redirect to our interface
        return redirect('/', code=302)

# Captive portal detection - return success for Windows
@app.route('/ncsi.txt')
def ncsi():
    return Response("Microsoft NCSI", mimetype="text/plain")

# Captive portal detection - return success for iOS/MacOS
@app.route('/success.txt')
def success():
    return Response("success", mimetype="text/plain")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/visualization')
def visualization():
    return render_template('visualization.html')

@app.route('/api/channels')
def get_channels():
    # This should return the current state of your channels
    return jsonify(channels)

@socketio.on('connect')
def handle_connect():
    print('Client connected')
    handle_request_all_channels()  # Reuse the same function

@socketio.on('change_frequency')
def handle_frequency_change(data):
    if channels_ref and 'frequency' in data:
        channel = data.get('channel', 0)
        channels_ref[channel]['frequency'] = float(data['frequency'])
        print(f"Web client changed frequency for channel {channel} to {data['frequency']}")
        # Broadcast to all clients except the sender
        emit('update_channel', {
            'channel': channel,
            'frequency': channels_ref[channel]['frequency']
        }, broadcast=True, include_self=False)

@socketio.on('change_mute')
def handle_mute_change(data):
    if channels_ref and 'mute' in data:
        channel = data.get('channel', 0)
        set_mute(channel, data['mute'])
        print(f"Web client changed mute for channel {channel} to {data['mute']}")
        # Broadcast to all clients except the sender
        emit('update_channel', {
            'channel': channel,
            'mute': channels_ref[channel]['mute']
        }, broadcast=True, include_self=False)

@socketio.on('change_volume')
def handle_volume_change(data):
    if channels_ref and 'volume' in data:
        channel = data.get('channel', 0)
        channels_ref[channel]['volume'] = float(data['volume'])
        print(f"Web client changed volume for channel {channel} to {data['volume']}")
        # Broadcast to all clients except the sender
        emit('update_channel', {
            'channel': channel,
            'volume': channels_ref[channel]['volume']
        }, broadcast=True, include_self=False)

@socketio.on('global_button')
def handle_global_button_event(data):
    if channels_ref and 'button_name' in data:
        button_name = data['button_name']
        print(f"Web client pressed global button: {button_name}")
        handle_global_action(button_name)

@socketio.on('request_all_channels')
def handle_request_all_channels():
    if channels_ref:
        # Send state for all channels
        for i in range(8):
            emit('update_channel', {
                'channel': i,
                'frequency': channels_ref[i]['frequency'],
                'volume': channels_ref[i]['volume'],
                'mute': channels_ref[i]['mute']
            })

def start_web_server(channels):
    global channels_ref
    channels_ref = channels
    
    # Register the broadcast function as a callback for state changes
    register_update_callback(broadcast_channel_update)
    
    # Start Flask-SocketIO with gevent in the main thread
    print("Starting web server with gevent at http://0.0.0.0:6134")
    socketio.run(app, host='0.0.0.0', port=6134, debug=False)

# Function to broadcast channel updates to all web clients
def broadcast_channel_update(channel_number):
    if channels_ref and socketio:
        try:
            socketio.emit('update_channel', {
                'channel': channel_number,
                'frequency': channels_ref[channel_number]['frequency'],
                'volume': channels_ref[channel_number]['volume'],
                'mute': channels_ref[channel_number]['mute']
            })
        except Exception as e:
            print(f"Error broadcasting update: {e}")