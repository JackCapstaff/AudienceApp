import os
from flask import Flask, render_template, send_from_directory
from flask_socketio import SocketIO, emit

app = Flask(__name__)
# Pull SECRET_KEY from Heroku’s config; fall back to random if unset.
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or os.urandom(24)

redis_url = os.environ.get('REDIS_URL') or os.environ.get('REDIS_TLS_URL')
socketio = SocketIO(
    app,
    message_queue=redis_url,
    cors_allowed_origins="*"        # <— allow the client’s polling requests
)



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

# Media Controls
@socketio.on('play_pause_video')
def on_play_pause_video():
  print("👂 [server] play_pause_video received")
  emit('play_pause_video', broadcast=True)

@socketio.on('set_playback_speed')
def on_set_playback_speed(data):
  print("👂 [server] set_playback_speed received:", data)
  emit('set_playback_speed', data, broadcast=True)

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
    port = int(os.environ.get('PORT', 5000))
    print("⚙️  Starting SocketIO server on port", port, "…")
    socketio.run(
        app,
        host='0.0.0.0',
        port=port,
        
    )
