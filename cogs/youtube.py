""" Youtube cog """
import html
from urllib.parse import urlencode

import isodate
import requests
import youtube_dl
from discord.ext import commands
from cogs.music import Song

import keys

OPTIONS = {'format': 'bestaudio/best',
           'extractaudio' : True,
           'audioformat' : "mp3",
           'outtmpl': '%(id)s',
           'noplaylist' : True,
           'nocheckcertificate' : True,
           'no_warnings' : True,
          }

class YouTube(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.downloader = youtube_dl.YoutubeDL(OPTIONS)

    def _get(self, endpoint, params=None):
        """ Makes an authorized request to the desired endpoint.

        Returns:
            JSONified response
        """
        url = f"https://www.googleapis.com/youtube/v3/{endpoint}?key={keys.youtube_key}&"
        if params:
            url += urlencode(params)
        print(f"YouTube._get({url})")
        response = requests.get(url)
        return response.json()

    async def load_song(self, song):
        """
        Populates the following fields of a song:
         - thumbnail
         - title
         - url
         - youtube_id
        Either song.query or song.youtube_id must be set for this to work
        Returns the song after updating the fields.
        """
        # Missing video id, use query to get it (does not set duration)
        if song.youtube_id is None:
            params = {
                "part": "snippet",
                "type": "video",
                "maxResults": 1,
                "q": song.query,
                }
            results = self._get("search", params=params)
            item = results.get("items", [{}])[0]
            snippet = item.get("snippet", {})
            song.youtube_id = item.get("id", {}).get("videoId")
            if song.title is None:
                song.title = html.unescape(snippet.get("title", "?"))
                song.title = song.title.translate(str.maketrans(dict.fromkeys('[]()')))
            thumbnails = snippet.get("thumbnails", {}).get("high", {})
            song.thumbnail = thumbnails.get("url", "https://i.imgur.com/MSg2a9d.png")

        # If we have the video id, make sure we have these too
        if song.title is None or song.thumbnail is None or song.duration is None:
            params = {
                "part": "contentDetails,snippet",
                "id": song.youtube_id,
                }
            results = self._get("videos", params=params)
            item = results.get("items", [{}])[0]
            snippet = item.get("snippet", {})
            if song.title is None:
                song.title = html.unescape(snippet.get("title", "?"))
                song.title = song.title.translate(str.maketrans(dict.fromkeys('[]()')))
            thumbnails = snippet.get("thumbnails", {}).get("high", {})
            song.thumbnail = thumbnails.get("url", "https://i.imgur.com/MSg2a9d.png")
            duration = item.get("contentDetails", {}).get("duration")
            if duration is not None:
                song.duration = isodate.parse_duration(duration).total_seconds()
            else:
                song.duration = 0

        # Overwrite spotify URLs
        song.url = "http://youtube.com/watch?v={}".format(song.youtube_id)

        return song

    async def url_to_songs(self, url):
        """ Returns a list of Song()s from given YouTube URL """
        if 'playlist' in url:
            songs = await self.playlist_to_songs(url)
        else:
            songs = await self.video_to_songs(url)
        return songs

    async def playlist_to_songs(self, url):
        """ Returns a list of Song() objects from a given youtube playlist """
        songs = []

        playlist_id = url.split('list=', 1)[1].split('&', 1)[0]

        # Get the list of videos in the playlist
        params = {
            "part": "contentDetails,snippet",
            "maxResults": 50,
            "playlistId": playlist_id,
        }
        results = self._get("playlistItems", params)
        # Go through each page of results
        index = 0
        while index < results.get("pageInfo", {}).get("totalResults", 0):
            for item in results.get("items", []):
                song = self.video_item_to_song(item)
                songs.append(song)
                index += 1
            try:
                # Get next page using the token
                params["pageToken"] = results["nextPageToken"]
                results = self._get("playlistItems", params)
            except KeyError:
                # Last page
                pass

        return songs

    async def video_to_songs(self, url):
        """ Converts a video URL to a list containing one Song """
        if 'youtube.com' in url:
            youtube_id = url.split('v=', 1)[1].split('&', 1)[0]
        elif 'youtu.be' in url:
            youtube_id = url.split('youtu.be/', 1)[1].split('&', 1)[0]
        else:
            return []

        # Lookup song in database
        query = f"SELECT title, duration, plays, thumbnail FROM songs WHERE youtube_id = ?"
        self.bot.db.cursor.execute(query, (youtube_id,))
        song = self.bot.db.find_song(youtube_id=youtube_id)
        if song is None:
            song = Song()
            song.youtube_id = youtube_id
            song = await self.load_song(song)

        return [song]

    def video_item_to_song(self, item):
        """ Converts a YouTube response from the videos or playlistItems endpoint to a Song() """
        song = Song()
        snippet = item.get("snippet", {})
        thumbnails = snippet.get("thumbnails", {}).get("high", {})
        song.thumbnail = thumbnails.get("url", "https://i.imgur.com/MSg2a9d.png")

        duration = item.get("contentDetails", {}).get("duration")
        if duration is not None:
            song.duration = isodate.parse_duration(duration).total_seconds()
        else:
            song.duration = 0
        song.youtube_id = snippet.get("resourceId", {}).get("videoId")
        if song.youtube_id is None: # ID may be in two different places
            song.youtube_id = item.get("id")
        song.title = snippet.get("title").replace('[', '').replace(']', '')
        song.url = "http://youtube.com/watch?v={}".format(song.youtube_id)
        return song
    


def setup(bot):
    bot.add_cog(YouTube(bot))
    print("Loaded YouTube cog")
