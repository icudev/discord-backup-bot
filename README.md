<a href="https://github.com/icudev/discord-backup-bot/">
    <img src="https://imgur.com/aiOeEzU.png" alt="Discord Backup Bot"/>
</a>

<h1 align="center" style="margin-top: 20px;">Discord Backup Bot</h1>

<p align="center">
<a href="https://www.python.org/downloads/">
    <img src="https://img.shields.io/badge/python-3.8_|_3.9_|_3.10_|_3.11-3776AB"/>
</a>
<a href="https://opensource.org/license/mit/">
    <img src="https://img.shields.io/badge/license-MIT-yellow"/>
</a>
<a href="https://opensource.org/license/mit/">
    <img src="https://img.shields.io/badge/PRs-welcome-green"/>
</a>
</p>

## Overview
This is an easy to use backup bot to save the state of your discord server and load it at any time.
The bot uses SQLite as its db which makes the install as easy as possible.

## Features
|        Done        |            Feature             |
|--------------------|:-------------------------------|
| :heavy_check_mark: | Cross Server Backups           |
| :heavy_check_mark: | Channel / Category backups     |
|         :x:        | Automatic backups in intervals |
| :heavy_check_mark: | Role backups                   |
|         :x:        | Message backups                |

## Setup
1. Copy `.env.template` to `.env` and insert your discord bot token
1. Install the dependencies
    ```
    pip install -r requirements.txt
    ```
1. Run the bot
    ```
    cd src
    python bot.py
    ```
    or
    ```
    python src/bot.py
    ```

## Usage
|   Command name   |         Command description         |
|------------------|-------------------------------------|
| `/backup create` |   Creates a backup of your server   |
| `/backup load`   |    Loads a backup to your server    |
| `/backup delete` | Deletes a backup to save disk space |

## FAQ
> Why is the bot not doing anything when loading a backup?

Make sure that the bot role is above every other and has the following permission:
* Administrator

If that doesn't help it could be because your bot got ratelimited. This happens when
you load a lot of backups in a short amount of time. In that case you just have to wait.