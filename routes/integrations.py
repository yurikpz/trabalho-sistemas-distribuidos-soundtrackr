from flask import Blueprint, request, jsonify
import requests
import os

bp = Blueprint('integrations', __name__)


#CONFIGURAÇÕES DE API

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "AIzaSyCwxWyijyzesFj1geR7m3S1T6j2X7BzJSU")
ITUNES_SEARCH_URL = "https://itunes.apple.com/search"
LYRICS_OVH_URL = "https://api.lyrics.ovh/v1"


#API DE BUSCA DO ITUNES

@bp.route('/search')
def search():
    """
    Faz busca na API do iTunes por música, álbum ou artista.
    Parâmetros:
      - term (string)
      - entity (song  album  musicArtist)
    """
    term = request.args.get('term')
    entity = request.args.get('entity', 'song')
    if not term:
        return jsonify([])

    resp = requests.get(ITUNES_SEARCH_URL, params={'term': term, 'entity': entity, 'limit': 25})
    if resp.status_code != 200:
        return jsonify([])

    data = resp.json()
    return jsonify(data.get('results', []))


#YOUTUBE DATA API — BUSCA MV

@bp.route('/youtube')
def youtube_video():
    """
    Busca o MV no YouTube.
    Parâmetros:
      - q (string): termo da música ou artista
    """
    q = request.args.get('q')
    if not q:
        return jsonify({'error': 'missing query'}), 400

    search_url = (
        f"https://www.googleapis.com/youtube/v3/search"
        f"?part=snippet&type=video&maxResults=3&q={q}+MV"
        f"&key={YOUTUBE_API_KEY}"
    )
    r = requests.get(search_url)
    if r.status_code != 200:
        return jsonify({'error': 'youtube_fail'}), 500

    data = r.json()
    items = data.get("items", [])

    #fallback: lyric video (mvídeo com letra da música)
    if not items:
        search_url_lyric = (
            f"https://www.googleapis.com/youtube/v3/search"
            f"?part=snippet&type=video&maxResults=3&q={q}+lyric+video"
            f"&key={YOUTUBE_API_KEY}"
        )
        r2 = requests.get(search_url_lyric)
        data2 = r2.json()
        items = data2.get("items", [])

    if not items:
        return jsonify({'videoId': None})

    video_id = items[0]["id"]["videoId"]
    title = items[0]["snippet"]["title"]
    channel = items[0]["snippet"]["channelTitle"]

    return jsonify({
        'videoId': video_id,
        'title': title,
        'channel': channel
    })


# API DA LETRA

@bp.route('/lyrics')
def lyrics():
    """
    Retorna letra da música via lyrics.ovh
    Parâmetros:
      - artist
      - title
    """
    artist = request.args.get('artist')
    title = request.args.get('title')

    if not artist or not title:
        return jsonify({'error': 'missing params'}), 400

    try:
        resp = requests.get(f"{LYRICS_OVH_URL}/{artist}/{title}")
        if resp.status_code == 200:
            return jsonify(resp.json())
        else:
            return jsonify({'lyrics': 'Letra não encontrada 😢'})
    except Exception:
        return jsonify({'lyrics': 'Erro ao obter letra.'})
