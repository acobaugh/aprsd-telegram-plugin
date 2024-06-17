import datetime
import logging
import threading
import time
import asyncio

from aprsd import conf  # noqa
from aprsd import packets, plugin, threads
from aprsd.utils import objectstore
from oslo_config import cfg
from telegram import Update
from telegram.ext import filters, Application, MessageHandler, Updater

import aprsd_telegram_plugin
from aprsd_telegram_plugin import conf  # noqa

CONF = cfg.CONF
LOG = logging.getLogger("APRSD")

class TelegramUsers(objectstore.ObjectStoreMixin):
    """Class to automatically store telegram user ids between starts.

    Telegram doesn't provide an API for looking up an userid from
    username, so we have to save it off for better user experience.

    Unfortunately, we can't get the userid, until the telegram user
    sends a message to the bot FIRST.
    """
    _instance = None
    data = {}
    _shortcuts = {}

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.lock = threading.Lock()
            cls._instance.data = {}
            if CONF.aprsd_telegram_plugin.shortcuts:
                cls._instance._shortcuts = CONF.aprsd_telegram_plugin.shortcuts
            else:
                cls._instance._shortcuts = None
            cls._instance._init_store()
        return cls._instance

    def __getitem__(self, item):
        with self.lock:
            if item in self._shortcuts:
                item = self._shortcuts[item]
            return self.data[item]

    def __setitem__(self, item, value):
        with self.lock:
            self.data[item] = value

    def __delitem__(self, item):
        del self.data[item]

    def __contains__(self, item):
        if item in self._shortcuts:
            item = self._shortcuts[item]

        if item in self.data:
            return True
        else:
            return False

    def get_shortcuts(self):
        return self._shortcuts


class TelegramChatPlugin(plugin.APRSDRegexCommandPluginBase):

    version = aprsd_telegram_plugin.__version__
    # Look for any command that starts with w or W
    command_regex = "^[tT][gG]"
    # the command is for ?
    command_name = "telegram"

    enabled = False
    users = None
    loop = None

    def help(self):
        _help = [
            "telegram: Chat with a user on telegram Messenger.",
            "telegram: username has to message you first."
            "tg: Send tg <username> <message>",
        ]
        return _help

    def setup(self):
        self.enabled = True
        _loop = asyncio.new_event_loop()
        # Do some checks here?
        if not CONF.aprsd_telegram_plugin.apiKey:
            LOG.error(f"Failed to find config telegram:apiKey {ex}")
            self.enabled = False
            return

        token = CONF.aprsd_telegram_plugin.apiKey

        self.users = TelegramUsers()
        self.users.load()

        # self.bot = telegram.Bot(token=token)
        # LOG.info(self.bot.get_me())
        LOG.info("Starting up Telegram Application")
        try:
            self.application = Application.builder().token(token).build()
            LOG.info(f"Started telegram bot: {self.application.bot.name}")
        except Exception as ex:
            self.enabled = False
            LOG.exception(ex)

        try:
            self.application.add_handler(
                MessageHandler(
                    filters.TEXT & (~filters.COMMAND),
                    self.message_handler,
                ),
            )
        except Exception as ex:
            self.enabled = False
            LOG.exception(ex)

    async def message_handler(self, update, context):
        """This is called when a telegram users texts the bot."""
        LOG.info(f"{self.__class__.__name__}: Got message {update.message.text}")
        # LOG.info(f"Text {update.message.text}")
        # LOG.info(f"Chat {update.message.chat}")
        # LOG.info(f"From {update.message.from.username} : ")
        fromcall = CONF.get("aprs.login")
        tocall = CONF.callsign
        pkg = None

        if update.message.chat.type == "private":
            LOG.info(f"Username {update.message.chat.username} - ID {update.message.chat.id}")
            message = "Telegram({}): {}".format(
                update.message.chat.username,
                update.message.text,
            )
            self.users[update.message.chat.username] = update.message.chat.id
            # LOG.debug(self.users)
            # LOG.info(f"{message}")
            pkt = packets.MessagePacket(
                from_call=fromcall,
                to_call=tocall,
                message_text=message,
            )
            pkt.send()
        elif update.message.chat.type == "group":
            group_name = "noidea"
            message = "TelegramGroup({}): {}".format(
                group_name,
                update.message.text,
            )
            pkt = packets.MessagePacket(
                from_call=fromcall,
                to_call=tocall,
                message_text=message,
            )
            pkt.send()
        await update.message.reply_text(f"Sent packet: {pkg}")

    def create_threads(self):
        if self.enabled:
            LOG.info("Starting TelegramThread")
            return TelegramThread(self.application)

    def process(self, packet):
        """This is called when a received packet matches self.command_regex."""
        LOG.info("TelegramChatPlugin Plugin")

        from_callsign = packet.from_call
        message = packet.message_text

        if self.enabled:
            # Now we can process
            # Only allow aprsd owner to use this.
            mycall = CONF.aprsd_telegram_plugin.callsign

            # Only allow the owner of aprsd to send a tweet
            if not from_callsign.startswith(mycall):
                LOG.warning(f"unauthorized: {from_callsign} -> {mycall}")
                return "Unauthorized"

            # Always should have format of
            # <command> <username> <message>
            parts = message.split(" ")
            LOG.info(parts)

            if len(parts) < 3:
                return "invalid request"
            # parts[0] is the command
            username = parts[1]
            msg = " ".join(parts[2:])
            if username not in self.users:
                # Unfortunately there is no way to lookup a user ID
                # from a username right now.
                return f"Need a message from {username} first"

            bot = self.updater.bot
            bot.sendMessage(
                chat_id=self.users[username],
                text=msg,
            )

            return packets.NULL_MESSAGE
        else:
            LOG.warning("TelegramChatPlugin is disabled.")
            return packets.NULL_MESSAGE


class TelegramThread(threads.APRSDThread):
    def __init__(self, application):
        super().__init__(self.__class__.__name__)
        self.application = application
        self.past = datetime.datetime.now()
        
    def stop(self):
        self.thread_stop = True
        self.application.updater.stop()
        TelegramUsers().save()

    def loop(self):
        #LOG.info("loop()")
        try:
            # self._loop.run_until_complete(self.application.updater.start_polling(
            #     timeout=2,
            #     drop_pending_updates=True,
            # ))
            #_loop = asyncio.new_event_loop()
            #asyncio.set_event_loop(_loop)
            _loop.run_until_complete(self.application.updater.initialize())
            _loop.run_forever(self.application.updater.start_polling(
                timeout=2,
                drop_pending_updates=True,
                allowed_updates=["messages"],
            ))
            LOG.info(f"qsize(): {self.application.update_queue.qsize()}, running: {self.application.running}")
        except Exception as ex:
            LOG.exception(ex)
        
        time.sleep(1)
        # so we can continue looping
        return True
