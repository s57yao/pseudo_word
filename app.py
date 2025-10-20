from flask import Flask, render_template, request, jsonify
import os, json, datetime
import io, base64
import numpy as np
import uuid, shortuuid
import re
from gevent.pywsgi import WSGIServer   
import argparse
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/experiment', defaults={'path': ''})
@app.route('/experiment/<path:path>')
def index(path):
    return render_template('index.html')

@app.route('/save-data', methods=['POST'])
def save_data():
    try:
        data_json = request.get_json(force=True)
        trials = data_json
        participant_id = shortuuid.uuid()
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

    os.makedirs('data', exist_ok=True)
    filename = os.path.join('data', f'responses.jsonl')

    record = {
        'submitted_at': datetime.datetime.now(datetime.timezone.utc).isoformat() + 'Z',
        'client_ip': request.remote_addr,
        'trials': trials
    }
    with open(filename, 'a', encoding='utf-8') as f:
        f.write(json.dumps(record) + '\n')

    audio_trials = [t for t in trials[-61:-1] if 'response' in t and t['response']]
    if audio_trials:
        os.makedirs('data/audio', exist_ok=True)

    for i, trial in enumerate(audio_trials):
        audio_base64 = trial['response']
        word = re.sub('<[^<]+?>', '', trial['stimulus'])
        if ',' in audio_base64:
            audio_base64 = audio_base64.split(',')[1]
        audio_bytes = base64.b64decode(audio_base64)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        audio_filename = os.path.join('data/audio', f"{participant_id}_{word}_{timestamp}.webm")
        with open(audio_filename, 'wb') as audio_file:
            audio_file.write(audio_bytes)
    
    return jsonify({'status': 'ok', 'message': 'Data and audio saved'})

@app.route('/finish')
def finish():
    filename = os.path.join('data', 'responses.jsonl')
    with open(filename, "r") as f:
        last_line = f.readlines()[-1]
        record = json.loads(last_line)
    trial_data = record.get('trials', [])[-61:-1]
    rt_list = [trial.get('rt') for trial in trial_data if 'rt' in trial and trial['rt'] is not None]
    avg_rt = sum(rt_list)/len(rt_list) if rt_list else 0
    sd_rt = np.std(rt_list) if rt_list else 0
    if avg_rt >= 2000 and sd_rt >= 200:  
        url = "https://app.prolific.com/submissions/complete?cc=C11W147H"  
    else:
        url = "https://app.prolific.com/submissions/complete?cc=CK3EXTCI"
    return jsonify({"url": url})

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8002)
    parser.add_argument('--key-path', type=str, default=None)  
    parser.add_argument('--cert-path', type=str, default=None)  
    args = parser.parse_args()

    if args.key_path and args.cert_path:
        http_server = WSGIServer(
            ('0.0.0.0', args.port),
            app,
            keyfile=args.key_path,
            certfile=args.cert_path
        )
    else:
        from gevent.pywsgi import WSGIServer
        http_server = WSGIServer(('0.0.0.0', args.port), app)

    print(f"Serving on port {args.port}...")
    http_server.serve_forever()