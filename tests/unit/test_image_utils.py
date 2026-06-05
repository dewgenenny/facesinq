"""Tests for image_utils.generate_grid_image_bytes."""

import io
from unittest.mock import MagicMock, patch

from PIL import Image


def _make_fake_image_response(color=(255, 0, 0), size=(100, 100)):
    img = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = buf.read()
    return mock_resp


class TestGenerateGridImageBytes:
    def test_returns_bytes_for_four_images(self):
        from image_utils import generate_grid_image_bytes

        colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]
        responses = [_make_fake_image_response(c) for c in colors]

        with patch("image_utils.requests.get", side_effect=responses):
            result = generate_grid_image_bytes(["http://img.jpg"] * 4)

        assert result is not None
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_handles_failed_image_fetch(self):
        from image_utils import generate_grid_image_bytes

        def _side_effect(url, timeout):
            r = MagicMock()
            r.status_code = 404
            r.content = b""
            return r

        with patch("image_utils.requests.get", side_effect=_side_effect):
            result = generate_grid_image_bytes(["http://missing.jpg"] * 4)
        # Should return None or bytes — just shouldn't raise
        assert result is None or isinstance(result, bytes)

    def test_handles_exception_on_fetch(self):
        from image_utils import generate_grid_image_bytes

        with patch("image_utils.requests.get", side_effect=Exception("network error")):
            result = generate_grid_image_bytes(["http://bad.jpg"] * 4)
        assert result is None or isinstance(result, bytes)

    def test_three_valid_one_missing(self):
        from image_utils import generate_grid_image_bytes

        good = _make_fake_image_response()
        bad = MagicMock()
        bad.status_code = 500

        responses = [good, good, good, bad]
        with patch("image_utils.requests.get", side_effect=responses):
            result = generate_grid_image_bytes(["http://img.jpg"] * 4)
        assert result is None or isinstance(result, bytes)
