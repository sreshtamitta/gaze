from flask import Flask, jsonify, request, render_template, send_from_directory
from datetime import datetime, timedelta
import csv, os, json
from flask_cors import CORS
app = Flask(__name__, template_folder='templates', static_folder='static')
CORS(app)
DATA_DIR = os.path.join(os.getcwd(), 'data')
os.makedirs(DATA_DIR, exist_ok=True)
ALLOWED_MODES = ['pomodoro', '50_10', 'custom', 'count up']
STATE = {'focused': True, 'last_updated': None, 'detail': 'Focused', 'total_points': 0, 'session_start_time': None, 'session_rewarded': False, 'current_level': 1, 'rank_name': 'Egg', 'timer_running': False, 'timer_mode': 'count up', 'phase_start_time': None, 'phase_end_time': None, 'timer_state': 'IDLE', 'custom_study': 1500, 'custom_break': 300, 'last_5min_mark': 0, 'reward_detail': 'Select a mode to start focusing!'}
focus_session_length = 1500
LAST_USER_FILE = os.path.join(DATA_DIR, 'last_user.txt')
def user_file(username):
    safe = username.replace('/', '_') if username else 'default'
    return os.path.join(DATA_DIR, f'{safe}_events.csv')
def log_event(username, event_type, info=''):
    fname = user_file(username)
    ts = datetime.now().isoformat()
    header = not os.path.exists(fname)
    with open(fname, 'a', newline='') as f:
        writer = csv.writer(f)
        if header:
            writer.writerow(['timestamp','event','info'])
        writer.writerow([ts,event_type,info])
    try:
        with open(LAST_USER_FILE,'w') as lf:
            lf.write(username)
    except:
        pass

def tick_timer():   
    now = datetime.now()

    if STATE['timer_state'] == 'IDLE':
        return
    
    if not STATE.get('phase_end_time'):
        return
    
    if not STATE.get('timer_running'):
        return

    if STATE['timer_state'] == 'STUDYING':
        if STATE['timer_state'] == 'STUDYING' and now >= STATE['phase_end_time']:
            STATE['total_points'] += 100

            STATE['timer_state'] = 'ON_BREAK'
            STATE['phase_start_time'] = now
            STATE['phase_end_time'] = now + timedelta(seconds=STATE['custom_break'])

            STATE['session_rewarded'] = False
            STATE['last_5min_mark'] = 0

    elif STATE['timer_state'] == 'ON_BREAK':
        if now >= STATE['phase_end_time']:
            STATE['timer_state'] = 'STUDYING'
            STATE['phase_start_time'] = now
            STATE['phase_end_time'] = now + timedelta(seconds=STATE['custom_study'])

            STATE['last_5min_mark'] = 0

def add_focus_progress():
    now = datetime.now()

    if STATE['timer_state'] != 'STUDYING':
        return

    if STATE.get('phase_start_time') is None:
            STATE['phase_start_time'] = now
            STATE['last_5min_mark'] = 0
            STATE['session_rewarded'] = False
            return

    if not STATE['focused']:
        elapsed = 0
        STATE['last_5min_mark'] = 0
        STATE['session_rewarded'] = False
        return

    elapsed = (now - STATE['phase_start_time']).total_seconds()

    mode = STATE.get('timer_mode', 'count up')
    limit = get_focus_length()

    chunks = int((elapsed - STATE['last_5min_mark']) // 300)
    if chunks > 0:
        STATE['total_points'] += chunks * 5
        STATE['last_5min_mark'] += chunks * 300
    
    if mode == 'count up':
        # reward based on continuous accumulation
        if elapsed >= 1500:  # or your chosen interval
            STATE['total_points'] += 100
            STATE['phase_start_time'] = now
            STATE['last_5min_mark'] = 0

            update_level()
        return

    if mode != 'count up' and limit != float('inf'):
        if elapsed >= limit and not STATE.get('session_rewarded', False):
            STATE['total_points'] += 20
            STATE['session_rewarded'] = True

    if limit != float('inf') and elapsed >= limit:
        STATE['total_points'] += 100
        STATE['phase_start_time'] = now
        STATE['last_5min_mark'] = 0

        update_level()

def update_level():
    if STATE['total_points'] >= 100000:
        STATE['current_level'] = 4
        STATE['rank_name'] = 'Eagle'
    elif STATE['total_points'] >= 10000:
        STATE['current_level'] = 3
        STATE['rank_name'] = 'Fledgling'
    elif STATE['total_points'] >= 1000:
        STATE['current_level'] = 2
        STATE['rank_name'] = 'Hatchling'
    else:
        STATE['current_level'] = 1
        STATE['rank_name'] = 'Egg'

def get_focus_length():
    mode = STATE.get('timer_mode', 'count up')

    if mode == 'pomodoro':
        return 1500
    elif mode == '50_10':
        return 3000
    elif mode == 'custom':
        return focus_session_length  # optional later
    elif mode == 'count up':
        return float('inf')
    else:
        return 1500        
        
@app.route('/start_timer', methods=['POST'])
def start_timer():
    data = request.get_json() or {}
    mode = data.get('mode', 'count up')

    STATE['timer_mode'] = mode
    STATE['timer_running'] = True
    STATE['timer_state'] = 'STUDYING'
    STATE['phase_start_time'] = datetime.now()

    if mode == 'custom':
        STATE['custom_study'] = int(data.get('study', STATE['custom_study']))
        STATE['custom_break'] = int(data.get('break', STATE['custom_break']))
        
    if mode == 'count up':
            STATE['phase_end_time'] = None
            return jsonify({'ok': True})

    if mode == 'pomodoro':
        duration = 1500
    elif mode == '50_10':
        duration = 3000
    elif mode == 'custom':
        duration = STATE['custom_study']
    else:
        duration = 1500

    STATE['phase_end_time'] = STATE['phase_start_time'] + timedelta(seconds=duration)

    return jsonify({'ok': True})

@app.route('/set_mode', methods=['POST'])
def set_mode():
    data = request.get_json() or {}

    mode = data.get('mode', 'count up')

    if mode not in ALLOWED_MODES:
        mode = 'count up'

    STATE['timer_mode'] = mode

    return jsonify({'ok': True})
@app.route('/')
def index():
    return render_template('index.html')
@app.route('/status', methods=['GET'])
def status():
    now = datetime.now()

    # only run timer logic if active
    if STATE.get('timer_running') and STATE.get('timer_state') != 'IDLE':
        tick_timer()
        add_focus_progress()

    # elapsed (safe guard)
    if STATE.get('timer_start_time') is not None and STATE.get('timer_running'):
        STATE['elapsed'] = int((now - STATE['timer_start_time']).total_seconds())
    elif STATE.get('phase_start_time') is not None and STATE.get('timer_running'):
        STATE['elapsed'] = int((now - STATE['phase_start_time']).total_seconds())
    else:
        STATE['elapsed'] = 0

    # remaining (safe guard)
    if STATE.get('phase_end_time') and STATE.get('timer_running'):
        remaining = (STATE['phase_end_time'] - now).total_seconds()
        STATE['time_remaining'] = max(0, int(remaining))
    else:
        STATE['time_remaining'] = None

    print("STATUS:", STATE["timer_state"], STATE["timer_running"])

    return jsonify(STATE)

@app.route('/update', methods=['POST'])
def update():
    data = request.get_json() or {}
    event = data.get('event')
    username = data.get('username','default_user')

    if not event:
        event = 'focused' if data.get('focused', True) else 'eyes_away'

    # update STATE for dashboard
    if event == 'focused':
        STATE['focused'] = True
        STATE['detail'] = 'Focused'
    elif event == 'eyes_away':
        STATE['focused'] = False
        STATE['detail'] = 'Distracted - Eyes Away'
    elif event == 'face_not_detected':
        STATE['focused'] = False
        STATE['detail'] = 'Face Not Detected'
    else:
        STATE['focused'] = False
        STATE['detail'] = event.replace('_',' ').title()

    STATE['last_updated'] = datetime.now().isoformat()

    # log every event in CSV 
    log_event(username, event, '')

    print(f'[Gaze] Logged {event} for {username}')  # <-- debug

    return jsonify({'ok': True})
@app.route('/log_tab', methods=['POST'])
def log_tab():
    print("LOG_TAB HIT")
    data = request.get_json() or {}
    print("RAW TAB DATA:", data)
    username = data.get('username','default_user')
    url = data.get('url','')
    print("URL:", url)
    event = data.get('event','tab_switch')
    focus_domains = data.get('focus_domains', [])
    if isinstance(focus_domains, str):
        focus_domains = [d.strip() for d in focus_domains.split(',') if d.strip()]
    is_focused = False
    for d in focus_domains:
        if d and d in url:
            is_focused = True
            break
    if is_focused:
        event = 'focused'
    print("IS FOCUSED:", is_focused)
    log_event(username, event, url)
    STATE['focused'] = (event == 'focused')
    if event == 'focused':
        STATE['detail'] = f'Focused - Tab ({url})'
    else:
        STATE['detail'] = f'Distracted - Tab Switch ({url})'
    STATE['last_updated'] = datetime.now().isoformat()
    return jsonify({'ok':True})
@app.route('/events/<username>', methods=['GET'])
def get_events(username):
    fname = user_file(username)
    if os.path.exists(fname):
        return send_from_directory(os.path.dirname(fname), os.path.basename(fname), as_attachment=True)
    else:
        return ('No events yet for user', 404)
@app.route('/download_all/<username>', methods=['GET'])
def download_all(username):
    return get_events(username)
@app.route('/clear/<username>', methods=['POST'])
def clear_user(username):
    fname = user_file(username)
    if os.path.exists(fname):
        os.remove(fname)
        return jsonify({'ok': True})
    return jsonify({'ok': False, 'error': 'No file'})
@app.route('/set_custom_times', methods=['POST'])
def set_custom_times():
    data = request.get_json() or {}
    STATE['custom_study'] = int(data.get('study', STATE['custom_study']))
    STATE['custom_break'] = int(data.get('break', STATE['custom_break']))
    return jsonify({'ok': True})

@app.route('/stop_timer', methods=['POST'])
def stop_timer():
    STATE.update({
    'timer_running': False,
    'timer_state': 'IDLE',
    'phase_start_time': None,
    'phase_end_time': None,
    'elapsed': 0,
    'time_remaining': None,
    'focus_seconds_accumulator': 0
    })
    return jsonify({'ok': True})
@app.route('/last_user', methods=['GET'])
def last_user():
    if os.path.exists(LAST_USER_FILE):
        with open(LAST_USER_FILE,'r') as f:
            u = f.read().strip()
            return jsonify({'username': u})
    return jsonify({'username': ''})
if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000)

