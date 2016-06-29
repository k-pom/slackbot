#coding: UTF-8
import json
import re
from datetime import datetime, timedelta

from slackbot.bot import listen_to, dispatcher, respond_to


DEFAULT_TIMEOUT = 3600  # will auto release the locks after this many seconds
DATE_FORMAT = "%Y-%m-%d %H:%M"

EXPIRED="EXPIRED"
LOCKED="LOCKED"
OPEN="OPEN"

locks = {
    # ord: {user: 'U123534' time: datetime.now }
}

@respond_to('.*')
def help(message):
    commands = [
        "system.lock()    # Locks the system if it is available (default for one hour)",
        "system.lock(90)  # locks the system for 90 seconds",
        "system.unlock()  # Unlocks the system, if you have the lock on it",
        "system.notify()  # Receive a notification when the lock is removed or expired",
        "system.status()  # Get the lock information for a system"
    ]
    message.reply('You can issue the following commands. [system] should be replaced with iad, dfw, or ord ')
    # react with thumb up emoji
    message.react('+1')


def _parse(message):

    body = message.body.get('text', None)
    match = re.search(r'([^\.]*)\.[a-z]*\((.*)\)', body)
    system = match.group(1)
    arguments = match.group(2)
    user = message._get_user_id()
    return {
        'arguments': arguments,
        'system': system,
        'text': body,
        'user': user
    }

def _get_lock(system):

    current_lock = locks.get(system, None)
    if not current_lock:
        return OPEN, None

    if current_lock['expires'] < datetime.now():
        return EXPIRED, current_lock

    return LOCKED, current_lock


@listen_to(r'.*\.unlock\(\)')
def unlock(message):


    data = _parse(message)
    lock_status, lock = _get_lock(data['system'])
    if lock_status == EXPIRED:
        message.reply('Lock was held by <@{}>, but expired at {}'.format(data['user'], lock['expires_str']))
    elif lock_status == OPEN:
        message.send("No locks on {}".format(data['system']))
    elif data['user'] != lock['user']:
        message.send("<@{}> is owns the lock.".format(data['user']))
    else:
        notify = ", ".join(["<@{}>".format(notify) for notify in lock['notify']])
        message.send('Unlocked {} (notify {})'.format(data['system'], notify))
        dispatcher.cancel_delayed_message(data['system'])
        del locks[data['system']]


@listen_to(r'.*\.notify\(\)')
def notify(message):

    data = _parse(message)

    lock_status, lock = _get_lock(data['system'])
    if lock_status == EXPIRED:
        message.reply('Lock was held by <@{}>, but expired at {}'.format(data['user'], lock['expires_str']))
    elif lock_status == OPEN:
        message.send("No locks on {}".format(data['system']))
    else:
        dispatcher.append_delayed_message(data['system'], " (notify <@{}>)".format(data['user']))
        lock['notify'].append(data['user'])
        message.send('I will notify you when the lock on {} is released or expired'.format(data['system']))


@listen_to(r'.*\.lock\([0-9]*\)')
def lock(message):
    data = _parse(message)

    # If there is not an open/expired lock, we can't lock it again
    lock_status, lock = _get_lock(data['system'])
    if lock_status == LOCKED:
        return message.send('<@{}> is holding the lock until {}'.format(lock['user'], lock['expires_str']))

    timeout = DEFAULT_TIMEOUT
    try:
        timeout = int(data['arguments'])
    except:
        pass  # if its not an int, use the default

    expires = datetime.now() + timedelta(0, timeout)
    locks[data['system']] = {
        "user": data['user'],
        'notify': [],
        "expires": expires,
        "expires_str": expires.strftime(DATE_FORMAT)
    }

    if lock_status == EXPIRED:
        message.send("Stole expired lock from <@{}>".format(lock['user']))
    else:
        message.send('Locked {} for <@{}> for {} seconds'.format(data['system'], data['user'], timeout))

    # Queue a message for the expired
    msg = 'Your lock on {} is expired. Make sure to lock it again if you still need it.'.format(data['system'])
    dispatcher.delayed_message(data['system'], message, msg, timeout)


@listen_to(r'.*\.status\(\)')
def status(message):

    data = _parse(message)
    lock_status, lock = _get_lock(data['system'])
    if lock_status == EXPIRED:
        message.reply('Lock was held by <@{}>, but can be taken. (expired at {})'.format(
            lock['user'], lock['expires_str']))
    elif lock_status == OPEN:
        message.send("No locks on {}".format(data['system']))
    else:
        message.send('<@{}> is holding the lock until {}'.format(user, lock['expires_str']))
