from discord.ext import commands, tasks
from config import Config
import discord
from os import kill, path
#from utils.locations import Locations
import aiofiles, asyncio, logging, re, os
from config import Config
import sqlite3, datetime
from datetime import timedelta
player_data = sqlite3.connect("db/playerdata.db")
data = player_data.cursor()
data.execute("CREATE TABLE IF NOT EXISTS playerdata (id, name, deaths, timeplayed)")
data.execute("CREATE TABLE IF NOT EXISTS initialized (message_id)")
player_data.commit()
class ServerFeed(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.reported = {}
        self.last_log = {}
        self.FirstTime = True
        self.server_iterator = 0
        self.testing = False
        self.joincode = None
        self.player = ''
        self.players = 0
        self.connected_list = []
        logging.basicConfig(level=logging.INFO)
        self.assign = False
        self.playfabid = 0  
        self.queuejoin = True
        self.previous_data = ''

    @commands.Cog.listener()
    async def on_ready(self):
        logging.info("Started bot")
        self.fetch_logs.start()

    @staticmethod
    async def new_logfile(fp) -> bool:
        async with aiofiles.open(fp, "r") as f:
            text = await f.read()
            logs = len(re.findall("Starting server", text))

        return logs == 1

    async def run_loop(self):
        coros = []
        coros.append(self.check_log()) 
        await asyncio.gather(*coros)

    @tasks.loop(seconds=5)
    async def fetch_logs(self):

        await self.run_loop()

    async def check_log(self):
        try:
            code = None
            players = None
            self.statuschannel = self.bot.get_channel(Config.STATUS_CHANNEL)
            self.activity = self.bot.get_channel(Config.ACTIVITY_CHANNEL)
            self.deathfeed = self.bot.get_channel(Config.DEATH_CHANNEL)
            if len(data.execute("SELECT * FROM initialized").fetchall()) == 0:
                print("Initializing")
                message = await self.statuschannel.send("Initializing bot...")
                data.execute("INSERT INTO initialized (message_id) VALUES (?)", (message.id,))
                print("Initialized message ID")
                player_data.commit()
            #else:
                #print("Message already initialized")
            self.message = await self.statuschannel.fetch_message(data.execute("SELECT * FROM initialized").fetchone()[0])
            #logging.info(f"Checking logfile")
            fp = path.abspath(
                path.join(path.dirname(__file__), "..", "logs", "server_log.txt")
            )

            if 'valheim' not in self.reported:
                self.reported['valheim'] = []
            #print(fp)
            async with aiofiles.open(fp, mode="r") as f:
                async for line in f:
                    try:
                        players = re.search(r'now (\d+) player\(s\)', line).group(1) if players != re.search(r'now (\d+) player\(s\)', line).group(1) else players
                    except Exception:
                        pass
                    try:
                        code = re.search(r'join code (\d+)', line).group(1)
                        self.joincode = code
                    except Exception:
                        pass
                    if self.FirstTime == True:
                        self.reported['valheim'].append(str(line)) 

                    if str(line) in self.reported['valheim']:
                        continue
                    print(line)
                    join_event = re.search(r'(\d{2}:\d{2}:\d{2}).*?from\s+([^:]+?)\s*:\s*(-?\d+)(?::\d+)?$', line)
                    leave_event = re.search(r'owner (-?\d+)', line)
                    if leave_event:
                        print("Detected leave event")
                        id = leave_event.group(1)
                        print(str(int(id)))
                        name = data.execute("SELECT name FROM playerdata WHERE id = ?", (id,)).fetchone()[0]
                        if name in self.connected_list:
                            await self.activity.send(f"{name} has left the server!")
                            self.connected_list.remove(name)
                    if join_event:
                        time = join_event.group(1)
                        name = join_event.group(2)
                        id = join_event.group(3)
                        if name not in self.connected_list:
                            self.connected_list.append(name)
                            if len(data.execute("SELECT * FROM playerdata WHERE name = ?", (name,)).fetchall()) < 1:
                                data.execute("INSERT INTO playerdata (id, name, deaths, timeplayed) VALUES (?, ?, ?, ?)", (id, name, 0, int(datetime.datetime.now().timestamp())))
                                print("Appended new user to database")
                            else:
                                data.execute("UPDATE playerdata SET id = ? WHERE name = ?", (id, name))
                                print("Updated player in database")
                            player_data.commit()
                            await self.activity.send(f"{name} has joined the server!")
                        else:
                            data.execute('UPDATE playerdata SET deaths = deaths + 1 WHERE id = ?', (id,))
                            await self.deathfeed.send(f"{name} died!")
                            player_data.commit()

                    if "Starting server" in line:
                            if self.last_log['valheim'] != str(line):
                                if await self.new_logfile(fp):
                                    self.last_log['valheim'] = str(line)
                                    self.reported['valheim'] = []

                    self.reported['valheim'].append(str(line))
                try:
                        # To get password, open the only bat file in the directory, and read the password if it exists.
                        file = None
                        for i in os.listdir('./'):
                            if i.endswith('.bat'):
                                file = i
                        password = None
                        name = None
                        for i in open(file).readlines():
                            #print(i)
                            if str(i).startswith('valheim_server'):
                                modifiers = re.findall(r'-modifier\s+(\w+\s+\w+)', i)
                                name_search = re.search(r'-name\s+"([^"]+)"', i)
                                password_search = re.search(r'-password\s+"([^"]+)"', i)
                                if password_search:
                                    password = password_search.group(1)
                                if name_search:
                                    name = name_search.group(1)
                        server_data = [name, password, modifiers]
                        if server_data != self.previous_data:
                            if name == None:
                                print("Could not find bat file containing server information. Closing...")
                                exit()
                            embed = discord.Embed(title=server_data[0], description=f'Join code: ' + code if code else '', color=discord.Color.green())
                            embed.add_field(name="Players",value=f"Players online {players}")
                            if password:
                                embed.add_field("Password: ",value=password)
                            if modifiers:
                                modifier_data = ''
                                for i in modifiers:
                                    temp_data = i.split(' ')
                                    modifier_data += f'```{temp_data[0]}: {temp_data[1]}\n```'
                                embed.add_field(name="Modifier Data",value=modifier_data)
                            #content = f"Server Name: {server_data[0] if server_data[0] else Config.SERVER_NAME}\nTotal Players: {players if players else ''}\nJoin Code: {code if code else ''}{'|backspace|Password:  '+ server_data[1] if server_data[1] else ''}".replace('|backspace|','\n')
                            #print(self.message.content)
                            #print(content)
                            await self.message.edit(embed=embed, content=None)
                            print("Updated status message")
                            self.previous_data = server_data
                            if self.FirstTime == True:
                                self.FirstTime = False
                except Exception as e:
                    print("Something went wrong when updating status message")
                    print(e)
        except Exception as e:
            print("An error occurred")
            print(e)
        finally:
            self.reported['valheim'].append(str(line))

                    


async def setup(bot):
    await bot.add_cog(ServerFeed(bot))
