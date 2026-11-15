"""Interactive local setup; never paste bot tokens into chat or command arguments."""
import argparse
from dataclasses import replace
from getpass import getpass
import os
from pathlib import Path
import re
from .config import Settings
from .run import load_local_env
from .telegram_transport import TelegramClient, TelegramError


def save(values):
    path = Path(__file__).with_name('.env')
    lines = path.read_text().splitlines() if path.exists() else []
    lines = [line for line in lines if line.partition('=')[0] not in values]
    lines.extend(f'{key}={value}' for key, value in values.items())
    path.write_text('\n'.join(lines)+'\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--action', choices=('configure', 'check', 'webhook', 'polling'), default='configure')
    args = parser.parse_args()
    load_local_env()
    settings = Settings.from_env()
    token = settings.telegram_token or getpass('Telegram bot token from @BotFather (hidden): ')
    if not re.fullmatch(r'\d{5,20}:[A-Za-z0-9_-]{20,}', token):
        raise ValueError('Invalid bot token format')
    settings = replace(settings, telegram_token=token)
    client = TelegramClient(settings)
    bot = client.call('getMe')
    if not isinstance(bot, dict) or not bot.get('is_bot'):
        raise ValueError('Token does not identify a Telegram bot')
    print(f"Connected to @{bot['username']}.")
    hook = client.call('getWebhookInfo')
    if args.action == 'check':
        print('Recipient configured: '+('yes' if settings.telegram_chat_id else 'no'))
        print('Webhook registered: '+('yes' if hook.get('url') else 'no'))
        print('No messages sent.')
        return
    if args.action == 'webhook':
        replace(settings, transport='telegram', telegram_updates='webhook').validate()
        secret = settings.telegram_webhook_secret
        if not re.fullmatch(r'[A-Za-z0-9_-]{32,256}', secret) or not settings.public_url.startswith('https://'):
            raise ValueError('Configure HTTPS HOLYCOW_PUBLIC_BACKEND_URL and random TELEGRAM_WEBHOOK_SECRET first')
        client.call('setWebhook', {'url': settings.public_url+'/webhooks/telegram', 'secret_token': secret,
                                   'allowed_updates': ['message'], 'drop_pending_updates': False})
        save({'TELEGRAM_UPDATES_MODE':'webhook'})
        print('Webhook configured. Restart the backend.')
        return
    if hook.get('url'):
        if args.action != 'polling' or input('Remove this bot’s existing webhook and use polling? [y/N] ').lower() != 'y':
            raise ValueError('Existing webhook preserved. Use a dedicated bot or explicitly switch with --action polling')
        client.call('deleteWebhook', {'drop_pending_updates': False})
    if args.action == 'polling':
        save({'TELEGRAM_UPDATES_MODE':'polling'})
        print('Polling configured; pending updates preserved. Restart the backend.')
        return
    print(f"On the rancher’s phone, open https://t.me/{bot['username']} and tap Start.")
    input('Press Enter after Start has been sent. ')
    updates = client.call('getUpdates', {'timeout':0, 'limit':100, 'allowed_updates':['message']})
    chats = {}
    for update in updates:
        message = update.get('message', {})
        chat, sender = message.get('chat', {}), message.get('from', {})
        if chat.get('type') == 'private' and chat.get('id') == sender.get('id') and not sender.get('is_bot'):
            chats[str(chat['id'])] = ''.join(c for c in str(chat.get('first_name', 'Telegram user')) if ord(c) >= 32)[:60]
    if not chats:
        raise ValueError('No private chat found. Tap Start in the bot chat and run setup again')
    options = list(chats)
    for index, chat_id in enumerate(options, 1):
        print(f'{index}. {chats[chat_id]} (private chat {chat_id})')
    selection = input('Choose the rancher chat number: ')
    if not selection.isdigit() or not 1 <= int(selection) <= len(options):
        raise ValueError('No recipient selected')
    if input('Enable HolyCow alerts to this private chat? [y/N] ').lower() != 'y':
        print('Configuration unchanged.')
        return
    save({'TELEGRAM_BOT_TOKEN': token, 'TELEGRAM_CHAT_ID': options[int(selection)-1],
          'HOLYCOW_MESSAGING_TRANSPORT':'telegram', 'HOLYCOW_LIVE_TELEGRAM_ENABLED':'true',
          'HOLYCOW_RECIPIENT_OPTED_IN':'true', 'TELEGRAM_UPDATES_MODE':'polling'})
    print('Telegram settings saved in ignored backend/.env. Restart the backend to connect. No test alert was sent.')


if __name__ == '__main__':
    try:
        main()
    except (TelegramError, ValueError) as error:
        raise SystemExit(str(error)) from None
