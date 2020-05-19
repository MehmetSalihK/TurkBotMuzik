import sqlite3

import discord
from discord.ext import commands
from cogs.music import Song


GUILDS = ("id INT",
          "prefix TEXT",
          "volume INT",
          "music_channel TEXT",
         )

USERS = ("id INT",
         "name TEXT",
         "opendota_id INT",
        )

SONGS = ("title TEXT",
         "duration INT",
         "plays INT",
         "query TEXT",
         "spotify_id TEXT",
         "youtube_id TEXT",
         "thumbnail TEXT",
        )

async def author_is_plomdawg(ctx):
    """ Returns True if the author is plomdawg """
    return ctx.author.id == 163040232701296641

class Database(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.database = sqlite3.connect("database.sqlite")
        self.cursor = self.database.cursor()
        self.cursor.execute(f"CREATE TABLE IF NOT EXISTS guilds ({','.join(GUILDS)})")
        self.cursor.execute(f"CREATE TABLE IF NOT EXISTS users ({','.join(USERS)})")
        self.cursor.execute(f"CREATE TABLE IF NOT EXISTS songs ({','.join(SONGS)})")

    def find_song(self, query=None, youtube_id=None, spotify_id=None):
        if query is not None:
            _query = "SELECT * FROM songs WHERE query=?"
            values = (query,)
        elif youtube_id is not None:
            _query = "SELECT * FROM songs WHERE youtube_id=?"
            values = (youtube_id,)
        elif spotify_id is not None:
            _query = "SELECT * FROM songs WHERE spotify_id=?"
            values = (spotify_id,)
        else:
            raise(Exception("find_song() called with missing parameter: query, youtube_id, or spotify_id"))

        self.cursor.execute(_query, values)
        result = self.cursor.fetchone()
        if result is None:
            return None            
    
        song = Song()
        song.title = result[0]
        song.duration = result[1]
        song.plays = result[2]
        song.query = result[3]
        song.spotify_id = result[4]
        song.youtube_id = result[5]
        song.thumbnail = result[6]
        song.url = song.youtube_url
        print(f"Found cached youtube song in database: {song.title} ({song.plays} plays)")
        return song       

    def save_song(self, song):
        query = f"SELECT * FROM songs WHERE youtube_id = ?"
        self.cursor.execute(query, (song.youtube_id,))
        result = self.cursor.fetchone()
        if result is not None:
            # Song already in database, update the play count
            query = f"UPDATE songs SET plays = plays + 1, query = ? WHERE youtube_id = ?"
            print(query)
            self.cursor.execute(query, (song.query, song.youtube_id))
            self.database.commit()
            print("updated song", song.youtube_id, song.query, result)
        else:
            query = f"INSERT INTO songs (title, duration, plays, query, spotify_id, youtube_id, thumbnail) VALUES (?,?,?,?,?,?,?)"
            self.cursor.execute(query, (song.title, song.duration, song.plays, song.query, song.spotify_id, song.youtube_id, song.thumbnail))
            self.database.commit()
            print("saved song", (song.title, song.duration, song.plays, song.query, song.spotify_id, song.youtube_id, song.thumbnail))

    def get_opendota_id(self, user):
        query = f"SELECT opendota_id FROM users WHERE id=?"
        values = (user.id, )
        self.cursor.execute(query, values)
        result = self.cursor.fetchone()
        if result is None:
            return None
        opendota_id = result[0]
        return opendota_id

    def set_opendota_id(self, user, opendota_id):
        query = f"INSERT OR REPLACE INTO users VALUES (?,?,?)"
        values = (user.id, user.display_name, opendota_id)
        self.cursor.execute(query, values)

    @commands.command()
    async def prefix(self, ctx, *args):
        """ Set the prefix for a guild """
        # Help message (no args passed)
        if len(args) == 0:
            await ctx.send(f"Usage: {ctx.prefix}{ctx.command} [new prefix]")
            return

        # TODO: Validate prefix ?
        prefix = args[0]

        # Update database
        query = f"SELECT prefix FROM guilds WHERE id = ?"
        self.cursor.execute(query, (ctx.guild.id,))
        result = self.cursor.fetchone()
        if result: # guild already in database, update ie
            query = f"UPDATE guilds SET prefix = ? WHERE id = ?"
            self.cursor.execute(query, (prefix, ctx.guild.id))
        else:
            query = f"INSERT INTO guilds (id, prefix, volume, music_channel) VALUES (?,?,?,?)"
            self.cursor.execute(query, (ctx.guild.id, prefix, 20, None))

        self.database.commit()

        # Update cached prefixes
        self.bot.prefixes[ctx.guild.id] = prefix

        # Reply with status
        await ctx.send(f"{ctx.author.display_name} changed the prefix to {prefix}")

    @commands.command()
    async def music(self, ctx, *args):
        """ Set the music channel for a guild """
    
        # Check database for current setting
        query = "SELECT music_channel FROM guilds WHERE id = ?"
        self.cursor.execute(query, (ctx.guild.id,))
        result = self.cursor.fetchone()
        print(query, "\nresult:", result)
        if result:
            if result[0] is None or int(result[0]) != ctx.channel.id:
                # Set to new channel
                query = "UPDATE guilds SET music_channel = ? WHERE id = ?"
                self.cursor.execute(query, (ctx.channel.id, ctx.guild.id))
                await ctx.send(f"{ctx.author.display_name} changed the music channel to **{ctx.channel.name}**. (Send again to unset)")
            else:
                music_channel_id = int(result[0])
                query = "UPDATE guilds SET music_channel = ? WHERE id = ?"
                print(music_channel_id, ctx.channel.id, (music_channel_id == ctx.channel.id))
                if music_channel_id == ctx.channel.id:
                    # Clear the music channel if sent in the current channel
                    self.cursor.execute(query, (None, ctx.guild.id))
                    await ctx.send(f"{ctx.author.display_name} unset the music channel.")

        else:
            # No music channel was set - set it now
            query = "INSERT INTO guilds (id, prefix, volume, music_channel) VALUES (?,?,?,?)"
            self.cursor.execute(query, (ctx.guild.id, ctx.prefix, 20, ctx.channel.id))
            await ctx.send(f"{ctx.author.display_name} set **{ctx.channel.name}** as the music channel. (Send again to unset)")
        
        self.database.commit()
    
    @commands.command()
    async def top(self, ctx, *args):
        """ Sends the top 10 most played songs"""
        async with ctx.typing():
            query = f"SELECT youtube_id, title, plays FROM songs ORDER BY plays DESC LIMIT ?"
            self.cursor.execute(query, (10,))
            songs = self.cursor.fetchall()
            text = ""
            for song in songs:
                (youtube_id, title, plays) = song
                text += f"[{title}](https://youtu.be/{youtube_id}) ({plays} plays)\n"
            await self.bot.send_embed(ctx, title="Most Played Songs", text=text)

    @commands.command()
    @commands.check(author_is_plomdawg)
    async def clear_plays(self, ctx, *args):
        """ Reset the plays for all songs """
        query = f"UPDATE songs SET plays = 0"
        self.cursor.execute(query)
        self.database.commit()
        await ctx.send("Set plays to 0 for all songs.")

    @commands.command(aliases=["rm_song"])
    @commands.check(author_is_plomdawg)
    async def remove_song(self, ctx, *args):
        """ Removes a song from the database """
        if len(args) == 0:
            await ctx.send(f"Usage: {ctx.prefix}{ctx.command} [YouTube ID]")
            return

        youtube_id = args[0]
        song = self.find_song(youtube_id=youtube_id)

        if song is None:
            await ctx.send(f"Failed to find {youtube_id} in the database.")
            return

        query = "DELETE FROM songs WHERE youtube_id=?"
        self.cursor.execute(query, (youtube_id,))
        self.database.commit()

        await ctx.send(f"Deleted {song[0]} from the database.")


def setup(bot):
    print("Loading Database cog")
    bot.add_cog(Database(bot))
    print("Loaded Database cog")
