import asyncio
import os
import random
import time

import discord
import lyricsgenius
from discord.ext import commands

import keys

class Song:
    def __init__(self):
        self.title = None       # (str) Title
        self.duration = None    # (int) Duration in seconds
        self.position = 0       # (int) Current position in song in seconds
        self.plays = 0          # (int) Number of plays
        self.query = None       # (str) Search query that matched this song
        self.thumbnail = None   # (str) URL of thumbnail from YouTube API
        self.url = None         # (str) URL of song source
        self.youtube_id = None  # (str) ID of YouTube video
        self.spotify_id = None  # (str) ID of YouTube video
        self.user = None # (discord.User) who requested this song

    @property
    def path(self):
        return f"./songs/{self.youtube_id}.mp3"

    @property
    def pretty_duration(self):
        """ Converts the duration into a string like '4h20m' """
        if self.duration is None:
            return "?"
        if self.duration < 60: # Under a minute
            return "{}s".format(int(self.duration))
        if self.duration < 3600: # Under an hour
            return "{}m{}s".format(int(self.duration / 60), int(self.duration % 60))
        # Over an hour
        return "{}h{}m{}s".format(int(self.duration / 3600), int(self.duration % 3600 / 60), int(self.duration % 60))

    @property
    def youtube_url(self):
        return f"https://youtu.be/{self.youtube_id}"


class SongQueue:
    def __init__(self, bot):
        self.bot = bot
        self.songs = []
        self.position = 0
        self.queue_message = None

    @property
    def next_song(self):
        if self.position < len(self.songs):
            return self.songs[self.position]
        return None

    def format_queue(self):
        """ Returns a song list with the current song highlighted """
        max_songs = 10
        song_list = ""

        # Find the start and end of what we should print
        queue_length = len(self.songs)

        # case 0: no songs in queue
        if len(self.songs) == 0:
            return "(empty)"

        # case 1: queue is shorter than max songs, print the whole thing
        if queue_length <= max_songs:
            start = 0
            end = queue_length

        # case 2: less than max_songs away from the current song - print old songs
        elif self.position-1+max_songs > queue_length:
            start = queue_length - max_songs
            if start < 0:
                start = 0
            end = queue_length

        # case 3: more than max_songs away from current song - print current and next few
        else:
            start = max(0, self.position-1)
            end = self.position + max_songs

        for i, song in enumerate(self.songs[start:end]):
            # Nicely format the duration
            duration = song.pretty_duration

            # Limit name length
            length = 41 - len(duration)

            # Add a triangle to the current song
            symbol = "⭄" if self.position == start + i else "--"

            # Remove brackets from song title and limit length
            title = song.title[:length].translate(str.maketrans(dict.fromkeys('[]()')))

            song_list += " {} {} [**{}**]({}) ({})\n".format(
                symbol, start+i, title, song.url, duration)

            if i == max_songs:
                break

        return song_list

    async def clear(self):
        self.position = 0
        self.songs = []
        await self.update_queue_message()

    async def queue(self, songs, user, insert=False):
        """ Adds songs to the queue, if insert is true they will play next """
        if insert:
            for i, song in enumerate(songs):
                song.user = user
                self.songs.insert(self.position + 1 + i, song)
        else:
            for song in songs:
                song.user = user
                self.songs.append(song)
        await self.update_queue_message()

    async def send_queue_message(self, channel):
        """ Deletes existing queue message and sends a new one.

        Args:
            channel: discord.TextChannel to send the message
        """

        # Delete old message
        await self.bot.delete_message(self.queue_message)
        self.queue_message = None

        # Send the new message
        embed = discord.Embed(color=0x22FF33, title="Şarkı Sırası ♫")
        embed.description = self.format_queue()
        self.queue_message = await channel.send(embed=embed)
            
        # Non-empty queue - add shuffle button
        if self.songs:
            await self.bot.add_reactions(self.queue_message, "🔀")

        return self.queue_message

    async def shuffle(self):
        """ Shuffles the songs beyond the current position """
        if len(self.songs) > self.position+1:
            temp = self.songs[self.position+1:]
            random.shuffle(temp)
            self.songs[self.position+1:] = temp
            
        await self.update_queue_message()

    async def update_queue_message(self):
        """ Updates Queue message if it exists. """
        if self.queue_message is not None and self.queue_message.embeds:
            embed = self.queue_message.embeds[0]
            embed.description = self.format_queue()
            try:
                await self.queue_message.edit(embed=embed)
            except discord.errors.NotFound:
                pass


class MusicPlayer:
    def __init__(self, bot, guild, volume=20):
        self.bot = bot
        self.guild = guild
        self.volume = 20
        self.queue = SongQueue(bot)
        self.np_message = None     # (discord.Message) last printed Now Playing message
        self.volume_message = None # (discord.Message) last printed volume
        self.play_lock = False
        self.youtube = bot.get_cog('YouTube')
        self.vc = None

        self.repeat = False
        self.repeat_one = False

    async def increment_position(self):
        """ Used by play when going to the next song. """
        # Do not increment position if repeat one is set
        if self.repeat_one:
            return

        self.queue.position += 1
        # Hit the end of the queue
        if len(self.queue.songs) <= self.queue.position:
            # Repeat
            if self.repeat:
                self.queue.position = 0

    async def connect(self, voice_channel):
        """ Connects to a voice channel. Returns the voice channel or None if error """
        # Find the voice client for this server
        if self.vc is None:
            self.vc = discord.utils.get(self.bot.voice_clients, guild=voice_channel.guild)

        if self.vc is None:
            print("Connecting to voice channel:", voice_channel)
            try:
                self.vc = await voice_channel.connect()
                while not self.vc.is_connected():
                    print("waiting to connect")
                print("Successfully connected to:", self.vc.channel.name)
            except discord.errors.ClientException:
                print("Already connected")
            except asyncio.TimeoutError:
                print("Timed out!")


        # Move to the user if nobody is in the room with the bot
        if self.vc is not None and len(self.vc.channel.members) == 1:
            print("Moving to", voice_channel)
            await self.vc.move_to(voice_channel)

        return self.vc

    async def play(self, text_channel):
        """ Plays through the song queue
        :param channel: discord.TextChannel to send now playing message
        """
        # Allow one thread in here at a time
        if self.play_lock:
            return
        self.play_lock = True

        # Require voice client to exist
        if self.vc is None: 
            await text_channel.send(f"Voice client does not exist. Please send stop command and try again.")
            print(f"Voice client does not exist: {self.vc}")
            self.play_lock = False
            return

        ## Require voice client to be connected
        #if not self.vc.is_connected(): 
        #    await text_channel.send(f"Failed to join channel. Please send stop command and try again.")
        #    await self.vc.disconnect(force=True)
        #    self.vc = None
        #    self.play_lock = False
        #    return

        # Do nothing if already playing
        if self.vc.is_playing():
            print("Player already playing")
            self.play_lock = False
            return

        # Change status text to "Now playing"
        if self.np_message is not None and self.np_message.embeds:
            try:
                embed = self.np_message.embeds[0]
                title = "Şimdi oynuyor ♫"
                if not title == embed.title:
                    embed.title = title
                    await self.np_message.edit(embed=embed)
            except discord.errors.NotFound:
                pass

        # Player was previously paused
        if self.vc.is_paused():
            self.vc.resume()
            print("Oynatıldı, devam ettirildi")
            self.play_lock = False
            return

        # Delete now playing message if no song in queue
        if self.queue.next_song is None:
            print(f"[{text_channel.guild.name}] sırada hiçbir şey kalmadı")
            await self.queue.update_queue_message()
            await self.bot.delete_message(self.np_message)
            self.np_message = None
            self.play_lock = False
            return

        # Grab the next song and get it ready
        try:
            song = self.queue.next_song
            song = await self.youtube.load_song(song)
        except IndexError:
            await text_channel.send(f"Bir şey ters gitti, şarkı sıradan getiriliyor(Error code: {len(self.queue.songs)} {self.queue.position})")
            self.play_lock = False
            return
        # Get the mp3 ready
        try:
            await self.download_song(song)
        except Exception as error:
            await text_channel.send(f"İndirme hatası {song.title} {error}")
            await self.increment_position()
            self.play_lock = False
            return

        # Log song info
        print(f"[{text_channel.guild.name}] ({song.user.display_name}) playing {song.title} ({song.plays} plays)")

        # Create the audio source. FFmpegPCMAudio reference:
        # https://discordpy.readthedocs.io/en/latest/api.html#discord.FFmpegPCMAudio
        # Loudnorm filter didn't work, disabling
        #options = f"-af loudnorm=I=-16.0:TP=-1.0 -ss {song.position}"
        options = f"-ss {song.position}"
        try:
            audio_source_raw = discord.FFmpegPCMAudio(source=song.path, options=options)
        except discord.errors.ClientException:
            audio_source_raw = discord.FFmpegPCMAudio(source=song.path, executable="C:/ffmpeg/bin/ffmpeg.exe", options=options)

        # Set the volume. PCMVolumeTransformer reference:
        # https://discordpy.readthedocs.io/en/latest/api.html#discord.PCMVolumeTransformer
        audio_source = discord.PCMVolumeTransformer(audio_source_raw, volume=self.volume / 100.0)

        # Begin playback
        self.vc.play(audio_source)
        
        # Send now-playing message and update queue
        await self.send_now_playing(text_channel=text_channel)
        await self.queue.update_queue_message()

        # Wait for it to finish
        while self.vc and self.vc.is_playing():
            await asyncio.sleep(2)

        # Player was stopped or paused
        if self.vc is None or self.vc.is_paused():
            self.play_lock = False
            return

        # Song finished playing - increment playcount in database
        song.plays += 1
        self.bot.db.save_song(song)

        # Go on to the next song
        await self.increment_position()
        # Update queue message
        await self.queue.update_queue_message()
        self.play_lock = False
        await self.play(text_channel)

    async def pause(self):
        """ Pauses voice client and updates the Now Playing message """
        if self.vc is not None and self.vc.is_playing():
            self.vc.pause()
        if self.np_message and self.np_message.embeds:
            try:
                embed = self.np_message.embeds[0]
                title = "Şimdi Duraklatıldı ♫"
                if not title == embed.title:
                    embed.title = title
                    await self.np_message.edit(embed=embed)
            except discord.errors.NotFound:
                pass

    async def set_volume(self, volume):
        """ Sets the player's volume in range [0,100] """
        self.volume = max(min(100, volume), 0)

        # Change current audio source volume
        if self.vc and self.vc.source:
            self.vc.source.volume = self.volume/100.0

        return self.volume

    async def skip(self, n=1):
        """ Skips n songs """
        print(f"skipping {n} songs")
        index = self.queue.position + n
        # Something is playing, it will increment pos by 1 when we stop the queue
        if self.vc and self.vc.is_playing():
            index = max(0, index - 1)
            self.queue.position = min(index, len(self.queue.songs))
            self.vc.stop()
        else:
            self.queue.position = min(index, len(self.queue.songs))
        print("skipped to:", self.queue.position)

    async def skipto(self, index):
        """ Skips to the given index """
        print("skipping to ", index, min(index, len(self.queue.songs)))
        # Something is playing, it will increment pos by 1 when we stop the queue
        if self.vc and self.vc.is_playing():
            index = max(0, index - 1)
            self.queue.position = min(index, len(self.queue.songs))
            self.vc.stop()
        else:
            self.queue.position = min(index, len(self.queue.songs))
        print("skipped to:", self.queue.position)

    async def stop(self):
        """ Clears queue and disconnects, deleting all messages """
        await self.queue.clear()
        if self.vc is not None:
            await self.vc.disconnect(force=True)
            self.vc = None
        await self.bot.delete_message(self.np_message)
        await self.bot.delete_message(self.queue.queue_message)
        self.np_message = None
        self.queue_message = None

    async def download_song(self, song):
        """ Downloads the .mp3 file from YouTube """
        if not os.path.exists("./songs"):
            os.mkdir("./songs")

        # Use cached file if it exists
        if os.path.isfile(song.path):
            print(f"Using cached file for {song.title}: {song.path}")
            return
    
        # Download using youtube-dl
        self.youtube.downloader.download(['https://www.youtube.com/watch?v=BaW_jenozKc'])
        download = self.youtube.downloader.download([f"http://youtube.com/watch?v={song.youtube_id}"])

        # Rename to song_id.mp3
        if os.path.isfile(song.youtube_id):
            os.rename(song.youtube_id, song.path)
        
    async def send_now_playing(self, text_channel):
        """ Sends a Now Playing message, if possible also deletes the last one """
        # Delete the last message if it exists
        await self.bot.delete_message(self.np_message)
        self.np_message = None

        # Queue is empty, delete previous now_playing messages
        if self.queue.next_song is None:
            await text_channel.send("Nothing is playing.")
            return

        song = self.queue.next_song
        text = f"[**{song.title}**]({song.url})"

        # Add user's name and song duration to footer
        footer = f"@{song.user.display_name} ({song.pretty_duration})"

        # Add "Up next" to footer if something is in the queue
        if len(self.queue.songs) > self.queue.position + 1:
            footer += " Up next: {}".format(self.queue.songs[self.queue.position+1].title)

        # Send a new message
        self.np_message = await self.bot.send_embed(channel=text_channel,
                                                    color=0xFF69B4,
                                                    footer=footer,
                                                    footer_icon=song.user.avatar_url_as(size=64),
                                                    text=text,
                                                    thumbnail=song.thumbnail,
                                                    title="Şimdi oynuyor ♫")

        # Add emoji controls
        await self.bot.add_reactions(self.np_message, "⏸▶⏭⏹🇶🔊")
        return self.np_message

    async def send_volume(self, text_channel):
        """ Sends a volume message, if possible also deletes the last one """
        await self.bot.delete_message(self.volume_message)
        self.volume_message = None

        # Send the new message
        self.volume_message = await self.bot.send_embed(channel=text_channel,
                                                        color=0x22FF33,
                                                        title=f"Ses : {int(self.volume)}%",
                                                        text=volume_bar(self.volume))
        # Add emoji controls
        await self.bot.add_reactions(self.volume_message, "⏬⬇⬆⏫✳")

    async def update_volume_message(self, user):
        """ Updates the last sent volume message """
        if self.volume_message is not None:
            embed = self.volume_message.embeds[0]
            embed.title = f"Ses : {int(self.volume)}%"
            embed.description = volume_bar(self.volume)
            embed.set_footer(text=f"{user.display_name} tarafından değiştirildi", 
                             icon_url=user.avatar_url_as(size=64))
            try:
                await self.volume_message.edit(embed=embed)
            except discord.errors.NotFound:
                pass


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._music_players = {} # key = guild.id, value = music.MusicPlayer()
        self.genius = lyricsgenius.Genius(keys.genius_key)
        self.genius.verbose = False # Turn off status messages
        self.youtube = self.bot.get_cog('YouTube')
        self.spotify = self.bot.get_cog('Spotify')

    async def args_to_songs(self, args):
        """ Converts a list of arguments to a list of Songs """
        songs = []
        query = ""

        for arg in args:
            # Spotify songs/playlists/albums
            if 'spotify.com' in arg:
                spotify_songs = await self.spotify.url_to_songs(arg)
                songs.extend(spotify_songs)
            # YouTube videos/playlists
            elif 'youtube.com' in arg or 'youtu.be' in arg:
                youtube_songs = await self.youtube.url_to_songs(arg)
                songs.extend(youtube_songs)
            # Gather all non-links into one query string
            else:
                query = query + arg + " "

        query = query.strip()
                
        # Search query
        if len(query) > 0:
            result = self.bot.db.find_song(query=query)
            if result is None: 
                song = Song()
                song.query = query
                try:
                    song = await self.youtube.load_song(song)
                    songs.append(song)
                except IndexError:
                    pass
            else:
                songs.append(result)

        return songs

    async def get_player(self, ctx):
        """ Finds or creates a guild's music player. """
        try:
            player = self._music_players[ctx.guild.id]
        except KeyError:
            # Create new MusicPlayer, check database for saved volume
            self.bot.db.cursor.execute(f"SELECT volume FROM guilds WHERE id = ?", (ctx.guild.id,))
            vol = self.bot.db.cursor.fetchone()
            volume = 20
            if vol is not None and vol[0] is not None:
                volume = vol[0]
            self._music_players[ctx.guild.id] = MusicPlayer(self.bot, ctx.guild, volume)
            player = self._music_players[ctx.guild.id]
        return player

    async def find_music_channel(self, ctx):
        """ Returns the guild's music channel if it exists """
        # Check the database
        self.bot.db.cursor.execute(f"SELECT music_channel FROM guilds WHERE id = ?", (ctx.guild.id,))
        result = self.bot.db.cursor.fetchone()
        print("find music channel:", result)
        if result and result[0] is not None:
            print("found id:", result[0])
            music_channel = self.bot.get_channel(int(result[0]))
            print("found music_channel:", music_channel)
            
            # Delete the message and mention the music channel if it doesn't match
            if music_channel and music_channel.id != ctx.channel.id and ctx.message.author != self.bot.user:
                await self.bot.delete_message(ctx.message)
                await ctx.send(f'{ctx.author.mention} {music_channel.mention}')

        else:
            music_channel = discord.utils.get(ctx.guild.text_channels, name='music')


        # Return the current channel if we failed to find a music channel
        channel = music_channel if music_channel else ctx.channel
        print(channel)
        return channel

    @commands.command()
    async def clear(self, ctx):
        async with ctx.typing():
            if not author_voice_connected(ctx):
                response = f"{ctx.author.display_name}, you must be in a voice channel to clear the queue."
                await self.bot.send_embed(channel=ctx, text=response, thumbnail="http://i.imgur.com/go67eLE.gif")
                return

            player = await self.get_player(ctx)
            await player.queue.clear()
            await ctx.send(f"{ctx.author.display_name} cleared the queue")

    @commands.command()
    async def lyrics(self, ctx, *args):
        """ Gets lyrics from Genius """
        async with ctx.typing():
            start_time = time.perf_counter()
            # no args, lookup current song title
            if len(args) == 0:
                player = await self.get_player(ctx)
                song = player.queue.next_song
                if song is None:
                    response = f"Nothing is playing right now. Try {ctx.prefix}{ctx.command} [search query]"
                    await ctx.send(response)
                    return
                query = song.title
            else:
                query = " ".join(args)

            song = self.genius.search_song(query)
            if song is None:
                await ctx.send(f"Failed to find lyrics for '{query}'")
                return
            
            # Cut the lyrics off at 4 messages
            text = song.lyrics[:8000]
            text += f"\n\n[Click here to see the full lyrics on Genius]({song.url})"
            elapsed = round(time.perf_counter() - start_time, 2)
            footer = f"Lyrics found in {elapsed} seconds"
            if elapsed < 0.1:
                footer += " (cached!)"
            await self.bot.send_embed(channel=ctx,
                                      title=song.title,
                                      text=text,
                                      footer=footer,
                                      color=0xffff64,
                                      thumbnail=song._body.get("song_art_image_thumbnail_url"))

    @commands.command(aliases=["np"])
    async def nowplaying(self, ctx):
        player = await self.get_player(ctx)
        await player.send_now_playing(ctx)

    @commands.command()
    async def pause(self, ctx):
        if not author_voice_connected(ctx):
            response = f"{ctx.author.display_name}, you must be in a voice channel to pause the music."
            await self.bot.send_embed(channel=ctx, text=response, thumbnail="http://i.imgur.com/go67eLE.gif")
            return

        player = await self.get_player(ctx)
        await player.pause()
        if ctx.author.id is not self.bot.user.id:
            await ctx.send(f"{ctx.author.display_name} paused the music.")

    @commands.command(aliases=["p"])
    async def play(self, ctx, *args):
        """ Queues music from a Spotify link, Youtube link, or search query """
        music_channel = await self.find_music_channel(ctx)

        # Ensure the user is connected to a voice channel
        if not author_voice_connected(ctx):
            response = f"{ctx.author.mention} you must be in a voice channel to play music."
            await self.bot.send_embed(channel=music_channel, text=response, thumbnail="http://i.imgur.com/go67eLE.gif")
            return

        print("play", args, ctx)

        # Get the music player for this guild
        player = await self.get_player(ctx)

        # Iterate through each argument and figure out what the user wants
        if len(args) > 0:
            async with music_channel.typing():
                songs = await self.args_to_songs(args)

                # No results from search
                if len(songs) == 0:
                    await ctx.send(f"CSorgudan şarkı bulunamadı: '{' '.join(args)}'")
                    return

                # Response based on number of songs queued
                if len(songs) == 1:
                    response = f"Queued [{songs[0].title}]({songs[0].url})"
                else:
                    response = f"Queued {len(songs)} songs"

                # Add the songs to the queue
                await player.queue.queue(songs, user=ctx.author)
                embed = discord.Embed(description=response)
                await music_channel.send(embed=embed)
        
        # Begin playback
        await player.connect(voice_channel=ctx.author.voice.channel)
        await player.play(text_channel=music_channel)

    @commands.command(aliases=["pnext", "upnext"])
    async def playnext(self, ctx, *args):
        """ Queues music from a Spotify link, Youtube link, or search query, inserting them into the queue"""
        music_channel = await self.find_music_channel(ctx)

        # Ensure the user is connected to a voice channel
        if not author_voice_connected(ctx):
            response = f"{ctx.author.mention} you must be in a voice channel to play music."
            await self.bot.send_embed(channel=music_channel, text=response, thumbnail="http://i.imgur.com/go67eLE.gif")
            return

        # Require arguments
        if len(args) == 0:
            await music_channel.send(f"Usage: {ctx.prefix}{ctx.command} [link or query]")
            return

        # Get the music player for this guild
        player = await self.get_player(ctx)

        # Iterate through each argument and figure out what the user wants
        async with music_channel.typing():
            songs = await self.args_to_songs(args)

            # No results from search
            if len(songs) == 0:
                await music_channel.send(f"Could not find song from query: '{' '.join(args)}'")
                return

            # Response based on number of songs queued
            if len(songs) == 1:
                response = f"Queued [{songs[0].title}]({songs[0].url}) up next"
            else:
                response = f"Queued {len(songs)} songs up next"

            # Add the songs to the queue
            await player.queue.queue(songs, user=ctx.author, insert=True)
            embed = discord.Embed(description=response)
            await music_channel.send(embed=embed)
        
        # Begin playback
        await player.connect(voice_channel=ctx.author.voice.channel)
        await player.play(text_channel=music_channel)

    @commands.command(aliases=["palbum"])
    async def playalbum(self, ctx, *args):
        """ Plays an album from a search query. """
        music_channel = await self.find_music_channel(ctx)
        if len(args) == 0:
            await music_channel.send("Usage: {}playalbum [album name]".format(ctx.prefix))
            return

        if not author_voice_connected(ctx):
            response = f"{ctx.author.display_name}, you must be in a " \
                        "voice channel to play music.".format(ctx)
            await self.bot.send_embed(channel=ctx, text=response, thumbnail="http://i.imgur.com/go67eLE.gif")
            return

        query = ' '.join(args)
        try:
            album = await self.spotify.query_to_album(query)
        except IndexError:
            await music_channel.send("Failed to find album from query \"{}\".".format(query))
            return
        async with music_channel.typing():
            player = await self.get_player(ctx)
            songs = await self.spotify.album_to_songs(album_id=album['id'])

            if len(songs) > 0:
                await player.queue.queue(songs, user=ctx.author)
                response = f"Queued {len(songs)} songs from [{album['name']}]" \
                        f"(https://open.spotify.com/album/{album['id']}) by " \
                        f"[{album['artists'][0]['name']}]" \
                        f"(https://open.spotify.com/artist/{album['artists'][0]['id']})"
                await self.bot.send_embed(channel=music_channel, text=response)
            else:
                await music_channel.send(f"Failed to find songs from album [{album['name']}]" \
                            f"(https://open.spotify.com/album/{album['id']})")
                return

        # Connect to the voice channel and play
        await player.connect(ctx.author.voice.channel)
        await player.play(music_channel)

    @commands.command(aliases=["partist"])
    async def playartist(self, ctx, *args):
        """ Plays the top 10 songs of an artist. """
        async with ctx.typing():
            
            music_channel = await self.find_music_channel(ctx)

            if len(args) == 0:
                await music_channel.send(f"Usage: {ctx.prefix}playartist [artist name]")
                return

            if not author_voice_connected(ctx):
                response = "{0.author.display_name}, you must be in a " \
                           "voice channel to play music.".format(ctx)
                await self.bot.send_embed(channel=music_channel, text=response, thumbnail="http://i.imgur.com/go67eLE.gif")
                return

            player = await self.get_player(ctx)
            query = ' '.join(args)
            try:
                artist = await self.spotify.query_to_artist(query)
            except IndexError:
                await music_channel.send("Failed to find artist from query \"{}\".".format(query))
                return

            songs = await self.spotify.artist_top_songs(artist_id=artist['id'])

            if len(songs) == 0:
                response = "Failed to find songs from artist "
                response += "[{}](https://open.spotify.com/artist/{}).".format(artist['name'], artist['id'])
                await music_channel.send(response)
                return

            await player.queue.queue(songs, user=ctx.author)
            response = f"Queued {len(songs)} of [{artist['name']}]" \
                        f"(https://open.spotify.com/artist/{artist['id']})'s top tracks"
            await self.bot.send_embed(channel=music_channel, text=response)

        # Connect to the voice channel
        await player.connect(ctx.author.voice.channel)
        # Resume playback
        try:
            await player.play(music_channel)
        except Exception as e:
            await music_channel.send(f"Failed to play music in channel: {ctx.author.voice.channel}. Error: {e}")

    @commands.command()
    async def players(self, ctx):
        playing = []
        paused = []
        stopped = []
        # Traverse all music players
        print(self._music_players)
        print(type(self._music_players))
        for guild_id, player in self._music_players.items():
            # If the player exists, add to appropriate list
            if player.vc is None:
                stopped.append(player)
            else:
                if player.vc.is_playing():
                    playing.append(player)
                elif player.vc.is_paused():
                    paused.append(player)
                else:
                    stopped.append(player)

        title = "Music Player Stats"
        text = f"Playing: {len(playing)}\n"
        text += f"Paused: {len(paused)}\n"
        text += f"Stopped: {len(stopped)}\n"
        await self.bot.send_embed(channel=ctx.channel, text=text, title=title)

    @commands.command(aliases=["q"])
    async def queue(self, ctx):
        """ Displays the current song queue with emoji controls """
        music_channel = await self.find_music_channel(ctx)
        async with music_channel.typing():
            player = await self.get_player(ctx)
            await player.queue.send_queue_message(music_channel)

    @commands.command(aliases=["rm", "rem"])
    async def remove(self, ctx, *args):
        """ Removes a song from the queue. """
        async with ctx.typing():
            try:
                index = int(args[0])
            except (IndexError, ValueError):
                await ctx.send("Usage: {}remove [song index]".format(ctx.prefix))
                return

            if not author_voice_connected(ctx):
                response = "{0.author.display_name}, you must be in a " \
                            "voice channel to remove songs from the queue.".format(ctx)
                await self.bot.send_embed(channel=ctx, text=response, thumbnail="http://i.imgur.com/go67eLE.gif")
                return

            player = await self.get_player(ctx)
            try:
                song = player.queue.songs.pop(index)
                response = "Removed: **{}** [{}]({})".format(index, song.title, song.url)
                await self.bot.send_embed(channel=ctx, text=response)
                await player.queue.update_queue_message()
            except IndexError:
                await ctx.send("Failed to remove song at index {}".format(index))

    @commands.command(aliases=["loop"])
    async def repeat(self, ctx):
        """ Sets the player to repeat the entire queue. """
        async with ctx.typing():
            music_channel = await self.find_music_channel(ctx)

            if not author_voice_connected(ctx):
                response = f"{ctx.author.display_name}, you must be in a " \
                           "voice channel to loop the current song."
                await self.bot.send_embed(channel=music_channel, text=response, thumbnail="http://i.imgur.com/go67eLE.gif")
                return

            player = await self.get_player(ctx)
            player.repeat = not player.repeat
            status = "on" if player.repeat else "off"
            response = f"{ctx.author.display_name} turned **{status}** repeat for the whole queue."
            if player.repeat_one:
                player.repeat_one = False
                response += " (and turned off song looping)"
        await music_channel.send(response)
    
    @commands.command(aliases=["loopone"])
    async def repeatone(self, ctx):
        """ Sets the player to repeat the current song. """
        async with ctx.typing():
            music_channel = await self.find_music_channel(ctx)

            if not author_voice_connected(ctx):
                response = f"{ctx.author.display_name}, you must be in a " \
                           "voice channel to loop the queue."
                await self.bot.send_embed(channel=music_channel, text=response, thumbnail="http://i.imgur.com/go67eLE.gif")
                return

            player = await self.get_player(ctx)
            player.repeat_one = not player.repeat_one
            status = "on" if player.repeat_one else "off"
            response = f"{ctx.author.display_name} turned **{status}** repeat for this song."
            if player.repeat:
                player.repeat = False
                response += " (and turned off queue looping)"
        await music_channel.send(response)

    @commands.command()
    async def resume(self, ctx):
        """ Resumes playback """
        async with ctx.typing():
            if not author_voice_connected(ctx):
                response = "{0.author.display_name}, you must be in a " \
                           "voice channel to resume the music.""".format(ctx)
                await self.bot.send_embed(channel=ctx, text=response, thumbnail="http://i.imgur.com/go67eLE.gif")
                return

            music_channel = await self.find_music_channel(ctx)
            player = await self.get_player(ctx)

            if not player.queue.next_song:
                await ctx.send("Nothing left in the queue.")
                return

            player = await self.get_player(ctx)

        # Connect to the voice channel and resume playback
        await player.connect(ctx.author.voice.channel)
        await player.play(text_channel=music_channel)

    @commands.command()
    async def shuffle(self, ctx):
        """ Shuffles the queue """
        if not author_voice_connected(ctx):
            response = "{0.author.display_name}, you must be in a " \
                        "voice channel to shuffle the queue.""".format(ctx)
            await self.bot.send_embed(channel=ctx, text=response, thumbnail="http://i.imgur.com/go67eLE.gif")
            return

        music_channel = await self.find_music_channel(ctx)

        player = await self.get_player(ctx)
        await player.queue.shuffle()
        if ctx.author.id is not self.bot.user.id:
            await music_channel.send(f"{ctx.author.mention} shuffled the queue.")

    @commands.command(aliases=["next"])
    async def skip(self, ctx, *args):
        """ Skip the current song """
        if not author_voice_connected(ctx):
            response = "{0.author.display_name}, you must be in a " \
                        "voice channel to skip the song.""".format(ctx)
            await self.bot.send_embed(channel=ctx, text=response, thumbnail="http://i.imgur.com/go67eLE.gif")
            return

        player = await self.get_player(ctx)

        # Argument can be the number of songs to skip
        n_songs = 1
        if len(args) > 0:
            try:
                n_songs = int(args[0])
            except ValueError:
                await ctx.send(f"Usage: {ctx.prefix}{ctx.invoked_with} [number of songs]")
                return

        print(n_songs)
        await player.skip(n_songs)
        await player.queue.update_queue_message()

    @commands.command(aliases=["goto"])
    async def skipto(self, ctx, *args):
        """ Skip to the specified song """
        if not author_voice_connected(ctx):
            response = "{0.author.display_name}, you must be in a " \
                        "voice channel to skip multiple songs.""".format(ctx)
            await self.bot.send_embed(channel=ctx, text=response, thumbnail="http://i.imgur.com/go67eLE.gif")
            return
        
        if len(args) == 0:
            await ctx.send(f"Usage: {ctx.prefix}{ctx.invoked_with} [song index]")
            return

        try:
            index = int(args[0])
        except ValueError:
            return

        player = await self.get_player(ctx)
        await player.skipto(index)    
        await player.queue.update_queue_message()

    @commands.command(aliases=["leave", "scram", "dc", "disconnect", "end"])
    async def stop(self, ctx):
        """ Stop the player and clear the queue. """
        if not author_voice_connected(ctx):
            response = "{0.author.display_name}, you must be in a " \
                        "voice channel to stop the music.".format(ctx)
            await self.bot.send_embed(channel=ctx, text=response,
                                       thumbnail="http://i.imgur.com/go67eLE.gif")
            return

        player = await self.get_player(ctx)
        await player.stop()

    @commands.command(aliases=["stream"])
    async def video(self, ctx):
        """ Reply with a link that users may use to begin screen sharing to a channel """
        if not author_voice_connected(ctx):
            response = "{0.author.display_name}, you must be in a " \
                        "voice channel to use video.""".format(ctx)
            await self.bot.send_embed(channel=ctx, text=response, thumbnail="http://i.imgur.com/go67eLE.gif")
            return

        url = f"http://www.discordapp.com/channels/{ctx.guild.id}/{ctx.author.voice.channel.id}"
        response = f"[Click to join the video call in {ctx.author.voice.channel.name}]({url})"
        await self.bot.send_embed(channel=ctx, text=response)

    @commands.command(aliases=["v", "vol"])
    async def volume(self, ctx, *args):
        """ Sends an interactive volume message """
        if not author_voice_connected(ctx):
            response = "{0.author.display_name}, you must be in a " \
                        "voice channel to change the volume.".format(ctx)
            await self.bot.send_embed(channel=ctx, text=response, thumbnail="http://i.imgur.com/go67eLE.gif")
            return

        music_channel = await self.find_music_channel(ctx)

        player = await self.get_player(ctx)
        if len(args) > 0:
            try:
                await player.set_volume(float(args[0]))
            except:
                pass

        await player.send_volume(music_channel)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        # Ignore own reactions
        if user == self.bot.user:
            return

        # Ignore messages not sent by the bot
        if reaction.message.author != self.bot.user:
            return

        # Create a discord context to pass onto commands
        ctx = commands.Context(
            message = reaction.message,
            bot = self.bot,
            prefix = ";",
            guild = user.guild,
            author = user
        )

        # Get the music player
        player = await self.get_player(ctx)

        # -- NOW PLAYING CONTROLS --

        # QUEUE
        # -- NOW PLAYING CONTROLS --

        # QUEUE
        if reaction.emoji in '🇶':
            await self.queue.callback(self, ctx) # pylint: disable=no-member
        # PLAY (RESUME)
        elif reaction.emoji in '▶':
            await self.resume.callback(self, ctx) # pylint: disable=no-member
        # PAUSE
        elif reaction.emoji in '⏸':
            await self.pause.callback(self, ctx) # pylint: disable=no-member
        # SHUFFLE
        elif reaction.emoji in '🔀':
            await self.shuffle.callback(self, ctx) # pylint: disable=no-member
        # SKIP
        elif reaction.emoji in '⏭':
            await self.skip.callback(self, ctx) # pylint: disable=no-member
        # STOP
        elif reaction.emoji in '⏹':
            await self.stop.callback(self, ctx) # pylint: disable=no-member
        # VOLUME
        elif reaction.emoji in '🔊':
            await self.volume.callback(self, ctx) # pylint: disable=no-member

        # -- VOLUME CONTROLS --

        elif reaction.emoji in '⬇️': # volume down
            await player.set_volume(volume=player.volume - 1.75)
            await player.update_volume_message(user=user)
        elif reaction.emoji in '⬆️': # volume up
            await player.set_volume(volume=player.volume + 1.75)
            await player.update_volume_message(user=user)
        elif reaction.emoji in '⏬': # volume down+
            await player.set_volume(volume=player.volume - 8)
            await player.update_volume_message(user=user)
        elif reaction.emoji in '⏫': # volume up+
            await player.set_volume(volume=player.volume + 8)
            await player.update_volume_message(user=user)
        elif reaction.emoji in '✳': # volume reset
            await player.set_volume(volume=20)
            await player.update_volume_message(user=user)
        else:
            # Unknown emoji, do nothing
            return

        # Remove the reaction once the job is done
        try:
            await reaction.remove(user)
        except discord.errors.NotFound:
            pass

def author_voice_connected(ctx):
    """ Returns True if the author is connected to a voice channel. """
    try:
        return ctx.author is not None and ctx.author.voice is not None and ctx.author.voice.channel is not None
    except AttributeError:
        return False

def volume_bar(volume):
    """ Returns an ASCII volume bar  """
    text = ""
    vol = int(volume/4)
    text += "█" * vol
    text += "░" * (25-vol)
    return text

def setup(bot):
    cog = Music(bot)
    bot.add_cog(cog)
    print("Loaded Music cog")