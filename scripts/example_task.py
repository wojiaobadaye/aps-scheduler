"""Example task script — logs a message."""

import datetime


def run():
    print("[%s] Hello from APScheduler example task!" % datetime.datetime.now())
