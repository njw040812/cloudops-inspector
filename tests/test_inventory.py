from __future__ import annotations

import pytest
from pydantic import ValidationError

from cloudops_inspector.inventory import Host, Inventory, load_inventory


def test_load_example_inventory():
    inventory = load_inventory("examples/inventory.yml")
    assert len(inventory.hosts) == 1
    assert inventory.hosts[0].name == "centos9"


def test_duplicate_hosts_rejected():
    with pytest.raises(ValidationError):
        Inventory(hosts=[Host(name="a", address="1.1.1.1"), Host(name="a", address="2.2.2.2")])


def test_empty_inventory_rejected():
    with pytest.raises(ValidationError):
        Inventory(hosts=[])


def test_key_expansion():
    host = Host(name="a", address="1.1.1.1", key="~/id_ed25519")
    assert "~" not in (host.key or "")
