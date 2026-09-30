"""Shared FastAPI route dependencies."""

from typing import Annotated

from fastapi import Depends

from app.core.config import Settings, get_settings
from app.services import launch_config
from app.services.launch_config import LaunchConfig

SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_launch_config(settings: SettingsDep) -> LaunchConfig:
    return launch_config.load(settings.launch_config_path)


LaunchConfigDep = Annotated[LaunchConfig, Depends(get_launch_config)]
