import socket
import threading
import json
import discord
from discord.ext import commands, tasks
import asyncio
import configparser


config = configparser.ConfigParser()
config.read('master_config.ini')

TOKEN = config['Discord']['TOKEN']
GUILD_ID = int(config['Discord']['GUILD_ID'])
CHANNEL_ID = int(config['Discord']['CHANNEL_ID'])
POOL_SIZE = int(config['Server']['POOL_SIZE'])
LISTEN_PORT = int(config['Server']['LISTEN_PORT'])


with open('code.json', 'r') as file:
    code_data = json.load(file)
    all_codes = code_data['codes']

code_pools = [all_codes[i:i + POOL_SIZE] for i in range(0, len(all_codes), POOL_SIZE)]
client_sockets = {}
pending_codes = {}
used_codes = {}
used_codes_lock = threading.Lock()


client_names = {}

intents = discord.Intents.default()
intents.typing = False
intents.presences = False

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name} - {bot.user.id}')

    global status_message_id
    status_channel = bot.get_channel(CHANNEL_ID)
    status_message = None

    try:
        status_message = await status_channel.fetch_message(status_message_id)
        await status(None)
    except discord.HTTPException as e:
        print(f"An error occurred while fetching the status message: {e}")
        async for message in status_channel.history(limit=None):
            await message.delete()

    if status_message:
        status_message_id = status_message.id
    global guild
    guild = bot.get_guild(GUILD_ID)

status_message_id = None

@bot.command()
@commands.guild_only()
async def status(ctx):
    online_clients = len(client_sockets)
    total_used_codes = sum(len(codes) for codes in used_codes.values())
    
    used_percentage = (total_used_codes / len(all_codes)) * 100

    message = (
        f"📊 **Status Report** 📊\n\n"
        f" {':green_circle:' if online_clients > 0 else ':red_circle:'} Online Clients: {online_clients}\n"
        f"':bar_chart:' Used Code Percentage: {used_percentage:.2f}%\n"
    )

    for client_id, used_code_count in used_codes.items():
        client_name = client_names.get(client_id, 'unknown')
        client_used_percentage = (len(used_code_count) / len(all_codes)) * 100
        client_info = f"• {client_name}: Used {len(used_code_count)} codes ({client_used_percentage:.2f}%)"
        message += f"\n{client_info}"

    global status_message_id
    if status_message_id:
        status_message = await bot.get_channel(CHANNEL_ID).fetch_message(status_message_id)
        await status_message.edit(content=message)
    else:
        status_message = await bot.get_channel(CHANNEL_ID).send(message)
        status_message_id = status_message.id


async def send_initial_status():
    await bot.wait_until_ready()

    global status_message_id
    status_channel = bot.get_channel(CHANNEL_ID)

    async for message in status_channel.history(limit=None):
        await message.delete()

    message = await status_channel.send("Initializing...")
    status_message_id = message.id

    while True:
        online_clients = len(client_sockets)
        total_used_codes = sum(len(codes) for codes in used_codes.values())

        used_percentage = (total_used_codes / len(all_codes)) * 100

        content = (
            f"📊 **Status Report** 📊\n\n"
            f" {':green_circle:' if online_clients > 0 else ':red_circle:'} Online Clients: {online_clients}\n"
            f"':bar_chart:' Used Code Percentage: {used_percentage:.2f}%\n"
        )

        for client_id, used_code_count in used_codes.items():
            client_name = client_names.get(client_id, 'unknown')
            client_used_percentage = (len(used_code_count) / len(all_codes)) * 100
            client_info = f"• {client_name}: Used {len(used_code_count)} codes ({client_used_percentage:.2f}%)"
            content += f"\n{client_info}"

        try:
            message = await status_channel.fetch_message(status_message_id)
            await message.edit(content=content)
        except discord.NotFound:
            message = await status_channel.send(content)
            status_message_id = message.id

        await asyncio.sleep(15)




@tasks.loop(seconds=15)
async def update_status():
    await bot.wait_until_ready()
    await status(None)
    
    global status_message_id
    if status_message_id:
        status_message = await bot.get_channel(CHANNEL_ID).fetch_message(status_message_id)

def process_request(client_socket, client_id, request_data):
    global client_names

    if request_data == 'get_codes':
        send_codes(client_socket, client_id)
    elif request_data.startswith('confirm_code:'):
        confirm_code_used(client_id, request_data.split(':')[1])
    elif request_data.startswith('set_name:'):
        set_client_name(client_id, request_data.split(':')[1])
    elif request_data == 'get_names':
        send_client_names(client_socket)

def handle_client(client_socket, client_address):
    print(f"Client trying to connect from {client_address[0]}:{client_address[1]}")

    client_id = client_address[0]
    client_sockets[client_id] = client_socket

    global client_names
    client_name = None

    while True:
        try:
            request_data = client_socket.recv(1024)
            if not request_data:
                break

            request_data = request_data.decode('utf-8')
            if request_data.startswith('set_name:'):
                client_name = request_data.split(':')[1]  # Update client name when set_name request is received
                print(f"Client {client_address[0]}:{client_address[1]} set name to '{client_name}'")

            process_request(client_socket, client_id, request_data)

        except socket.error:
            break

    if client_id in client_sockets:
        del client_sockets[client_id]
        if client_id in pending_codes:
            with used_codes_lock:
                code_pools.insert(0, pending_codes.pop(client_id))

        if client_id in client_names:
            del client_names[client_id]

        print(f"Client {client_name} disconnected.")
        redistribute_codes()

def send_codes(client_socket, client_id):
    global code_pools

    if code_pools:
        codes = code_pools.pop(0)
        pending_codes[client_id] = codes
        client_socket.send(json.dumps({'codes': codes}).encode('utf-8'))
    else:
        client_socket.send(json.dumps({'error': 'No codes available'}).encode('utf-8'))

def confirm_code_used(client_id, code):
    with used_codes_lock:
        if client_id in pending_codes and code in pending_codes[client_id]:
            pending_codes[client_id].remove(code)
            used_codes.setdefault(client_id, []).append(code)
            client_name = client_names.get(client_id, 'unknown')
            print(f'Code {code} confirmed as used by client \'{client_name}\'.')

def set_client_name(client_id, name):
    name = name.strip()
    if name:
        client_names[client_id] = name

def send_client_names(client_socket):
    global client_names
    client_socket.send(json.dumps({'names': client_names}).encode('utf-8'))

def redistribute_codes():
    while code_pools and client_sockets:
        codes = code_pools.pop(0)
        client_id, client_socket = client_sockets.popitem()
        pending_codes[client_id] = codes
        client_name = client_names.get(client_id, 'unknown')
        print(f'Redistributing codes to client \'{client_name}\'.')
        client_socket.send(json.dumps({'codes': codes}).encode('utf-8'))

@bot.command()
@commands.guild_only()
async def restart(ctx):
    global code_pools, pending_codes, used_codes

    code_pools = [all_codes[i:i + POOL_SIZE] for i in range(0, len(all_codes), POOL_SIZE)]
    pending_codes.clear()
    used_codes.clear()

    await ctx.send("Code pools have been reset.")


@bot.command()
@commands.guild_only()
async def set_starting_code(ctx, starting_code: str):
    global code_pools

    if starting_code in all_codes:
        index = all_codes.index(starting_code)
        code_pools = [all_codes[index:index + POOL_SIZE] for index in range(index, len(all_codes), POOL_SIZE)]
        await ctx.send(f"Code pools starting from '{starting_code}'.")
    else:
        await ctx.send("Starting code not found in the code list.")




async def background_tasks():
    update_status.start()

def bot_thread():
    bot.run(TOKEN)

def main():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('0.0.0.0', LISTEN_PORT))
    server_socket.listen(5)

    print(f'Master Server listening on port {LISTEN_PORT}')

    while True:
        client_socket, client_address = server_socket.accept()
        client_thread = threading.Thread(target=handle_client, args=(client_socket, client_address))
        client_thread.start()

if __name__ == '__main__':
    bot_thread = threading.Thread(target=bot_thread)
    bot_thread.start()

    loop = asyncio.get_event_loop()
    loop.create_task(send_initial_status())
    loop.create_task(background_tasks())

    main()
