import os
import subprocess
import tempfile
import json
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SUPPORTED = ['youtube.com', 'youtu.be', 'tiktok.com', 'instagram.com', 'x.com', 'twitter.com']

def is_supported(url):
    return any(s in url for s in SUPPORTED)

@app.route('/')
def index():
    return send_file(os.path.join(BASE_DIR, 'index.html'))

@app.route('/checklive', methods=['POST'])
def check_live():
    data = request.get_json()
    handles = data.get('handles', [])
    results = {}
    for handle in handles:
        handle = handle.strip().lstrip('@')
        url = f'https://www.tiktok.com/@{handle}/live'
        try:
            cmd = ['yt-dlp', '--no-warnings', '--no-playlist', '--skip-download',
                   '--dump-json', '--no-check-certificates', url]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            if result.returncode == 0 and result.stdout.strip():
                try:
                    info = json.loads(result.stdout.strip().split('\n')[0])
                    is_live = info.get('is_live', False) or info.get('live_status') == 'is_live'
                    results[handle] = 'live' if is_live else 'offline'
                except:
                    results[handle] = 'offline'
            else:
                results[handle] = 'offline'
        except subprocess.TimeoutExpired:
            results[handle] = 'offline'
        except Exception:
            results[handle] = 'error'
    return jsonify(results)

@app.route('/download', methods=['POST'])
def download():
    data = request.get_json()
    url = data.get('url', '').strip()

    if not url:
        return jsonify({'error': 'Ingen URL angiven'}), 400

    if not is_supported(url):
        return jsonify({'error': 'Plattformen stöds inte.'}), 400

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_template = os.path.join(tmpdir, 'video.%(ext)s')

            # No ffmpeg conversion — download best mp4 directly to save memory
            cmd = [
                'yt-dlp',
                '--no-playlist',
                '-f', 'best[ext=mp4]/best',
                '-o', output_template,
                '--no-warnings',
                '--no-check-certificates',
                '--socket-timeout', '30',
                url
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

            if result.returncode != 0:
                error_msg = result.stderr or result.stdout
                if 'Private' in error_msg:
                    return jsonify({'error': 'Videon är privat.'}), 400
                elif 'login' in error_msg.lower():
                    return jsonify({'error': 'Videon kräver inloggning.'}), 400
                else:
                    return jsonify({'error': 'Kunde inte ladda ner. Kontrollera länken.'}), 400

            files = os.listdir(tmpdir)
            if not files:
                return jsonify({'error': 'Filen hittades inte.'}), 500

            # Prefer mp4 but take whatever we got
            mp4_files = [f for f in files if f.endswith('.mp4')]
            filename = mp4_files[0] if mp4_files else files[0]
            filepath = os.path.join(tmpdir, filename)

            return send_file(
                filepath,
                as_attachment=True,
                download_name='video.mp4',
                mimetype='video/mp4'
            )

    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Timeout — videon tog för lång tid. Prova en kortare video.'}), 500
    except Exception as e:
        return jsonify({'error': f'Serverfel: {str(e)}'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
