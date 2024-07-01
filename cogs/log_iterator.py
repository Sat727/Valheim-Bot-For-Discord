from discord.ext import commands, tasks
from config import Config
import discord
from os import kill, path
#from utils.locations import Locations
import aiofiles, asyncio, logging, re
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
        #self.fetch_logs.start()

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
            match = None
            players = None
            self.statuschannel = self.bot.get_channel(Config.STATUS_CHANNEL)
            self.activity = self.bot.get_channel(Config.ACTIVITY_CHANNEL)
            if len(data.execute("SELECT * FROM initialized").fetchall()) == 0:
                print("Initializing")
                message = await self.statuschannel.send("Initializing bot...")
                data.execute("INSERT INTO initialized (message_id) VALUES (?)", (message.id,))
                print("Initialized message ID")
                player_data.commit()
            else:
                print("Message already initialized")
            self.message = await self.statuschannel.fetch_message(data.execute("SELECT * FROM initialized").fetchone()[0])
            logging.info(f"Checking logfile")
            fp = path.abspath(
                path.join(path.dirname(__file__), "..", "logs", "server_log.txt")
            )

            if 'valheim' not in self.reported:
                self.reported['valheim'] = []
            print(fp)
            async with aiofiles.open(fp, mode="r") as f:
                async for line in f:
                    try:
                        players = re.search(r'now (\d+) player\(s\)', line).group(1)
                    except Exception:
                        pass
                    try:
                        match = re.search(r'join code (\d+)', line).group(1)
                        self.joincode = match
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
                        if name not in self.connected_list:
                            id = join_event.group(3)
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
                            print(f"{name} Likely died.")

                    #match = re.search(regex_pattern, string)


                    if "Starting server" in line:
                            if self.last_log['valheim'] != str(line):
                                if await self.new_logfile(fp):
                                    self.last_log['valheim'] = str(line)
                                    self.reported['valheim'] = []
                    #try:
                    #    self.player = re.search(r'<color=orange>(.*?)<\/color>', line).group(1)
                    #    try:
                    #        if self.queuejoin == True:
                    #            await self.activity.send(f"{self.player} has joined the server")
                    #            self.queuejoin = False
                    #    except Exception:
                    #        pass
                    #except Exception:
                    #    pass
                    #join_match = re.search(r'Player joined', line)
                    #leave_match = re.search(r'Player connection lost', line)  
#   
                    #if join_match:
                    #    self.queuejoin = True
                    #if leave_match:
                    #    await self.activity.send(f"Someone has left the server")

                    self.reported['valheim'].append(str(line))
                try:
                        await self.message.edit(content=f"""
Server Name: Valheim Server 
Total Players: {players if players else ''}
Join Code: {match if match else ''}
Password: valfam""")
                except Exception as e:
                    print("Something went wrong when updating status message")
                    print(e)
                self.FirstTime = False
        except Exception as e:
            print("An error occurred")
            print(e)
        finally:
            self.reported['valheim'].append(str(line))

                    


async def setup(bot):
    await bot.add_cog(ServerFeed(bot))
