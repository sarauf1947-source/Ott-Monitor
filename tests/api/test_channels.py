"""
Tests for channel and dashboard API endpoints.
"""

import uuid
import pytest
from httpx import AsyncClient
from db.models import Channel


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("ok", "degraded")
    assert "database" in data
    assert "redis" in data


@pytest.mark.asyncio
async def test_create_channel(client: AsyncClient):
    payload = {
        "name": "BBC News HD",
        "stream_url": "https://bbc.example.com/news/playlist.m3u8",
        "protocol": "HLS",
        "group": "News",
        "expected_bitrate": 3500,
        "expected_resolution": "1920x1080",
    }
    resp = await client.post("/api/v1/channels", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "BBC News HD"
    assert data["status"] == "UNKNOWN"
    assert uuid.UUID(data["id"])


@pytest.mark.asyncio
async def test_list_channels(client: AsyncClient, sample_channel: Channel):
    resp = await client.get("/api/v1/channels")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_get_channel(client: AsyncClient, sample_channel: Channel):
    resp = await client.get(f"/api/v1/channels/{sample_channel.id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == str(sample_channel.id)


@pytest.mark.asyncio
async def test_get_channel_not_found(client: AsyncClient):
    resp = await client.get(f"/api/v1/channels/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_channel(client: AsyncClient, sample_channel: Channel):
    resp = await client.patch(
        f"/api/v1/channels/{sample_channel.id}",
        json={"name": "Test Channel 4K", "expected_bitrate": 8000},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Test Channel 4K"
    assert data["expected_bitrate"] == 8000


@pytest.mark.asyncio
async def test_delete_channel(client: AsyncClient):
    # Create then delete
    resp = await client.post("/api/v1/channels", json={
        "name": "Channel To Delete",
        "stream_url": "https://delete.example.com/stream.m3u8",
    })
    channel_id = resp.json()["id"]
    del_resp = await client.delete(f"/api/v1/channels/{channel_id}")
    assert del_resp.status_code == 204
    get_resp = await client.get(f"/api/v1/channels/{channel_id}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_dashboard_summary(client: AsyncClient, sample_channel: Channel):
    resp = await client.get("/api/v1/dashboard/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_channels" in data
    assert "availability_pct" in data
    assert "open_alerts" in data


@pytest.mark.asyncio
async def test_channel_metrics_empty(client: AsyncClient, sample_channel: Channel):
    resp = await client.get(f"/api/v1/channels/{sample_channel.id}/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_channel_errors_empty(client: AsyncClient, sample_channel: Channel):
    resp = await client.get(f"/api/v1/channels/{sample_channel.id}/errors")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_list_alerts(client: AsyncClient):
    resp = await client.get("/api/v1/alerts")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
