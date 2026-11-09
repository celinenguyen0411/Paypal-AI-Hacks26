from .config import TZ


def deal_runs_on(deal, moment):
    return moment.astimezone(TZ).weekday() in deal["days"]


def deal_live(deal, moment):
    local = moment.astimezone(TZ)
    return local.weekday() in deal["days"] and deal["from_hour"] <= local.hour < deal["to_hour"]


def deal_opens_at(deal, moment):
    local = moment.astimezone(TZ)
    opens = local.replace(hour=deal["from_hour"], minute=0, second=0, microsecond=0)
    return opens if local.weekday() in deal["days"] and local < opens else None


def deal_cashback(deal, listed_cents, paid_cents):
    if deal["flat_cents"] is not None:
        earned = deal["flat_cents"]
    else:
        earned = min(round(min(listed_cents, paid_cents) * deal["pct"] / 100), deal["cap_cents"])
    return min(earned, paid_cents)
