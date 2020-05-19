"""spotify.py - All Spotify related functions go in here """
import spotipy
from discord.ext import commands
from spotipy.oauth2 import SpotifyClientCredentials

import keys
from cogs.music import Song


class Spotify(commands.Cog):
    """ Spotify cog """
    def __init__(self, bot):
        self.bot = bot
        self.client = spotipy.Spotify(
            client_credentials_manager=SpotifyClientCredentials(
                client_secret=keys.spotify_secret,
                client_id=keys.spotify_id
            ))
        self.client.trace = False
        self.client.trace_out = False

    async def album_to_songs(self, album_id):
        """ Converts a Spotify Album ID to a list of Song() objects.
        Args:
            album_id: The album ID as a string.
        Raises:
            AttributeError: If the album_id is not a string.
            spotipy.client.SpotifyException: If the album ID is empty or invalid.
        Returns:
            A list of Song() objects.
        """
        playlist = self.client.album_tracks(album_id)
        songs = []

        tracks = playlist.get('tracks', {}).get('items')
        if tracks is None:
            tracks = playlist.get('items', [])

        print(tracks)

        for track in tracks:
            song = track_to_song(track)
            song.url = "https://open.spotify.com/album/" + album_id
            songs.append(song)

        return songs

    async def artist_top_songs(self, artist_id, num_songs=10):
        """ Searches for an artists top tracks.
        Args:
            artist_id: A Spotify Artist ID.
            num_songs: Number of songs to return. Maximum: 10
        Raises:
            spotipy.client.SpotifyException: If the artist ID is empty or invalid.
        Returns:
            A list of Song() objects.
        """
        playlist = self.client.artist_top_tracks(artist_id=artist_id)
        songs = []
        for track in playlist['tracks']:
            song = track_to_song(track)
            songs.append(song)

        return songs[:num_songs]

    async def playlist_to_songs(self, playlist_id):
        """ Converts a Spotify Playlist to Song() objects.
        Args:
            playlist_id: A Spotify Playlist ID.
        Raises:
            spotipy.client.SpotifyException: If the playlist ID is empty or invalid.
        Returns:
            A list of Song() objects.
        """
        playlist = self.client._get("playlists/%s" % (playlist_id)) # pylint: disable=protected-access
        songs = []

        for track in playlist['tracks']['items']:
            song = track_to_song(track.get('track'))
            if song is not None:
                song.url = f"https://open.spotify.com/playlist/{playlist_id}" # Replace url with spotify link
                songs.append(song)

        return songs

    async def query_to_album(self, query):
        """ Searches Spotify Albums for a given query.
        Args:
            query: A query string.
        Raises:
            IndexError: If the query returned no results.
            spotipy.client.SpotifyException: If the search query is empty.
        Returns:
            A Spotify Album object
        """
        results = self.client.search(q=query, type='album')
        return results['albums']['items'][0]

    async def query_to_artist(self, query):
        """ Searches Spotify Artists for a given query.
        Args:
            query: A query string.
        Raises:
            IndexError: If the query returned no results.
            spotipy.client.SpotifyException: If the search query is empty.
        Returns:
            A Spotify Artist object
        """
        results = self.client.search(q=query, type='artist')
        return results['artists']['items'][0]

    async def url_to_songs(self, url):
        """ Returns a list of Song() objects from a given URL.
        Args:
            url: A Spotify URL string.
        Raises:
            ?
        Returns:
            A list of Song() objects, possibly empty.
        """
        songs = []

        if 'album' in url:
            album_id = get_url_value(url, "album")
            if album_id is not None:
                for song in await self.album_to_songs(album_id):
                    songs.append(song)

        elif 'artist' in url:
            artist_id = get_url_value(url, "artist")
            if artist_id is not None:
                for song in await self.artist_top_songs(artist_id):
                    songs.append(song)

        elif 'playlist' in url:
            playlist_id = get_url_value(url, "playlist")
            if playlist_id is not None:
                for song in await self.playlist_to_songs(playlist_id):
                    song.url = url
                    songs.append(song)

        elif 'track' in url:
            track_id = get_url_value(url, "track")

            # Lookup song in database
            song = self.bot.db.find_song(spotify_id=track_id)
            if song is None:
                # not cached, look up song via spotify web api
                track = self.client.track(track_id)
                song = track_to_song(track)
            songs.append(song)

        return songs

def get_url_value(url, key):
    """ Extracts a value from a URL of the form:
        http://www.example.com/[key]/[value to be returned]?otherkey=notimportant

    Args:
        url: The URL string to search.
    Returns:
        The value following the key in the url, or None if something goes wrong.
    """
    try:
        return url.split("{}/".format(key))[1].split("?", 1)[0]
    except IndexError:
        return None

def track_to_song(track):
    """ Converts a single Spotify Track to a Song
    Args:
        track: Spotify Track object.
    Raises:
        ?
    Returns:
        A Song() object.
    """
    if track is None:
        return None

    artist_name = track.get('artists', [{}])[0].get('name')
    track_name = track.get('name')
    track_id = track.get('id')
    duration_ms = track.get('duration_ms', 0)

    if track_id is None:
        return None

    #print(f"track_to_song() {artist_name} - {track_name} [{track_id}] ({duration_ms})")

    song = Song()
    song.duration = int(duration_ms / 1000)
    song.title = f"{artist_name} - {track_name}"
    song.query = song.title
    song.url = f"https://open.spotify.com/track/{track_id}"
    song.spotify_id = track_id
    return song

def setup(bot):
    bot.add_cog(Spotify(bot))
    print("Loaded Spotify cog")
