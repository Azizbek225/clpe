import pytest

from app.labengine.manifest import ManifestError, parse_manifest, to_storage

KNOWN = {"kali-linux", "ubuntu-server", "dvwa"}
VTYPES = {"flag", "answer", "port_discovery"}

SPEC_EXAMPLE = """
id: network-scan-001
title: Network Scanning Fundamentals
difficulty: beginner
machines:
  - kali-linux
  - ubuntu-server
network:
  type: isolated
  internet: false
resources:
  cpu: 4
  ram: 4096
tasks:
  - id: task-01
    title: Identify active ports
    validation: port_discovery
scoring:
  maximum: 100
cleanup:
  snapshot_restore: true
  auto_shutdown: true
"""


def test_spec_shorthand_is_accepted():
    m = parse_manifest(SPEC_EXAMPLE, known_templates=KNOWN, validator_types=VTYPES)
    assert [x.role for x in m.machines] == ["attacker", "target"]
    assert m.networks[0].internet is False
    assert m.tasks[0].validation.type == "port_discovery"


@pytest.mark.parametrize("patch,msg", [
    ("network:\n  type: bridged", "bridged"),
    ("network:\n  type: isolated\n  internet: true", "internet"),
])
def test_isolation_policy(patch, msg):
    text = SPEC_EXAMPLE.replace("network:\n  type: isolated\n  internet: false", patch)
    with pytest.raises(ManifestError) as e:
        parse_manifest(text, known_templates=KNOWN, validator_types=VTYPES)
    assert msg in str(e.value)


def test_unknown_template_and_validator():
    text = SPEC_EXAMPLE.replace("ubuntu-server", "evil-image").replace("validation: port_discovery", "validation: rm_rf")
    with pytest.raises(ManifestError) as e:
        parse_manifest(text, known_templates=KNOWN, validator_types=VTYPES)
    assert any("evil-image" in x for x in e.value.errors)
    assert any("rm_rf" in x for x in e.value.errors)


def test_flags_are_hashed_in_storage():
    text = SPEC_EXAMPLE.replace("validation: port_discovery", "validation: {type: flag, flag: 'CLPE{x}'}")
    cfg = to_storage(parse_manifest(text, known_templates=KNOWN, validator_types=VTYPES))
    v = cfg["tasks"][0]["validation"]["config"]
    assert "flag" not in v and len(v["flag_hash"]) == 64
