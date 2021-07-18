<h1 align="center">aioaria2-mirror-bot</h1>

A Bot for Telegram made with Python using [Pyrogram](https://github.com/pyrogram/pyrogram) library.
It needs **Python 3.9** or newer to run.

## Compatibility

Bot should work with all Linux-based operating systems. This program is tested partially on Windows and not officially tested on macOS, but there shouldn't be any problem if you install the correct dependencies.

## Installation

This bot uses MongoDB Atlas for it database, you can get it free at <https://www.mongodb.com/> and save the uri for use on config or env variable.

Obviously you need git, and it should be already installed on major operating systems linux based.

### Local

First, clone this Git repository locally: `git clone https://github.com/adekmaulana/aioaria2-mirror-bot`

After that, you can run `python3 -m pip install .` to install the bot along with the depencies.

Once it's installed, you can choose to invoke it using the `bot` command, or run the bot in-place (which is described later in the Usage section). Running it in-place is recommended.

#### Error: Directory '.' is not installable. File 'setup.py' not found.

This common error is caused by an outdated version of pip. We use the Poetry package manager to make things easier to maintain, which works with pip through PEP-517. This is a relatively new standard, so a newer version of pip is necessary to make it work.

Upgrade to pip 19 to fix this issue: `pip3 install -U pip`

### Using Heroku

- Create a heroku account at <http://signup.heroku.com/> (skip if you already have)
- Then go to your [dashboard](https://dashboard.heroku.com/apps)
- Create an empty application, remember your app name
- Go to **Account Settings**
- Find **API Key** and click **Reveal**, copy
- Fork this repo and then go to **Settings** Tabs on your forked repo
- Go to **Secrets** > **New Repository Secret**
- Create 2 of repository secret with this name:
  - **HEROKU_APP**: Your created app name that upper step told
  - **HEROKU_API_KEY**: Your API Key heroku that upper step told
- Then go to **Actions** Tab, Click **Container**
- Run workflow
- It should be finished around 5-6 minutes and then go to your heroku dashboard again, and choose the app you've created
- Go to **Settings** > **Reveal Config Vars** and fill the coresponding _Name_ and _Value_ based on `config.env_sample`
- After all Variables are met then you can run your dyno

## Configuration

Copy `config.env_sample` to `config.env` and edit the settings as desired. Each and every setting is documented by the comments above it.

Obtain the _API ID_ and _API HASH_ from [Telegram's website](https://my.telegram.org/apps). **TREAT THESE SECRETS LIKE A PASSWORD!**

Obtain the _BOT TOKEN_ from [@BotFather](https://t.me/BotFather). **TREAT THESE SECRETS LIKE A PASSWORD!**

Obtain the _DB URI_ from [MongoDB](https://www.mongodb.com/try). **TREAT THESE SECRETS LIKE A PASSWORD!**

Obtain the _G DRIVE SECRET_ from [Google Console](https://console.cloud.google.com/apis/credentials). **TREAT THESE SECRETS LIKE A PASSWORD!**

Configuration must be complete before starting the bot for the first time for it to work properly.

## Usage

To start the bot, type `python3 -m bot` if you are running it in-place or use command corresponding to your chosen installation method above.

## Support

You may also open an [issue](https://github.com/adekmaulana/aioaria2-mirror-bot/issues) on GitHub for bugs, suggestions, or anything else relevant to the project.
