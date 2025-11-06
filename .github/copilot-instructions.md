Project: AudienceApp — Flask + SocketIO audience display

Short goal
- This app serves a live audience display and a control panel. The server is a single-process Flask app using Flask-SocketIO for realtime messaging. Typical agent tasks: add routes, change socket events, update templates, or wire Redis for scaling.

Architecture (big picture)
- Single Flask app: `app.py` is the entrypoint and contains routes and SocketIO handlers. Templates are regular HTML files (not in a `templates/` subfolder; the app uses `template_folder='.'`).
- Static assets: `static/slides/` (images), `static/media/` (videos), and `static/` for CSS/JS and `favicon.ico`.
- In-memory state: `current_asset` dict in `app.py` holds the currently displayed asset and playback metadata. It is intentionally ephemeral (resets on restart).
- Realtime comms: Flask-SocketIO events broadcast control messages to all viewers. Redis is supported as a message queue via the `REDIS_URL` env var for scaling across processes.

Key files
- `app.py` — main app, contains: login, `/control` and `/` routes, socket event handlers (names used by clients: `display_asset`, `play_pause_video`, `seek_video`, `set_playback_speed`, `transition`, `crossfade_to`, `fade_to_black`). Use this file to understand event payload shapes.
- `requirements.txt` — dependencies (Flask, Flask-SocketIO, gevent, redis, python-dotenv). Match versions when adding dependencies.
- `static/slides/` and `static/media/` — files enumerated by `/control` route; new assets are picked up automatically.
- `templates/*.html` — `audience.html`, `control.html`, `login.html` are the client views; they reference the SocketIO event names and expected payloads.

Developer workflows & commands
- Run locally (development): set `PORT` and optional `REDIS_URL` in `.env` then run app directly: Python runs via `socketio.run(app, host='0.0.0.0', port=PORT, debug=True)` in `app.py`. Use `python app.py` in the project root.
- Production: container or Gunicorn + gevent is expected (requirements include `gunicorn` and `gevent`). If deploying multiple workers, set `REDIS_URL` so SocketIO uses Redis message queue.
- Common env vars:
  - `SECRET_KEY` — session secret (optional; auto-generated if missing)
  - `CONTROL_USER` / `CONTROL_PASS` — credentials for the control panel (required)
  - `REDIS_URL` or `REDIS_TLS_URL` — optional, for multi-process SocketIO
  - `PORT` — optional, defaults to 5000

Conventions & patterns agents should follow
- Templates are simple static HTML; modify `control.html` when changing control UI and mirror event names used in `app.py`.
- The server keeps playback timing using wallclock math (see `video_started_at`, `video_time`, `video_paused`, `video_speed`). When updating video logic, preserve the `get_video_current_time()` and `update_video_started_at()` semantics so late-joiners are synced correctly.
- Authentication: lightweight session-based check implemented by `login_required` decorator. Localhost bypass exists — agents should not remove this without reason.
- State is kept in memory (global `current_asset`) — any agent aiming for persistence or multi-process correctness must use Redis or another store and update all SocketIO emitters to use `socketio.emit(..., broadcast=True)` or `socketio.send` as appropriate.

Examples (from code)
- Emit current state to new connections: the `connect` handler copies `current_asset` and updates `video_time` using `get_video_current_time()` before emitting `sync_state`.
- Display an asset (control → all): `display_asset` updates `current_asset`, resets video timing for videos, then emits `display_asset` with `{type, name, autoplay, fadeIn, id}` to all clients.

What NOT to change without checking
- The timing math around video playback (`video_started_at`, `video_time`, `video_speed`) — subtle and used to sync viewers.
- Socket event names — clients rely on exact strings in `templates/*.html` and static JS.

If you need more
- Open `app.py` and search for `@socketio.on(...)` to find all socket events.
- Look at `control.html` to see how the control UI emits events and the payload structure expected.

Please review these instructions and tell me if you want more examples (payload schemas) or added guidance for tests / CI.
