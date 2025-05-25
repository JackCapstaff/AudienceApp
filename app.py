import os
from flask import Flask, render_template, send_from_directory
from flask_socketio import SocketIO, emit

# Create Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'replace-with-your-secret'

# Initialize Socket.IO (no async_mode override so it auto-picks gevent)
socketio = SocketIO(app)

# In-memory polls example (if you use it)
polls = {}

# Serve control panel
@app.route('/control')
def control():
    # Dynamically list slides and videos
    slides_dir = os.path.join(app.root_path, 'static', 'slides')
    slides = sorted(f for f in os.listdir(slides_dir)
                    if f.lower().endswith(('.png', '.jpg', '.jpeg')))
    media_dir = os.path.join(app.root_path, 'static', 'media')
    videos = sorted(f for f in os.listdir(media_dir)
                    if f.lower().endswith(('.mp4', '.webm', '.ogg')))
    return render_template('control.html', slides=slides, videos=videos)

# Serve audience view
@app.route('/')
def audience():
    return render_template('audience.html')

# Debug handler: slide paging
@socketio.on('change_slide')
def on_change_slide(data):
    print("👂 [server] change_slide received:", data)
    emit('slide_update', data, broadcast=True)

# Debug handler: display any asset
@socketio.on('display_asset')
def on_display_asset(data):
    print("👂 [server] display_asset received:", data)
    emit('display_asset', data, broadcast=True)

# Debug handler: fade to black
@socketio.on('fade_to_black')
def on_fade_to_black():
    print("👂 [server] fade_to_black received")
    emit('fade_to_black', broadcast=True)

# Debug handler: play video
@socketio.on('play_video')
def on_play_video():
    print("👂 [server] play_video received")
    emit('play_video', broadcast=True)

# Debug handler: votes (if using polls)
@socketio.on('vote')
def on_vote(payload):
    print("👂 [server] vote:", payload)
    # you’d normally store and maybe emit updated results here

# Static files for favicon (optional)
@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

if __name__ == '__main__':
    # Make sure to run via `python app.py` in a terminal
    print("⚙️  Starting SocketIO server…")
    socketio.run(
        app,
        host='0.0.0.0',
        port=5000,
        debug=True,
        use_reloader=True
    )
