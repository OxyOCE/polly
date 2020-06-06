import discord
from discord.ext import commands

def gen_poll_embed(poll_args):
    desc_str = ""
    react_char = '\U0001f1e6'
    for arg_iter in range(1, len(poll_args)):
        poll_arg_lf_sanitised = poll_args[arg_iter].replace("\n", " ")
        desc_str += f'{react_char} {poll_arg_lf_sanitised}\n'
        react_char = chr(ord(react_char) + 1)

    return discord.Embed(
        title=poll_args[0],
        description=desc_str
    )

class Polls(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='poll', aliases=['p'])
    async def create_poll(self, ctx, *poll_args: str):
        """Creates a new poll
        $poll "title" "opt-a" "opt-b" ...
        """

        if len(poll_args) < 2:
            await ctx.send('A poll needs at least one option!')
        elif len(poll_args) > 21:
            await ctx.send('Sorry, `$poll` only supports 20 options max!')
        else:
            async with ctx.typing():
                poll_embed=gen_poll_embed(poll_args)
                result_msg = await ctx.send(embed=poll_embed)

                poll_embed.add_field(name="Poll Reference", value=result_msg.id)
                await result_msg.edit(embed=poll_embed)

                react_char = '\U0001f1e6'
                for arg_iter in range(1, len(poll_args)):
                    await result_msg.add_reaction(react_char)
                    react_char = chr(ord(react_char) + 1)

def setup(bot):
    bot.add_cog(Polls(bot))
