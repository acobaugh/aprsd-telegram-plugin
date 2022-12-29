from oslo_config import cfg


telegram_group = cfg.OptGroup(
    name="aprsd_telegram_plugin",
    title="APRSD Telegram Plugin settings",
)

telegram_opts = [
    cfg.StrOpt(
        "callsign",
        help="Callsign allowed to use Telegram! "
             "For example, if you set this to WB4BOR then any"
             "callsign starting with WB4BOR will be allowed to use this."
             "This way WB4BOR-1 can tweet from this instance.",
    ),
    cfg.StrOpt(
        "apiKey",
        help="Your twitter apiKey"
             "Information for creating your api keys is here:  "
             "https://developer.twitter.com/en/docs/authentication/oauth-1-0a/api-key-and-secret",
    ),
    cfg.ListOpt(
        "shortcuts",
        help="List of shortcuts for sending telegram messages "
             "For Exmaple: wb=hemna6969,cl=craigerl\n"
             "Means use 'wb' to send a telegram message to hemna6969",
    ),
]

ALL_OPTS = (
    telegram_opts
)


def register_opts(cfg):
    cfg.register_group(telegram_group)
    cfg.register_opts(ALL_OPTS, group=telegram_group)


def list_opts():
    return {
        telegram_group.name: ALL_OPTS,
    }
