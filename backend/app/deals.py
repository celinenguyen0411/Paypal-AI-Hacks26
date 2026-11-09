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


def deal_cashback(deal, cost_cents):
    if deal["flat_cents"] is not None:
        return deal["flat_cents"]
    return min(round(cost_cents * deal["pct"] / 100), deal["cap_cents"])
