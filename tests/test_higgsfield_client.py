import pytest

from app.higgsfield_client import HiggsfieldError, _extract_video_url


def test_extract_video_url_direct_video_url():
    assert _extract_video_url({"video": {"url": "https://x/video.mp4"}}) == "https://x/video.mp4"


def test_extract_video_url_output_video_url():
    assert _extract_video_url({"output": {"video_url": "https://x/video.mp4"}}) == "https://x/video.mp4"


def test_extract_video_url_videos_list():
    assert _extract_video_url({"videos": [{"url": "https://x/video.mp4"}]}) == "https://x/video.mp4"


def test_extract_video_url_top_level_url():
    assert _extract_video_url({"url": "https://x/video.mp4"}) == "https://x/video.mp4"


def test_extract_video_url_missing_raises():
    with pytest.raises(HiggsfieldError):
        _extract_video_url({"status": "completed"})


def test_build_arguments_uses_image_by_default():
    from app.higgsfield_client import HiggsfieldVideoClient

    client = HiggsfieldVideoClient(
        job_type="marketing_studio_video",
        mode="ugc",
        aspect_ratio="9:16",
        duration=10,
        resolution="720p",
    )
    args = client._build_arguments("prompt text", "https://img/1.jpg")
    assert args["image"] == "https://img/1.jpg"
    assert "product_ids" not in args
    assert args["mode"] == "ugc"


def test_build_arguments_uses_product_id_when_configured():
    from app.higgsfield_client import HiggsfieldVideoClient

    client = HiggsfieldVideoClient(
        job_type="marketing_studio_video",
        mode="ugc",
        aspect_ratio="9:16",
        duration=10,
        resolution="720p",
        product_id="prod-123",
        avatar_id="avatar-456",
    )
    args = client._build_arguments("prompt text", "https://img/1.jpg")
    assert args["product_ids"] == ["prod-123"]
    assert args["avatars"] == [{"id": "avatar-456", "type": "preset"}]
    assert "image" not in args
