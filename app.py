import os
import time
from flask import (
    Flask, render_template, send_from_directory,
    request, session, redirect, url_for, flash
)
from flask_socketio import SocketIO, emit, disconnect
from dotenv import load_dotenv
from functools import wraps

# Load .env into os.environ (okay locally; Azure uses App Settings)
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', os.urandom(24))

# Redis for socket‐messaging (optional in Azure)
redis_url = os.environ.get('REDIS_URL') or os.environ.get('REDIS_TLS_URL')
socketio = SocketIO(app, message_queue=redis_url, cors_allowed_origins="*")

# ---- Auth config (SAFE READ) ----
VALID_USER = os.environ.get('CONTROL_USER')
VALID_PASS = os.environ.get('CONTROL_PASS')
if not VALID_USER or not VALID_PASS:
    # Don’t crash at import on Azure; log + default to disabled auth
    # Prefer: set CONTROL_USER/CONTROL_PASS in Azure → Configuration.
    print("[WARN] CONTROL_USER / CONTROL_PASS not set – /control will require login but no creds configured.", flush=True)

# ---- Viewer count (note: per-process only) ----
active_viewers = 0

def now(): return time.time()

current_asset = {
    'type': 'slide',
    'name': 'holdingslide.jpg',
    'autoplay': False,
    'fadeIn': False,
    'video_time': 0.0,
    'video_paused': True,
    'video_speed': 1.0,
    'video_started_at': None
}

def update_video_started_at():
    if current_asset['type'] == 'video':
        if not current_asset['video_paused']:
            current_asset['video_started_at'] = now() - current_asset['video_time']
        else:
            current_asset['video_time'] = get_video_current_time()
            current_asset['video_started_at'] = None

def get_video_current_time():
    if current_asset['type'] == 'video':
        if not current_asset['video_paused'] and current_asset['video_started_at'] is not None:
            return now() - current_asset['video_started_at']
        return float(current_asset.get('video_time', 0.0))
    return 0.0

# ---------------------------------------------------------------------
# Decorator
# ---------------------------------------------------------------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Auto-auth for localhost
        host = request.host.split(':')[0]
        if host in ('localhost', '127.0.0.1', '::1'):
            session['authenticated'] = True
            return f(*args, **kwargs)

        if not session.get('authenticated'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ---------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        if VALID_USER and VALID_PASS and username == VALID_USER and password == VALID_PASS:
            session['authenticated'] = True
            flash('Logged in successfully', 'success')
            return redirect(url_for('control'))
        else:
            flash('Invalid credentials', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('authenticated', None)
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))

# ---------------------------------------------------------------------
# Control interface
# ---------------------------------------------------------------------
@app.route('/control')
@login_required
def control():
    slides_dir = os.path.join(app.root_path, 'static', 'slides')
    media_dir = os.path.join(app.root_path, 'static', 'media')

    slides = []
    if os.path.isdir(slides_dir):
        slides = sorted(f for f in os.listdir(slides_dir)
                        if f.lower().endswith(('.png', '.jpg', '.jpeg')))

    videos = []
    if os.path.isdir(media_dir):
        videos = sorted(f for f in os.listdir(media_dir)
                        if f.lower().endswith(('.mp4', '.webm', '.ogg')))

    return render_template('control.html', slides=slides, videos=videos)

# ---------------------------------------------------------------------
# Audience
# ---------------------------------------------------------------------
@app.route('/')
def audience():
    return render_template('audience.html')

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

# ---------------------------------------------------------------------
# Socket.IO
# ---------------------------------------------------------------------
@socketio.on('connect')
def on_connect():
    # viewer count (best-effort; per-process)
    global active_viewers
    active_viewers += 1
    emit('viewer_count_update', {'count': active_viewers}, broadcast=True)

    # late join sync
    asset = current_asset.copy()
    if asset['type'] == 'video':
        asset['video_time'] = get_video_current_time()
    emit('sync_state', asset)

@socketio.on('disconnect')
def on_disconnect():
    global active_viewers
    active_viewers = max(0, active_viewers - 1)
    emit('viewer_count_update', {'count': active_viewers}, broadcast=True)

@socketio.on('display_asset')
def on_display_asset(data):
    global current_asset
    for k in ['type', 'name', 'autoplay', 'fadeIn']:
        if k in data:
            current_asset[k] = data[k]
    if current_asset['type'] == 'video':
        current_asset['video_time'] = 0.0
        current_asset['video_paused'] = not current_asset.get('autoplay', False)
        current_asset['video_speed'] = 1.0
        current_asset['video_started_at'] = None if current_asset['video_paused'] else now()
    else:
        current_asset.update({
            'video_time': 0.0,
            'video_paused': True,
            'video_speed': 1.0,
            'video_started_at': None
        })

    asset = current_asset.copy()
    if asset['type'] == 'video':
        asset['video_time'] = get_video_current_time()

    emit('display_asset', {
        'type': data.get('type'),
        'name': data.get('name'),
        'autoplay': data.get('autoplay', False),
        'fadeIn': data.get('fadeIn', False),
        'id': data.get('id')
    }, broadcast=True)

@socketio.on('transition')
def on_transition(data):
    emit('transition', data, broadcast=True)

@socketio.on('crossfade_to')
def handle_crossfade_to(asset):
    socketio.emit('crossfade_to', asset)
    socketio.emit('crossfade_to_control', asset)

@socketio.on('fade_to_black')
def on_fade_to_black(data=None):
    emit('fade_to_black', data or {}, broadcast=True)
    emit('fade_to_black_control', data or {}, broadcast=True)

@socketio.on('fade_from_black')
def on_fade_from_black(data=None):
    emit('fade_from_black', data or {}, broadcast=True)

@socketio.on('play_pause_video')
def on_play_pause_video():
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
    import sys
    port = int(os.environ.get('PORT', 5000))
    print("Starting Audience Live App…", flush=True)
    print(f"Python {sys.version.split()[0]}  •  Port {port}", flush=True)
    socketio.run(app, host='0.0.0.0', port=port, debug=True)
