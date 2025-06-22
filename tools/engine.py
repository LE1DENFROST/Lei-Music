import os
import time
import yt_dlp
import wikipediaapi
import musicbrainzngs
from ytmusicapi import YTMusic
from concurrent.futures import ThreadPoolExecutor, as_completed

class MusicEngine:
    def __init__(self, cache_ttl_seconds=1800):
        print("MusicEngine başlatılıyor...")
        self.ytmusic = YTMusic()
        musicbrainzngs.set_useragent("Lei-Music", "1.0", "mailto:user@example.com")
        self.wiki_tr = wikipediaapi.Wikipedia(user_agent="Lei-Music/1.0", language='tr', extract_format=wikipediaapi.ExtractFormat.WIKI)
        self.wiki_en = wikipediaapi.Wikipedia(user_agent="Lei-Music/1.0", language='en', extract_format=wikipediaapi.ExtractFormat.WIKI)

        self._api_cache = {}
        self.CACHE_TTL = cache_ttl_seconds

        if not os.path.exists('music_cache'):
            os.makedirs('music_cache')

        self.YDL_OPTS_STREAM_URL = {'format': 'bestaudio/best', 'quiet': True}
        self.YDL_OPTS_DOWNLOAD = {
            'format': 'bestaudio/best', 'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'opus', 'preferredquality': '192'}],
            'outtmpl': os.path.join('music_cache', '%(id)s.%(ext)s'), 'noplaylist': True, 'quiet': True,
            'retries': 10, 'fragment_retries': 10, 'socket_timeout': 10
        }
        print("MusicEngine başarıyla başlatıldı.")

    def _get_from_cache(self, key):
        if key in self._api_cache:
            data, timestamp = self._api_cache[key]
            if time.time() - timestamp < self.CACHE_TTL:
                print(f"'{key}' için önbellekten başarılı bir şekilde veri çekildi.")
                return data
        return None

    def _set_in_cache(self, key, data):
        print(f"'{key}' için yeni veri önbelleğe alınıyor.")
        self._api_cache[key] = (data, time.time())

    def _parse_track_data(self, track, album_thumbnails=None):
        artist_name = "Bilinmeyen Sanatçı"
        if track.get('artists') and track['artists'][0].get('name'):
            artist_name = track['artists'][0]['name']

        thumbnail_url = album_thumbnails[-1]['url'] if album_thumbnails else (track['thumbnails'][-1]['url'] if track.get('thumbnails') else None)

        return {
            'type': 'song',  
            'id': track.get('videoId'), 'title': track.get('title', 'Başlık Yok'),
            'duration': track.get('duration_seconds', 0), 'thumbnail': thumbnail_url,
            'artist': artist_name
        }

    def _parse_artist_data(self, artist):
        return {
            'type': 'artist', 
            'browseId': artist.get('browseId'),
            'artist': artist.get('artist'),
            'thumbnail': artist['thumbnails'][-1]['url'] if artist.get('thumbnails') else None,
        }

    def _parse_album_data(self, album):
        return {
            'type': 'album', 
            'browseId': album.get('browseId'),
            'title': album.get('title'),
            'artist': album['artists'][0]['name'] if album.get('artists') else 'Çeşitli Sanatçılar',
            'year': album.get('year'),
            'thumbnail': album['thumbnails'][-1]['url'] if album.get('thumbnails') else None,
        }

    def search_ytmusic(self, query, limit=20, search_filter="songs"):
        cache_key = f"search:{query}:{limit}:{search_filter}"
        cached_data = self._get_from_cache(cache_key)
        if cached_data:
            return cached_data

        try:
            search_results = self.ytmusic.search(query, filter=search_filter, limit=limit)
            
            results = []
            if search_filter == "songs":
                results = [self._parse_track_data(song) for song in search_results if song.get('videoId')]
            elif search_filter == "artists":
                results = [self._parse_artist_data(artist) for artist in search_results if artist.get('browseId')]
            elif search_filter == "albums":
                results = [self._parse_album_data(album) for album in search_results if album.get('browseId')]

            self._set_in_cache(cache_key, results)
            return results
        except Exception as e:
            print(f"YTMusic API '{search_filter}' arama sırasında hata: {e}")
            return []

    def get_stream_url(self, video_id):
        try:
            with yt_dlp.YoutubeDL(self.YDL_OPTS_STREAM_URL) as ydl:
                info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
                return info['url']
        except Exception as e:
            print(f"Stream URL alınırken hata: {e}")
            return None

    def download_and_cache_song(self, video_id):
        try:
            with yt_dlp.YoutubeDL(self.YDL_OPTS_DOWNLOAD) as ydl:
                ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
            return True
        except Exception:
            return False

    def check_cache(self, video_id):
        cached_path = os.path.join('music_cache', f"{video_id}.opus")
        return cached_path if os.path.exists(cached_path) else None

    def get_artist_info(self, artist_name):
        if not artist_name or artist_name == "Bilinmeyen Sanatçı":
            return None
            
        cache_key = f"artist_v3:{artist_name}" 
        cached_data = self._get_from_cache(cache_key)
        if cached_data:
            return cached_data

        print(f"--- API'den bilgi aranıyor: '{artist_name}' ---")
        artist_info = {'name': artist_name, 'bio': "Biyografi bulunamadı.", 'image_url': None}
        mb_artist_type = None
        try:
            result = musicbrainzngs.search_artists(artist=artist_name, limit=1, strict=True)
            if result['artist-list'] and result['artist-list'][0]['ext:score'] == '100':
                mb_artist = result['artist-list'][0]
                mb_artist_type = mb_artist.get('type')
                print(f"MusicBrainz sonucu: '{artist_name}' bir '{mb_artist_type}'")
        except Exception as e:
            print(f"MusicBrainz hatası: {e}")
        search_queries = []
        if mb_artist_type == 'Person':
            search_queries.extend([f"{artist_name} (şarkıcı)", f"{artist_name} (müzisyen)"])
        elif mb_artist_type == 'Group':
            search_queries.extend([f"{artist_name} (müzik grubu)", f"{artist_name} (grup)"])
        search_queries.append(artist_name)
        search_queries.extend([f"{artist_name} (müzik grubu)", f"{artist_name} (şarkıcı)"])
        search_queries = list(dict.fromkeys(search_queries))
        print(f"Wikipedia için denenecek sorgular: {search_queries}")
        MUSIC_KEYWORDS = ['grup', 'band', 'müzisyen', 'musician', 'şarkıcı', 'singer', 'albüm', 'album', 'rock', 'pop', 'metal', 'sanatçı']
        FILM_KEYWORDS = ['film', 'movie', 'yönetmen', 'director', 'oyuncu', 'actor', 'actress', 'sinema', 'cinema']
        bio_found = False
        for query in search_queries:
            if bio_found: break
            for lang_wiki in [self.wiki_tr, self.wiki_en]:
                if bio_found: break
                try:
                    page = lang_wiki.page(query)
                    if page.exists() and len(page.summary) > 50:
                        summary_lower = page.summary.lower()
                        if any(keyword in summary_lower for keyword in FILM_KEYWORDS):
                            print(f"'{query}' sorgusu bir filmle ilgili, atlanıyor.")
                            continue 
                        is_music_related = any(keyword in summary_lower for keyword in MUSIC_KEYWORDS)
                        if artist_name.lower() in summary_lower and is_music_related:
                            artist_info['bio'] = page.summary.split('\n')[0].strip()
                            print(f"DOĞRU BİLGİ BULUNDU! Dil: {lang_wiki.language}, Sorgu: '{query}'")
                            bio_found = True
                            break 
                except Exception as e:
                    print(f"Wikipedia sorgusu '{query}' sırasında hata: {e}")
        self._set_in_cache(cache_key, artist_info)
        return artist_info

    def get_ytmusic_browse_results(self, browse_id):
        if not browse_id: return []
        cache_key = f"browse:{browse_id}"
        cached_data = self._get_from_cache(cache_key)
        if cached_data:
            return cached_data

        results = []
        try:
            if browse_id.startswith('UC'):
                print(f"Sanatçı ID'si ({browse_id}) için sonuçlar getiriliyor...")
                artist_data = self.ytmusic.get_artist(browse_id)
                if artist_data.get('songs') and artist_data['songs'].get('browseId'):
                    playlist_id = artist_data['songs']['browseId']
                    playlist_data = self.ytmusic.get_playlist(playlist_id, limit=50)
                    results = [self._parse_track_data(track) for track in playlist_data.get('tracks', [])]
                else: 
                    print(f"Sanatçının ({browse_id}) doğrudan şarkı listesi bulunamadı.")

            elif browse_id.startswith('MPRE'):
                print(f"Albüm ID'si ({browse_id}) için sonuçlar getiriliyor...")
                album_data = self.ytmusic.get_album(browse_id)
                results = [self._parse_track_data(track, album_data.get('thumbnails')) for track in album_data.get('tracks', [])]

            else: 
                print(f"Çalma Listesi ID'si ({browse_id}) için sonuçlar getiriliyor...")
                playlist_data = self.ytmusic.get_playlist(browse_id, limit=50)
                results = [self._parse_track_data(track) for track in playlist_data.get('tracks', [])]

            if results:
                self._set_in_cache(cache_key, results)
            return results

        except Exception as e:
            print(f"ID {browse_id} için içerik getirilirken hata oluştu: {e}")
            return []

    def get_ytmusic_discover_data(self):
        """Keşfet kategorilerini paralel olarak çeker. Kategori listesini önbelleğe alır."""
        cache_key = "discover_data"
        cached_data = self._get_from_cache(cache_key)
        if cached_data:
            return cached_data

        discover_data = {}
        CATEGORIES_TO_SEARCH = ["50s Rock'n'Roll Classics", "Türkçe Rock", "Rock Classics", "Chill Music", "Focus Piano", "Workout Gym"]

        def _fetch(query):
            try:
                results = self.ytmusic.search(query, filter="playlists", limit=5) 
                playlists = [{'title': r['title'], 'browseId': r.get('browseId'), 'thumbnails': r.get('thumbnails')} for r in results if r.get('browseId') and r.get('browseId').startswith(('VL', 'PL'))]
                return query, playlists
            except Exception:
                return query, []

        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_query = {executor.submit(_fetch, query): query for query in CATEGORIES_TO_SEARCH}
            for future in as_completed(future_to_query):
                query, playlists = future.result()
                if playlists:
                    discover_data[query] = playlists
        
        self._set_in_cache(cache_key, discover_data)
        return discover_data