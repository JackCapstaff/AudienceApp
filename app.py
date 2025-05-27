import os
import time
from flask import Flask, render_template, send_from_directory
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or os.urandom(24)
redis_url = os.environ.get('REDIS_URL') or os.environ.get('REDIS_TLS_URL')
socketio = SocketIO(
    app,
    message_queue=redis_url,
    cors_allowed_origins="*"
)

# --- In-memory current state (reset on restart!) ---
current_asset = {
    'type': 'slide',
    'name': 'holdingslide.jpg',
    'autoplay': False,
    'fadeIn': False,
    'video_time': 0.0,
    'video_paused': True,
    'video_speed': 1.0,
    'video_started_at': None  # UTC timestamp when video started playing (if playing)
}

def now():
    return time.time()

def update_video_started_at():
    # Called whenever play/pause is toggled
    if current_asset['type'] == 'video':
        if not current_asset['video_paused']:
            # Video started playing now: record wallclock time
            current_asset['video_started_at'] = now() - current_asset['video_time']
        else:
            # Video paused: stop "timer"
            current_asset['video_time'] = get_video_current_time()
            current_asset['video_started_at'] = None

def get_video_current_time():
    # Return the video time corresponding to wallclock
    if current_asset['type'] == 'video':
        if not current_asset['video_paused'] and current_asset['video_started_at'] is not None:
            # Compute how long since play started
            elapsed = now() - current_asset['video_started_at']
            return elapsed
        else:
            return current_asset.get('video_time', 0.0)
    return 0.0

@app.route('/control')
def control():
    slides_dir = os.path.join(app.root_path, 'static', 'slides')
    slides = sorted(f for f in os.listdir(slides_dir)
                    if f.lower().endswith(('.png', '.jpg', '.jpeg')))
    media_dir = os.path.join(app.root_path, 'static', 'media')
    videos = sorted(f for f in os.listdir(media_dir)
                    if f.lower().endswith(('.mp4', '.webm', '.ogg')))
    return render_template('control.html', slides=slides, videos=videos)

@app.route('/')
def audience():
    return render_template('audience.html')

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

# --- SocketIO handlers ---

@socketio.on('connect')
def on_connect():
    # Calculate current playback time for late joiners
    asset = current_asset.copy()
    if asset['type'] == 'video':
        asset['video_time'] = get_video_current_time()
    emit('sync_state', asset)

@socketio.on('display_asset')
def on_display_asset(data):
    global current_asset
    for k in ['type', 'name', 'autoplay', 'fadeIn']:
        if k in data:
            current_asset[k] = data[k]
    if current_asset['type'] == 'video':
        # Always reset time and paused status on new video
        current_asset['video_time'] = 0.0
        current_asset['video_paused'] = not current_asset.get('autoplay', False)
        current_asset['video_speed'] = 1.0
        if not current_asset['video_paused']:
            current_asset['video_started_at'] = now()
        else:
            current_asset['video_started_at'] = None
    else:
        current_asset['video_time'] = 0.0
        current_asset['video_paused'] = True
        current_asset['video_speed'] = 1.0
        current_asset['video_started_at'] = None

    # For all: emit with up-to-date video_time
    asset = current_asset.copy()
    if asset['type'] == 'video':
        asset['video_time'] = get_video_current_time()
    emit('display_asset', asset, broadcast=True)

@socketio.on('fade_to_black')
def on_fade_to_black():
    emit('fade_to_black', broadcast=True)

@socketio.on('play_pause_video')
def on_play_pause_video():
    # Toggle paused
    current_asset['video_time'] = get_video_current_time()
    current_asset['video_paused'] = not current_asset.get('video_paused', True)
    update_video_started_at()
    asset = current_asset.copy()
    if asset['type'] == 'video':
        asset['video_time'] = get_video_current_time()
    emit('play_pause_video', asset, broadcast=True)

@socketio.on('set_playback_speed')
def on_set_playback_speed(data):
    speed = float(data.get('speed', 1.0))
    # adjust base time to preserve continuity
    if current_asset['type'] == 'video':
        if not current_asset['video_paused'] and current_asset['video_started_at'] is not None:
            base_time = get_video_current_time()
            current_asset['video_speed'] = speed
            current_asset['video_started_at'] = now() - (base_time / speed)
        else:
            current_asset['video_speed'] = speed
    emit('set_playback_speed', {'speed': speed}, broadcast=True)

@socketio.on('seek_video')
def on_seek_video(data):
    time_sec = float(data.get('time', 0.0))
    if current_asset['type'] == 'video':
        current_asset['video_time'] = time_sec
        if not current_asset['video_paused']:
            current_asset['video_started_at'] = now() - time_sec / current_asset['video_speed']
        else:
            current_asset['video_started_at'] = None
    emit('seek_video', {'time': time_sec}, broadcast=True)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port)
