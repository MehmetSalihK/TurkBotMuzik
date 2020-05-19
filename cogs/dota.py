""" Dota 2 cog """
import asyncio
import json
from urllib.parse import quote

import discord
import opendota2py
import requests
from discord.ext import commands

GAME_MODES = {
    1: "All Pick",
    2: "Captain's Mode",
    3: "Random Draft",
    4: "Single Draft",
    5: "All Random",
    6: "Intro",
    11: "Mid Only",
    12: "Least Played",
    13: "Limited Heroes",
    15: "Custom",
    16: "Captain's Draft",
    18: "Ability Draft",
    22: "Turbo",
    23: "Turbo",
}


async def send_help(ctx):
    embed = discord.Embed()
    embed.title = "Dota commands"
    embed.description = f"""**{ctx.prefix}dota quiz** *Play the shopkeeper's quiz!*
                            **{ctx.prefix}dota match** *See the results of your last game.*
                            **{ctx.prefix}dota id [id]** *Add your opendota account ID.*
                            **{ctx.prefix}dota search [username]** *Find your opendota account ID.*"""
    embed.set_thumbnail(url="https://png.pngtree.com/svg/20170427/dota_907941.png")
    await ctx.send(embed=embed)

def generate_stats(team):
    """ Generates the stats used in the dota match summary 
    
    :param team: a subset of match.players
    :returns: a formatted text field with interesting stats
    """
    stats = ""
    legs = 0
    stacks = 0
    pings = 0
    obs_placed = 0
    sen_placed = 0

    for player in team:
        hero = opendota2py.Hero(player['hero_id'])
        legs += hero.legs
        camps = player.get('camps_stacked', 0)
        stacks += camps if camps is not None else 0
        ping = player.get('pings', 0)
        pings += ping if ping is not None else 0
        obs = player.get('obs_placed', 0)
        obs_placed += obs if obs is not None else 0
        sen = player.get('sen_placed', 0)
        sen_placed += obs if obs is not None else 0

    stats = f"**{stacks}** stacks\n"
    stats += f"**{pings}** pings\n"
    stats += f"**{legs / 5}** avg. legs\n"
    stats += f"**{obs_placed}** wards\n"
    stats += f"**{sen_placed}** sentries\n"

    return stats


class Dota(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.quizzes = {}  # key = guild.id, value = Bool
        self.args = ('quiz',) # cache last args for NEW button
        self.database = bot.get_cog('Database')

    # ;dota match
    async def last_match(self, ctx):
        """ Sends info about the user's last match """
        if len(ctx.message.mentions) > 0:
            user = ctx.message.mentions[0]
        else:
            user = ctx.author

        # Get opendota ID from database
        opendota_id = self.database.get_opendota_id(user)
        
        # Missing from database, tell the user to fix it
        if opendota_id is None:
            response = f"Missing player ID for {user.mention}. You can add it with the command: `{ctx.prefix}dota search [username]`"
            await ctx.send(response)
            return

        #async with ctx.typing:
        # Find the player's last match
        print(f"Searching for {user.display_name}'s last match ({opendota_id})")
        player = opendota2py.Player(opendota_id)
        print(f"  Refreshing user data")
        player.refresh()
        print(f"  Found: {player}")
        match = player.recent_matches[0]
        print(f"  Found: {match}")
        hero = opendota2py.Hero(match.hero_id)
        print(f"  Found: {hero}")
        
        # Add team and game outcome to title
        if match.player_slot < 5:
            title = "Radiant"
            if match.radiant_win:
                title = f" Victory"
                color = 0x00FF00
            else:
                title = f" Loss"
                color = 0xFF0000
        else:
            title = "Dire"
            if match.radiant_win:
                title = f" Loss"
                color = 0xFF0000
            else:
                title = f" Victory"
                color = 0x00FF00

        # Add hero name and duration to title
        minutes = match.duration // 60
        seconds = match.duration % 60
        title += f" as {hero.localized_name}!"
        title += f" ({minutes}:{seconds})"

        radiant = match.players[:5]
        dire = match.players[5:]

        # Throw all the data into an embed
        embed = discord.Embed(title=title, color=color)
        embed.set_thumbnail(url=hero.thumbnail)

        ## Stats 
        kda = f"**{match.kills}**/**{match.deaths}**/**{match.assists}**"
        embed.add_field(name="K/D/A", value=kda)
        game_mode = f"**{GAME_MODES.get(match.game_mode)}**"
        embed.add_field(name="Game Mode", value=game_mode)

        ## Score (Kills) 
        score = f"**{match.radiant_score}** - **{match.dire_score}**"
        embed.add_field(name="Score", value=score)

        ## Radiant v Dire stats
        radiant_stats = generate_stats(radiant)
        dire_stats = generate_stats(dire)
        embed.add_field(name="Radiant", value=radiant_stats)
        embed.add_field(name="Dire", value=dire_stats)

        ## Top 5 words said
        #words = sorted(match.all_word_counts.items(), key=lambda x: x[1], reverse=True)
        #text = ""
        #if len(words) > 5:
        #    words = words[:5]
        #print(words)
        #for word in words:
        #    text += f'{word[0]}" x {word[1]}\n'
        #if text != "":
        #    embed.add_field(name="All Chat", value=text, inline=False)

        ## Link to opendota.com
        text = f"View the full match analysis on [opendota]({match.url})"
        embed.add_field(name="Full results", value=text, inline=False)

        await ctx.send(embed=embed)

    # ;dota search [username]
    async def search_opendota(self, ctx, args):
        """ Searches opendota for the username given """
        if len(args) < 2:
            await ctx.send(f"Usage: {ctx.prefix}{ctx.command} [username]")
            return

        # Search opendota api
        query = " ".join(args[1:])
        url = (f"https://api.opendota.com/api/search?q={quote(query)}")
        response = requests.get(url)
        results = json.loads(response.text)

        # Send search results
        #output = ""
        messages = []
        n = 4
        for i, result in enumerate(results[:n]):
            output = f"{i+1}. {result['personaname']} {result['account_id']}"
            m = await self.bot.send_embed(ctx, text=output, thumbnail=result['avatarfull'])
            messages.append(m)

        search_url =f"https://www.opendota.com/search?q={quote(query)}"
        text = f"""**Reply with a number from 1-{n} to select your account.**

                    If you don't see your account, get your ID from [opendota]({search_url}) then reply with {ctx.prefix}dota id [id]"""
        m = await self.bot.send_embed(ctx, text=text)

        messages.append(m)

        # Wait for user response
        def check(msg):
            if msg.author == ctx.author:
                try:
                    if (int(msg.content)) in range(1, n+1):
                        return True
                    else:
                        return False
                except:
                    return False
            else:
                return False

        try:
            correct_msg = await ctx.bot.wait_for('message', check=check, timeout=30)
            result = results[:n][int(correct_msg.content)-1]
            response = await ctx.send(f"Selected {int(correct_msg.content)}. ({result['personaname']}) Saving account id {result['account_id']}.")
            # Save it to the database
            self.database.set_opendota_id(ctx.author, result['account_id'])
            await self.bot.add_reactions(response, "👍")

            # Delete messages
            for i, message in enumerate(messages):
                if int(correct_msg.content) is not i+1:
                    await self.bot.delete_message(message)

        except asyncio.TimeoutError:
            await ctx.send(f"No response received. ({query} search)")
            # Delete messages
            for message in messages:
                await self.bot.delete_message(message)

    # ;dota id [id]
    async def opendota_id(self, ctx, args):
        try:
            print("args:", args, "args[1]", args[1])
            opendota_id = int(args[1])
            # Save it to the database
            print(f"saving {ctx.author.display_name}'s opendota id: {opendota_id}")
            self.database.set_opendota_id(ctx.author, opendota_id)
            await ctx.send(f"Set opendota account ID to {opendota_id}.")
        except (IndexError, ValueError):
            text = f"""Usage: **{ctx.prefix}{ctx.command} [ID]**

                       Get your account ID from [opendota](https://www.opendota.com), or use: {ctx.prefix}dota search [username]"""
            await self.bot.send_embed(ctx, text=text)

    # COMMANDS

    # ;dota
    @commands.command()
    async def dota(self, ctx, *args):
        if len(args) == 0:
            await send_help(ctx)
        else:
            command = args[0].lower()
            if command == 'id':
                await self.opendota_id(ctx, args)
            elif command == 'quiz':
                title = "The shopkeeper's quiz has moved!"
                url = "https://discordapp.com/oauth2/authorize" \
                      "?client_id=650077099587141632&scope=bot&permissions=27712"
                text = f"Invite [**DotA Heroes**]({url}) then use command **dquiz**"                
                await self.bot.send_embed(ctx, title=title, text=text)
            elif command == 'match':
                await self.last_match(ctx)
            elif command == 'search':
                await self.search_opendota(ctx, args)
            else:
                await send_help(ctx)

def setup(bot):
    print("Loading Dota cog")
    bot.add_cog(Dota(bot))
