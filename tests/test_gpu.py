import pytest

torch = pytest.importorskip("torch")
pytestmark = pytest.mark.gpu


def test_cuda_visible():
    assert torch.cuda.is_available(), "torch is installed but CUDA is not available"
    assert torch.cuda.get_device_name(0)
