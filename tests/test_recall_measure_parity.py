import copy

import pytest
from test_cognition import STAMP, budget, event, request, scope, state

from membrain import cognition
from membrain.context_views import FittingMeasure


@pytest.mark.parametrize("limit", [2500, 5000, 16000])
def test_fitting_preserves_multilingual_context_and_every_measured_byte(limit, monkeypatch):
    monkeypatch.setattr(cognition, "now", lambda: STAMP)
    sources = [event(f'Project {index}: green folder 青色文件夹 🧠 contains "draft\\{index}".\n'
                     + "周五记得带上笔记本。 " * 20, index + 1) for index in range(24)]
    memories = [memory for source in sources for memory in cognition.extract_event(source)]
    current = state(len(sources))
    query = request("green folder 青色文件夹", budget=budget(limit))

    def normalized(result):
        result = copy.deepcopy(result)
        recall_id = result.pop("recall_id")
        snapshot_id = result["retrieval_snapshot"].pop("snapshot_id")
        result["usage"].pop("elapsed_ms")
        assert len({trace["trace_id"] for trace in result["recall_traces"]}) == len(result["recall_traces"])
        for trace in result["recall_traces"]:
            assert trace["recall_id"] == recall_id and trace["retrieval_snapshot_id"] == snapshot_id
            trace["recall_id"], trace["retrieval_snapshot_id"] = "recall", "snapshot"
            trace.pop("trace_id")
        return result

    with monkeypatch.context() as plain:
        plain.setattr(cognition, "FittingMeasure", lambda handles: lambda result:
                      len(cognition.render_recall(result, handles).encode("utf-8")))
        expected = normalized(cognition.recall(scope(), copy.deepcopy(query), copy.deepcopy(memories),
                                               copy.deepcopy(sources), copy.deepcopy(current)))
    measurements = []

    class Checked(FittingMeasure):
        def __call__(self, result):
            measured = super().__call__(result)
            assert measured == len(cognition.render_recall(result).encode("utf-8"))
            measurements.append(measured)
            return measured

    monkeypatch.setattr(cognition, "FittingMeasure", Checked)
    result = cognition.recall(scope(), query, memories, sources, current)
    assert len(measurements) > 2
    assert result["items"]
    assert result["usage"]["context_tokens"] == len(result["model_context"].encode("utf-8")) <= limit
    assert normalized(result) == expected
