import logging

import requests
from requests.auth import HTTPDigestAuth

logger = logging.getLogger(__name__)

LASER_URL = "http://192.168.0.100/restapi/relay/outlets/2/state/"
LASER_USER = "admin"
LASER_PASS = "1234"


class LaserError(Exception):
    pass


class Laser:
    def set_state(self, on: bool) -> None:
        """PUT value=true/false to the relay outlet to turn the laser on or off."""
        state_str = "true" if on else "false"
        logger.info("Laser set_state called: on=%s", on)
        try:
            resp = requests.put(
                LASER_URL,
                data={"value": state_str},
                auth=HTTPDigestAuth(LASER_USER, LASER_PASS),
                headers={"X-CSRF": "x"},
                timeout=5,
            )
            resp.raise_for_status()
            logger.info("Laser relay responded %s", resp.status_code)
        except requests.RequestException as e:
            logger.error("Laser relay request failed: %s", e)
            raise LaserError(str(e)) from e
