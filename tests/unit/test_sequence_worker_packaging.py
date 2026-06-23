from pathlib import Path


def test_evo_image_builds_vtx_cuda_extensions() -> None:
    dockerfile = Path("infra/docker/evo-worker.Dockerfile").read_text(encoding="utf-8")
    assert "pytorch/pytorch:2.7.1-cuda12.8-cudnn9-devel" in dockerfile
    assert "for operation in depr_attn conv" in dockerfile
    assert "import flash_attn_2_cuda, local_causal_conv1d_cuda" in dockerfile
