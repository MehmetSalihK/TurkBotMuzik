""" Error handler that PMs me with any unhandled errors """
import traceback
import sys
import discord
from discord.ext import commands

def _create_error_embed(ctx, error) -> discord.Embed:
    """ Creates a nicely formatted embed for an error """
    embed = discord.Embed()

    # Add the title
    title = f"{ctx.prefix}{ctx.command} failed"
    if ctx.guild is not None:
        title += f" in [{ctx.guild.name}]"
    embed.title = title

    # Command with prefix and arguments
    embed.add_field(name="Command", value=f"**{ctx.message.content}**")

    # Who did this
    if ctx.author is not None:
        embed.add_field(name="Who", value=ctx.author.display_name)
    
    # Error message
    embed.add_field(name="Error Message", value=error)

    return embed

class ErrorHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _log_error(self, ctx, error):
        """ Pretty logs an error """
        print(ctx)
        print(error)
        print(error.original)
        
        channel = self.bot.get_channel(711552593574363190) #errors in plombot dev
        embed = _create_error_embed(ctx, error)

        # Try to send error message to the channel
        try:
            response = f"Command {ctx.prefix}{ctx.command} failed: {error} ({error.original}). plomdawg adlı kullanıcıya bildirimde bulunuldu ve sorunun çözümü için çalışıyor. Destek Sunucusu: https://discord.gg/wvEQMUd"
            await ctx.channel.send(response)
        except:
            pass

        # Give it a full send
        print(f"Sending error to {channel.name}")
        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """ Triggered if a command raises an error.
        Args:
            ctx   : commands.Context
            error : Exception
        """
        plom = self.bot.get_user(163040232701296641)

        # Ignore command not found errors
        if isinstance(error, commands.CommandNotFound):
            return

        # Errors within commands
        if isinstance(error, commands.CommandInvokeError):
            # Ignore NotFound errors (trying to delete an already deleted message)
            if isinstance(error.original, discord.errors.NotFound):
                print("ignoring notfound error")
                return

            # Forbidden (missing permissions)
            elif isinstance(error.original, discord.errors.Forbidden):
                # Figure out which permission is missing
                permissions = ctx.channel.permissions_for(ctx.me)
                if not permissions.send_messages:
                    await ctx.author.send(f"Hey! I need permission to **send messages** to channel {ctx.channel}.")
                elif not permissions.embed_links:
                    await ctx.send(f"{ctx.author.mention} I need permission to **embed links** in this channel.")
                elif not permissions.add_reactions:
                    await ctx.send(f"{ctx.author.mention} I need permission to **add reactions** in this channel.")
                elif not permissions.manage_messages:
                    await ctx.send(f"{ctx.author.mention} I need permission to **manage messages** in this channel.")
                else:
                    # Unhandled error - log it
                    await self._log_error(ctx, error)
            else:
                await self._log_error(ctx, error)
        else:
            await self._log_error(ctx, error)


def setup(bot):
    bot.add_cog(ErrorHandler(bot))
    print("Loaded Error Handler cog")
