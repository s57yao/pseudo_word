"""Server to receive the data from survey."""
import argparse
from flask import Flask, request, render_template
from gevent.pywsgi import WSGIServer
import json
import numpy as np


_ACCEPT_STRING = json.dumps('https://app.prolific.com/submissions/complete?cc=CP800GLL')
_WARNING_STRING = json.dumps('https://app.prolific.com/submissions/complete?cc=C1OAGGQ8')

app = Flask(__name__)


@app.route('/experiment/', defaults={'path': ''})
@app.route('/experiment/<path:path>')
def index(path):
    """Serve the index page.

    Args:
        path: Path to the index page.
    """
    return render_template(f'{path}')


@app.route('/vlm_spatial_receive_data', methods=['POST'])
def receive_data():
    """Receive data from the survey."""
    raw_data = json.loads(request.data.decode())
    subject_id = raw_data['data'][0]['subject_id']
    study_id = raw_data['data'][0]['study_id']
    session_id = raw_data['data'][0]['session_id']
    # basic data checks: average response time >= 1000ms
    data = raw_data['data'][2:-1]
    rts = [item['rt'] for item in data]
    average_rt = np.mean(rts)
    if average_rt < 1000:
        with open(f'data/ongoing_warning/{subject_id}_{study_id}_{session_id}.json', 'w') as fout:
            json.dump(raw_data, fout, indent=4)
        return _WARNING_STRING
    # basic data checks: standard deviation of responses > 0
    responses = [item['response'] for item in data]
    std_response_threshold = 10
    if not (isinstance(responses[0], int) or isinstance(responses[0], float)):
        responses = [char2int(response) for response in responses]
        std_response_threshold = 0
    std_response = np.std(responses)
    if std_response <= std_response_threshold:
        with open(f'data/ongoing_warning/{subject_id}_{study_id}_{session_id}.json', 'w') as fout:
            json.dump(raw_data, fout, indent=4)
        return _WARNING_STRING
    # pass quality check, return the accept string
    with open(f'data/ongoing_accept/{subject_id}_{study_id}_{session_id}.json', 'w') as fout:
        json.dump(raw_data, fout, indent=4)
    return _ACCEPT_STRING


def char2int(char: str) -> str:
    """Converts a character to an integer.

    Args:
        char: Character to be converted.

    Returns:
        Integer representation of the character.
    """
    assert len(char) == 1, 'Input must be a single character.'
    return ord(char) - ord('a')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Server to receive the data from survey.')
    parser.add_argument('--port', type=int, default=8000, help='Port to run the server.')
    args = parser.parse_args()

    http_server = WSGIServer(('', args.port), app)
    http_server.serve_forever()