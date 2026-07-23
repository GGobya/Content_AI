import asyncio
import os
import tempfile

import pytest

from app.state import JobStatus, StateStore


@pytest.fixture
def state_path():
    with tempfile.TemporaryDirectory() as tmp:
        yield os.path.join(tmp, "state.json")


def test_create_and_get_job(state_path):
    async def run():
        store = StateStore(state_path)
        job = await store.create_job(
            chat_id=1,
            drive_file_id="file-1",
            drive_file_name="scarf.jpg",
            product_name="scarf",
            photo_path="/tmp/scarf.jpg",
            scenario_text="scenario",
            hf_prompt="prompt",
        )
        assert job.status == JobStatus.AWAITING_APPROVAL
        fetched = await store.get(job.id)
        assert fetched.product_name == "scarf"
        assert await store.is_photo_used("file-1") is True
        assert await store.is_photo_used("file-2") is False

    asyncio.run(run())


def test_state_persists_across_instances(state_path):
    async def run():
        store = StateStore(state_path)
        job = await store.create_job(
            chat_id=1,
            drive_file_id="file-1",
            drive_file_name="scarf.jpg",
            product_name="scarf",
            photo_path="/tmp/scarf.jpg",
            scenario_text="scenario",
            hf_prompt="prompt",
        )
        await store.update(job.id, status=JobStatus.GENERATING, hf_request_id="req-1")

        reloaded = StateStore(state_path)
        fetched = await reloaded.get(job.id)
        assert fetched.status == JobStatus.GENERATING
        assert fetched.hf_request_id == "req-1"

    asyncio.run(run())


def test_list_by_status(state_path):
    async def run():
        store = StateStore(state_path)
        j1 = await store.create_job(
            chat_id=1,
            drive_file_id="a",
            drive_file_name="a.jpg",
            product_name="a",
            photo_path="/tmp/a.jpg",
            scenario_text="s",
            hf_prompt="p",
        )
        await store.create_job(
            chat_id=1,
            drive_file_id="b",
            drive_file_name="b.jpg",
            product_name="b",
            photo_path="/tmp/b.jpg",
            scenario_text="s",
            hf_prompt="p",
        )
        await store.update(j1.id, status=JobStatus.GENERATING)

        generating = await store.list_by_status(JobStatus.GENERATING)
        awaiting = await store.list_by_status(JobStatus.AWAITING_APPROVAL)
        assert [j.id for j in generating] == [j1.id]
        assert len(awaiting) == 1

    asyncio.run(run())
