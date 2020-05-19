""" Admin commands extension """
import discord
from discord.ext import commands


# Checks
async def author_is_plomdawg(ctx):
    """ Returns True if the author is plomdawg """
    return ctx.author.id == 163040232701296641

class Admin(commands.Cog):
    """ Admin cog

    Provides commands:
         ;reload ;vote
    """
    def __init__(self, bot):
        self.bot = bot
        self.bot.remove_command('help')

    @commands.command(aliases=["r"])
    @commands.check(author_is_plomdawg)
    async def reload(self, ctx):
        """ Reloads all cogs """
        async with ctx.typing():
            ctx.bot.reload_extension('cogs.admin')
            ctx.bot.reload_extension('cogs.database')
            ctx.bot.reload_extension('cogs.dota')
            ctx.bot.reload_extension('cogs.error_handler')
            ctx.bot.reload_extension('cogs.youtube')
            ctx.bot.reload_extension('cogs.music')
            print("Reloaded cogs")
            await ctx.send("Reloaded cogs.")

    @commands.command(aliases=["?"])
    async def help(self, ctx):
        """Sends help message """
        await self.bot.send_help(channel=ctx, prefix=ctx.prefix)

    @commands.command()
    async def vote(self, ctx):
        """ Sends a link to discord bot list """
        async with ctx.typing():
            url = "https://discordbots.org/bot/412809807842639883/vote"
            embed = discord.Embed()
            embed.description = "Vote for plombot on [Discord Bot List]({})".format(url)
            await ctx.send(embed=embed)

def setup(bot):
    bot.add_cog(Admin(bot))
    print("Loaded Admin cog")
