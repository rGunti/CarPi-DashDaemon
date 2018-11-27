"""
CARPI DASH DAEMON
(C) 2018, Raphael "rGunti" Guntersweiler
Licensed under MIT
"""
from logging import Logger
from time import sleep

from carpicommons.log import logger
from carpicommons.errors import CarPiExitException
from carpisettings import IniStore, RedisStore, ConfigStore
from daemoncommons.daemon import Daemon
from dashdaemon.keys import LIVE_INPUT_DATA_KEYS, LIVE_OUTPUT_DATA_KEYS, CONFIG_KEYS
from redisdatabus.bus import BusWriter, TypedBusListener

from dashdaemon.work import calculate_fuel_usage, calculate_fuel_efficiency


class DashDaemonError(CarPiExitException):
    DEFAULT_EXIT_CODE = 0xFD00

    REASON_CONFIG_CONNECTION_INVALID = 0xC0
    REASON_CONFIG_WHEREISIT = 0xC1

    def __init__(self, reason=0x0):
        super().__init__(DashDaemonError.DEFAULT_EXIT_CODE + reason)
        self._reason = reason

    @property
    def reason(self):
        return self._reason


class DashDaemon(Daemon):
    def __init__(self):
        super().__init__("Dash Daemon")
        self._log: Logger = None
        self._current_values = dict()
        self._running = False
        self._reader: TypedBusListener = None

    def _build_config_reader(self) -> ConfigStore:
        cfg_type = self._get_config('Config', 'Type', 'Redis')
        if cfg_type.lower() == "ini":
            ini_path = self._get_config('Config', 'Path', None)
            if not ini_path:
                self._log.error("Failed to load configuration because you didn't specify it")
                raise DashDaemonError(DashDaemonError.REASON_CONFIG_WHEREISIT)

            self._log.info("Loading INI configuration from %s ...", ini_path)
            return IniStore(ini_path)
        elif cfg_type.lower() == "redis":
            url = self._get_config('Config', 'URL', None)
            if url:
                self._log.info("Loading Redis configuration from %s ...", url)
                return RedisStore(url=url)
            else:
                host = self._get_config('Config', 'Host', '127.0.0.1')
                port = self._get_config_int('Config', 'Port', 6379)
                db = self._get_config_int('Config', 'DB', 0)

                self._log.info("Loading Redis configuration from %s:%s/%s ...", host, port, db)
                return RedisStore(host=host, port=port, db=db,
                                  password=self._get_config('Config', 'Password', None))
        else:
            self._log.error("Configuration Type %s is unknown or not implemented", cfg_type)
            raise DashDaemonError(DashDaemonError.REASON_CONFIG_CONNECTION_INVALID)

    def _build_bus_writer(self) -> BusWriter:
        self._log.info("Connecting to Data Target Redis instance ...")
        return BusWriter(host=self._get_config('Destination', 'Host', '127.0.0.1'),
                         port=self._get_config_int('Destination', 'Port', 6379),
                         db=self._get_config_int('Destination', 'DB', 0),
                         password=self._get_config('Destination', 'Password', None))

    def _build_bus_reader(self, channels: list) -> TypedBusListener:
        self._log.info("Connecting to Data Source Redis instance ...")
        return TypedBusListener(channels,
                                host=self._get_config('Source', 'Host', '127.0.0.1'),
                                port=self._get_config_int('Source', 'Port', 6379),
                                db=self._get_config_int('Source', 'DB', 0),
                                password=self._get_config('Source', 'Password', None))

    def startup(self):
        self._log = log = logger(self.name)
        log.info("Starting up %s ...", self.name)

        channels = [
            LIVE_INPUT_DATA_KEYS['car_rpm'],
            LIVE_INPUT_DATA_KEYS['car_spd'],
            LIVE_INPUT_DATA_KEYS['car_map'],
            LIVE_INPUT_DATA_KEYS['car_tmp']
        ]

        config = self._build_config_reader()
        reader = self._build_bus_reader(channels)
        writer = self._build_bus_writer()

        reader.register_global_callback(self._on_new_value_registered)

        reader.start()
        self._running = True

        log.info("Ready to enter main loop")
        while self._running:
            self._step(config, writer)
            sleep(0.2)

        self._reader.stop()

    def shutdown(self):
        self._running = False
        if self._reader:
            self._reader.stop()

    def _on_new_value_registered(self, channel, value):
        self._log.debug("Reported new value from %s: %s", channel, value)
        self._current_values[channel] = value

    def _step(self, config: ConfigStore, writer: BusWriter):
        values = self._current_values

        # Pass over speed directly
        # TODO: In the future, compare GPS and OBD speed and try to find the best match
        car_speed = values.get(LIVE_INPUT_DATA_KEYS['car_spd'], 0)
        writer.publish(LIVE_OUTPUT_DATA_KEYS['speed'], car_speed)

        try:
            # Calculate Fuel Efficiency
            rpm = values[LIVE_INPUT_DATA_KEYS['car_rpm']]
            map = values[LIVE_INPUT_DATA_KEYS['car_map']]
            in_tmp = values[LIVE_INPUT_DATA_KEYS['car_tmp']]

            vol_efficiency = config.read_int_value(CONFIG_KEYS['vol_efficency'], 85) / 100
            eng_volume = config.read_int_value(CONFIG_KEYS['engine_vol']) / 1000
            fuel_density = config.read_int_value(CONFIG_KEYS['fuel_density'], 745)

            lph = calculate_fuel_usage(rpm, map, in_tmp,
                                       vol_efficiency, eng_volume, fuel_density)
            lpk = calculate_fuel_efficiency(car_speed, lph)

            writer.publish(LIVE_OUTPUT_DATA_KEYS['fuel_usage'], lph)
            writer.publish(LIVE_OUTPUT_DATA_KEYS['fuel_efficiency'], lpk)
        except KeyError as e:
            # If values aren't present, just fail fast
            writer.publish(LIVE_OUTPUT_DATA_KEYS['fuel_fail_flag'], True)
