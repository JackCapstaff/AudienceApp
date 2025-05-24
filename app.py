# app.py
import os
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit

app = Flask(__name__, static_folder="static")
socketio = SocketIO(app)

# --- State ---
current_index = 0
polls = {}   # { poll_id: { question, options: {opt:count}, active, results } }

# --- Routes ---
@app.route("/")
def audience():
    return render_template("audience.html")

@app.route('/control')
def control():
    slides_dir = os.path.join(app.root_path, 'static', 'slides')
    # include png, jpg, jpeg
    slides = sorted([
        f for f in os.listdir(slides_dir)
        if f.lower().endswith(('.png', '.jpg', '.jpeg'))
    ])

    media_dir = os.path.join(app.root_path, 'static', 'media')
    videos = [f for f in os.listdir(media_dir)
              if f.lower().endswith(('.mp4', '.webm', '.ogg'))]

    return render_template(
        'control.html',
        slides=slides,
        videos=videos,
        polls=polls
    )

@socketio.on('fade_to_black')
def handle_fade_to_black():
    emit('fade_to_black', broadcast=True)

@socketio.on('play_video')
def handle_play_video():
    emit('play_video', broadcast=True)



@socketio.on('play_media')
def on_play_media(data):
    filename = data.get('filename')
    # Broadcast to audience clients
    emit('play_media', {'filename': filename}, broadcast=True)

@socketio.on('stop_media')
def on_stop_media():
    emit('stop_media', broadcast=True)
    



@app.route("/create_poll", methods=["POST"])
def create_poll():
    data = request.json
    pid = str(len(polls)+1)
    polls[pid] = {
        "question": data["question"],
        "options": {opt: 0 for opt in data["options"]},
        "active": True
    }
    socketio.emit("new_poll", {"id": pid, **polls[pid]})
    return jsonify(success=True, poll_id=pid)

# --- SocketIO events ---
@socketio.on("change_slide")
def on_change(data):
    global current_index
    current_index = data["index"]
    emit("slide_update", {"index": current_index}, broadcast=True)

@socketio.on("vote")
def on_vote(data):
    pid = data["poll_id"]
    opt = data["option"]
    if pid in polls and polls[pid]["active"]:
        polls[pid]["options"][opt] += 1
        # broadcast updated results to control panel
        emit("poll_update", {"poll_id": pid, "results": polls[pid]["options"]}, broadcast=False)

@socketio.on("close_poll")
def on_close(data):
    pid = data["poll_id"]
    if pid in polls:
        polls[pid]["active"] = False
        emit("poll_closed", {"poll_id": pid, "results": polls[pid]["options"]}, broadcast=True)

@socketio.on('display_asset')
def on_display_asset(data):
    # debug log
    print(f"[socketio] display_asset received: {data}")
    # broadcast to everyone
    emit('display_asset', data, broadcast=True)



if __name__ == "__main__":
    print("⚙️  Starting SocketIO server…")
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)