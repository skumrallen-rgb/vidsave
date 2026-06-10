import os
import subprocess
import tempfile
import re
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
            output_template = os.path.join(tmpdir, 'video.%(ext)s')

            cmd = [
                'yt-dlp',
                '--no-playlist',
                '-f', 'bestvideo[ext=mp4][vcodec^=avc]+bestaudio[ext=m4a]/bestvideo[ext=mp4]+bestaudio/best[ext=mp4]/best',
                '--merge-output-format', 'mp4',
                '--postprocessor-args', 'ffmpeg:-c:v libx264 -c:a aac -movflags +faststart',
                '-o', output_template,
                '--no-warnings',
                '--no-check-certificates',
                url
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)

            if result.returncode != 0:
                error_msg = result.stderr or result.stdout
                if 'Private' in error_msg:
                    return jsonify({'error': 'Videon är privat och kan inte laddas ner.'}), 400
                elif 'login' in error_msg.lower():
                    return jsonify({'error': 'Videon kräver inloggning.'}), 400
                elif 'twitter' in url or 'x.com' in url:
                    return jsonify({'error': 'X/Twitter kräver ofta inloggning för att ladda ner. Prova en annan video.'}), 400
                else:
                    return jsonify({'error': 'Kunde inte ladda ner videon. Kontrollera länken och försök igen.'}), 400

            # Find downloaded file
            files = [f for f in os.listdir(tmpdir) if f.endswith('.mp4')]
            if not files:
                files = os.listdir(tmpdir)
            if not files:
                return jsonify({'error': 'Filen hittades inte efter nedladdning.'}), 500

            filepath = os.path.join(tmpdir, files[0])
            filename = 'video.mp4'

            return send_file(
                filepath,
                as_attachment=True,
                download_name=filename,
                mimetype='video/mp4'
            )

    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Timeout — videon tog för lång tid. Prova en kortare video.'}), 500
    except Exception as e:
        return jsonify({'error': f'Serverfel: {str(e)}'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
