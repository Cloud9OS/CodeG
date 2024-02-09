# Master Server for CodeG

## Overview

The Master Server for CodeG is a Python-based server application that manages and distributes codes to multiple clients in a distributed computing environment. It is specifically designed for scenarios where a central server needs to distribute a pool of codes to various clients and monitor their usage.


## Features

- Code Distribution: The server distributes codes to connected clients in a pool, ensuring fair distribution among active clients.
- Client Status Monitoring: Monitors the status of connected clients, providing information on online clients, used code percentage, and individual client usage.
- Discord Integration: Utilizes Discord for real-time status updates and interaction. A Discord bot is integrated to facilitate commands and reporting.

## Getting Started

## Prerequisites


Python 3.x
Discord account and bot token for Discord integration

```bash
pip install -r requirements.txt
```
    
## Discord Commands

- !status: Get the current status report, including online clients and used code percentage.
- !restart: Reset code pools and clear client usage.
- !set_starting_code [code]: Set the starting code for code distribution.
