from discord.ext import commands
import discord
import emoji
from discord.utils import escape_markdown
from textwrap import wrap
import pandas as pd
import matplotlib.pyplot as plt
import io
import datetime

def gen_yticks(max_pt):
    """Generates an array of y-axis ticks in integers - step is determined by the largest data point"""
    if max_pt <= 10:
        step = 1
    elif max_pt <= 50:
        step = 5
    elif max_pt <= 100:
        step = 10
    elif max_pt <= 500:
        step = 50
    else:
        step = 100

    return range(0, max_pt + step, step)

def trunc_label(label, num_opts=None, max_lines=None, max_length=25):
    """Breaks the label up into 25 character max lines."""
    """If the label space is too small, only some lines will be append and the rest will be represented with ..."""
    if max_lines is None:
        if num_opts <= 4:
            max_lines = 4
        elif num_opts <= 6:
            max_lines = 3
        elif num_opts <= 8:
            max_lines = 2
        else:
            max_lines = 1

    res = wrap(label, max_length)
    res_full_length = len(res)
    res = res[:min(res_full_length, max_lines)]

    return "\n".join(res) + ("..." if res_full_length > max_lines else "")

def gen_poll_options(poll):
    for option in poll.embeds[0].description.split("\n"):
        key = emoji.emojize(option[:option.find(' ')], use_aliases=True)
        desc = option[option.find(' ') + 1:]

        # If polls options don't match reactions, list has been messed with
        reaction = next((r for r in poll.reactions if r.emoji == key), None)
        if reaction is None:
            raise KeyError()

        yield key, desc, reaction

async def gen_polls_from_ids(ctx, poll_ids, id_fetch_point):
    for pid in poll_ids:
        try:
            poll = await id_fetch_point.fetch_message(pid)
        except discord.NotFound:
            await ctx.send(f'Couldn\'t find poll: `{pid}`')
            continue
        except discord.HTTPException:
            await ctx.send(f'`{pid}` is not a valid poll id!')
            continue

        if len(poll.embeds) < 1:
            await ctx.send(f'Couldn\'t find embed for poll: `{pid}`')
            continue

        yield poll, pid

async def get_poll_context_channel(ctx, poll_ids):
    if len(poll_ids) > 0 and poll_ids[0][0] == 'c':
        id_fetch_point = ctx.bot.get_channel(int(poll_ids[0][1:]))
        if id_fetch_point is None:
            await ctx.send(f'`{poll_ids[0][1:]}` is not a valid channel id!')
            return None, None

        poll_ids = poll_ids[1:]
    else:
        id_fetch_point = ctx.channel

    if len(poll_ids) < 1:
        await ctx.send('No poll reference provided!')
        return None, None

    return id_fetch_point, poll_ids

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

    @commands.command(name='results', aliases=['r'])
    async def poll_list_respondents_by_option(self, ctx, *poll_ids: str):
        """Lists a poll's respondents by the options they chose"""

        id_fetch_point, poll_ids = await get_poll_context_channel(ctx, poll_ids)
        if id_fetch_point is None:
            return

        async with ctx.typing():
            async for poll, pid in gen_polls_from_ids(ctx, poll_ids, id_fetch_point):
                result_embed = discord.Embed(
                    title=poll.embeds[0].title
                )

                try:
                    for _, desc, reaction in gen_poll_options(poll):
                        respondents = []
                        async for user in reaction.users():
                            if not user.bot:
                                user_line = escape_markdown(user.name) + "#" + user.discriminator
                                user_nick = getattr(user, 'nick', None)
                                if user_nick is not None:
                                    user_line += " _" + escape_markdown(user_nick) + "_"
                                respondents.append(user_line)

                        if len(respondents) == 0:
                            respondents = "None"
                        else:
                            respondents = "\n".join(respondents)

                        field_title = reaction.emoji + " " + desc
                        result_embed.add_field(name=field_title, value=respondents, inline=False)
                except KeyError:
                    await ctx.send(f'Error processing poll: `{pid}`')
                    continue

                await ctx.send(embed=result_embed)

    @commands.command(name='image', aliases=['i', 'id', 'image-dark'])
    async def collate_poll(self, ctx, *poll_ids: str):
        """Summarises the given poll references
        Use $id for dark theme
        Use $i c<channel-id> <poll-args>... to specify a channel to pull from
        """

        id_fetch_point, poll_ids = await get_poll_context_channel(ctx, poll_ids)
        if id_fetch_point is None:
            return

        async with ctx.typing():
            async for poll, pid in gen_polls_from_ids(ctx, poll_ids, id_fetch_point):
                poll_labels = []
                poll_results = []
                poll_title = trunc_label(poll.embeds[0].title, max_lines=2, max_length=50)

                try:
                    for _, desc, reaction in gen_poll_options(poll):
                        poll_labels.append(trunc_label(desc, len(poll.reactions)))
                        poll_results.append(reaction.count - 1)
                except KeyError:
                    await ctx.send(f'Error processing poll: `{pid}`')
                    continue

                data = pd.Series(poll_results, index=poll_labels)

                axes = data.plot.bar(title=poll_title, x='options', color=plt.cm.tab10(range(len(data))))
                axes.set_ylabel('Respondents')

                if ctx.invoked_with in ['id', 'image-dark']:
                    line_colors = "#FFFFFF"

                    axes.spines['bottom'].set_color(line_colors)
                    axes.spines['top'].set_color(line_colors)
                    axes.spines['left'].set_color(line_colors)
                    axes.spines['right'].set_color(line_colors)

                    axes.tick_params(colors=line_colors)

                    axes.yaxis.label.set_color(line_colors)
                    axes.xaxis.label.set_color(line_colors)

                    axes.title.set_color(line_colors)

                    axes.set_facecolor("#2C2F33")

                    bg_color = "#2C2F33"
                    bar_top_color = line_colors
                else:
                    bg_color = "#FFFFFF"
                    bar_top_color = "k"  # aka black

                _, top_ylim = plt.ylim()
                top_ylim *= 1.02
                plt.ylim(bottom=0, top=top_ylim)

                plt.yticks(gen_yticks(max(poll_results)))  # Appropriate tick spacing for number of respondents
                plt.xticks(rotation=45)

                # Adds number of respondents at top of bars
                for x, y in enumerate(poll_results):
                    axes.text(x, y, str(y), ha='center', va='bottom', color=bar_top_color)

                plt.tight_layout()  # Ensures label text is not cut off

                png_wrapper = io.BytesIO()
                plt.savefig(png_wrapper, format='png', facecolor=bg_color)
                png_wrapper.seek(0)

                dt = datetime.datetime
                filename = "gp-poll-" + pid + "-" + dt.strftime(dt.utcnow(), "%Y-%m-%d-%H-%M-%S") + ".png"
                await ctx.send(file=discord.File(png_wrapper, filename=filename))

                png_wrapper.close()
                plt.close()

def setup(bot):
    bot.add_cog(Polls(bot))
