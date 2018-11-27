"""
CARPI DASH DAEMON
(C) 2018, Raphael "rGunti" Guntersweiler
Licensed under MIT
"""

from carpicommons.log import DEFAULT_CONFIG
from logging import DEBUG

from daemoncommons.daemon import DaemonRunner
from dashdaemon.daemon import DashDaemon

if __name__ == '__main__':
    # configure_logging()
    DEFAULT_CONFIG['root']['level'] = DEBUG
    d = DaemonRunner('DASH_DAEMON_CFG', ['dash.ini', '/etc/carpi/dash.ini'])
    d.run(DashDaemon())
