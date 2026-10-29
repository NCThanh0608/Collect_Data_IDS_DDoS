"""Validate the lab subnet and derive the Pi/victim addresses."""

import ipaddress
import sys


def addresses(value):
    try:
        network = ipaddress.ip_network(value, strict=True)
    except ValueError as exc:
        raise ValueError(f"Invalid LAB_SUBNET: {value}") from exc
    if not isinstance(network, ipaddress.IPv4Network) or network.prefixlen != 24:
        raise ValueError("LAB_SUBNET must be an IPv4 /24 network")
    private_blocks = (
        ipaddress.ip_network("10.0.0.0/8"),
        ipaddress.ip_network("172.16.0.0/12"),
        ipaddress.ip_network("192.168.0.0/16"),
    )
    if not any(network.subnet_of(block) for block in private_blocks):
        raise ValueError("LAB_SUBNET must use RFC 1918 private IPv4 space")
    return str(network), str(network.network_address + 1), str(network.network_address + 2)


if __name__ == "__main__":
    try:
        print(" ".join(addresses(sys.argv[1])))
    except (IndexError, ValueError) as exc:
        print(exc, file=sys.stderr)
        sys.exit(2)
