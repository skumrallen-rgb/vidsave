import os
import subprocess
import tempfile
import re
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

SUPPORTED = ['youtube.com', 'youtu.be', 'tiktok.com', 'instagram.com', 'x.com', 'twitter.com']

def is_supported(url):
    return any(s in url for s in SUPPORTED)

@app.route('/')
def index():
    return send_file('index.html')

@app.route('/download', methods=['POST'])
def download():
    data = request.get_json()
    url = data.get('url', '').strip()

    if not url:
        return jsonify({'error': 'Ingen URL angiven'}), 400

    if not is_supported(url):
        return jsonify({'error': 'Plattformen stöds inte. Använd YouTube, TikTok, Instagram eller X.'}), 400

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_template = os.path.join(tmpdir, '%(title)s.%(ext)s')

            cmd = [
                'yt-dlp',
                '--no-playlist',
                '--merge-output-format', 'mp4',
                '-f', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                '-o', output_template,
                '--no-warnings',
                url
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

            if result.returncode != 0:
                error_msg = result.stderr or result.stdout
                # Clean up error message
                if 'Private video' in error_msg:
                    return jsonify({'error': 'Videon är privat och kan inte laddas ner.'}), 400
                elif 'Login' in error_msg or 'login' in error_msg:
                    return jsonify({'error': 'Videon kräver inloggning.'}), 400
                else:
                    return jsonify({'error': 'Kunde inte ladda ner videon. Kontrollera länken.'}), 400

            # Find downloaded file
            files = os.listdir(tmpdir)
            if not files:
                return jsonify({'error': 'Filen hittades inte efter nedladdning.'}), 500

            filepath = os.path.join(tmpdir, files[0])
            filename = files[0]
            # Clean filename
            filename = re.sub(r'[^\w\s\-.]', '', filename).strip()
            if not filename.endswith('.mp4'):
                filename += '.mp4'

            return send_file(
                filepath,
                as_attachment=True,
                download_name=filename,
                mimetype='video/mp4'
            )

    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Timeout — videon tog för lång tid att ladda ner.'}), 500
    except Exception as e:
        return jsonify({'error': f'Serverfel: {str(e)}'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
