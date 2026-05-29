# Telegram setup

The `digest` command will silently print to stdout if the Telegram env vars are
missing. If you'd like it delivered to your phone every morning, do the following.

## 1. Create a bot

1. Open Telegram, search for `@BotFather`.
2. `/newbot`, give it a name and a unique username.
3. BotFather replies with a token like `123456789:AAEa-...`. Copy it.

## 2. Get your chat id

1. Send a message to your new bot (any text — required so it can DM you).
2. In a browser, open: `https://api.telegram.org/bot<YOUR-TOKEN>/getUpdates`
3. Look for `"chat":{"id": 12345678,...}`. That number is your `TELEGRAM_CHAT_ID`.

## 3. Wire it up

Edit `.env` at the repo root:

```
TELEGRAM_BOT_TOKEN=123456789:AAEa-...
TELEGRAM_CHAT_ID=12345678
```

## 4. Test

```powershell
py -m src.cli digest
```

You should see `[telegram] sent.` at the bottom and the message in your chat.

## 5. Schedule

```powershell
.\scripts\install_task.ps1
```

That installs a Windows scheduled task `SerenityKillerPipeline` that runs the
full `all` pipeline at 08:00 each day. Logs go to
`%LOCALAPPDATA%\serenity-killer-playbook\pipeline.log`.
