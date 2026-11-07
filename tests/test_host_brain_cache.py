from uuid import uuid4

import httpx
import pytest

from membrain import host
from membrain.client import MemoryClient


@pytest.mark.parametrize("second_url", ["https://first.example", "https://second.example"])
def test_each_client_initializes_its_own_authenticated_user_brain(second_url):
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(200, json={"id": "created"})

    user = str(uuid4())
    with (MemoryClient("https://first.example", "test-key-a", "home-a",
                       transport=httpx.MockTransport(handle)) as first,
          MemoryClient(second_url, "test-key-b", "home-b",
                       transport=httpx.MockTransport(handle)) as second):
        for client in (first, second):
            host.use_brain(client, user)
            host.use_brain(client, None)
            host.use_brain(client, user)
        assert len(requests) == 2
        assert [request.headers["Authorization"] for request in requests] == ["Bearer test-key-a", "Bearer test-key-b"]
        assert first.brain_id == second.brain_id == host.user_brain_id(user)
