from discord.ext import commands
from modules.env import SECRETS

bot = commands.Bot(command_prefix='!')

@bot.event
async def on_ready():
    print('Ready')

bot.run(SECRETS['DISCORD_API_KEY'])
