import pytest

from app.labengine.scanner import ScanError, build_nmap_argv, parse_nmap_xml, validate_target

XML = """<?xml version="1.0"?><nmaprun>
<host><status state="up"/><address addr="10.200.0.10" addrtype="ipv4"/>
<ports><port protocol="tcp" portid="22"><state state="open"/><service name="ssh" product="OpenSSH" version="9.6"/></port>
<port protocol="tcp" portid="23"><state state="closed"/></port></ports></host>
<host><status state="up"/><address addr="8.8.8.8" addrtype="ipv4"/></host>
</nmaprun>"""


def test_parse_filters_out_of_lab_hosts_and_closed_ports():
    hosts = parse_nmap_xml(XML, ["10.200.0.0/24"])
    assert [h["ip"] for h in hosts] == ["10.200.0.10"]
    assert hosts[0]["ports"] == [{"port": 22, "protocol": "tcp", "service": "ssh", "product": "OpenSSH", "version": "9.6"}]


def test_target_must_be_inside_lab():
    assert validate_target("10.200.0.0/24", ["10.200.0.0/24"]) == "10.200.0.0/24"
    for bad in ["8.8.8.8", "10.200.0.0/16", "10.200.0.5; rm -rf /", "-oN /etc/passwd"]:
        with pytest.raises(ScanError):
            validate_target(bad, ["10.200.0.0/24"])


def test_argv_is_whitelisted():
    assert build_nmap_argv("quick", "10.200.0.10")[:3] == ["nmap", "-oX", "-"]
    with pytest.raises(ScanError):
        build_nmap_argv("--script=evil", "10.200.0.10")


def test_xxe_is_blocked():
    evil = '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><nmaprun>&e;</nmaprun>'
    with pytest.raises(ScanError):
        parse_nmap_xml(evil)
