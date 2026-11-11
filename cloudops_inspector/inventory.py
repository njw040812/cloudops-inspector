"""Inventory loading and host definitions."""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional, Union

import yaml
from pydantic import BaseModel, Field, field_validator


class Host(BaseModel):
    name: str
    address: str
    port: int = 22
    user: str = "root"
    key: Optional[str] = None
    known_hosts: Optional[str] = None
    password_env: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    mysql: bool = False

    @field_validator("key", "known_hosts")
    @classmethod
    def expand_path(cls, value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        return str(Path(os.path.expandvars(value)).expanduser())

    @property
    def is_local(self) -> bool:
        return self.address.lower() in {"localhost", "127.0.0.1", "::1", "local"}


class Inventory(BaseModel):
    hosts: List[Host]

    @field_validator("hosts")
    @classmethod
    def unique_names(cls, hosts: List[Host]) -> List[Host]:
        names = [host.name for host in hosts]
        if len(names) != len(set(names)):
            raise ValueError("host names must be unique")
        if not hosts:
            raise ValueError("inventory must contain at least one host")
        return hosts


def load_inventory(path: Union[str, Path]) -> Inventory:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return Inventory.model_validate(data)
