from discord.ext import commands
from modules.env import SECRETS

bot = commands.Bot(command_prefix='!')

@bot.event
async def on_ready():
    print('Ready')

def main():
    bot.load_extension('cogs.polls')
    bot.run(SECRETS['DISCORD_API_KEY'])

if __name__ == '__main__':
    main()
