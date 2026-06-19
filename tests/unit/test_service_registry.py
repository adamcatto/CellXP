from cellxp.services.registry import SERVICE_REGISTRY

def test_registry_contains_alphagenome():
    assert "alphagenome" in SERVICE_REGISTRY
