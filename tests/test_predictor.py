"""Predictor + scoreboard tests. No network, no Ollama: a FakeReasoner stands in for the LLM."""

from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import create_engine

from app.agents.predictor import PredictorAgent, parse_baseline
from app.agents.reasoning import (
    HeuristicReasoner,
    OpenAICompatibleReasoner,
    ReasonerError,
    _validate,
)
from app.config import Settings
from app.db.database import init_db, make_session_factory
from app.db.models import Match
from tests.conftest import make_client


class FakeReasoner:
    """Returns a fixed call, letting us assert the agent's path independently of any model."""

    def __init__(self, winner="home", home=3, away=0):
        self.result = {"winner": winner, "home_score": home, "away_score": away,
                       "rationale": "fake"}
        self.calls = []

    def reason(self, context: dict) -> dict:
        self.calls.append(context)
        return dict(self.result)


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite:///:memory:", future=True)
    init_db(engine)
    return make_session_factory(engine)


def _seed_match(session_factory, **kw):
    defaults = dict(fixture_id=101, home_team="Brazil", away_team="Serbia",
                    status="FT", home_goals=2, away_goals=0)
    defaults.update(kw)
    with session_factory() as s:
        s.merge(Match(**defaults))
        s.commit()


def test_parse_baseline_argmax_winner(predictions_payload):
    b = parse_baseline(predictions_payload["response"][0])
    assert b["winner"] == "home"  # 55% home is the max
    assert b["prob_home"] == 0.55
    assert b["prob_away"] == 0.20
    assert b["home_team"] == "Brazil"


def test_predict_stores_baseline_and_agent(predictions_payload, session_factory):
    client = make_client(lambda r: httpx.Response(200, json=predictions_payload))
    agent = PredictorAgent(client, session_factory, FakeReasoner(winner="home", home=3, away=1))

    row = agent.predict(101)
    assert row["baseline_winner"] == "home"
    assert row["agent_winner"] == "home"
    assert row["agent_home_score"] == 3
    assert row["agent_rationale"] == "fake"
    assert row["predicted_at"] is not None
    assert row["actual_winner"] is None  # not settled yet


def test_settle_sets_correctness(predictions_payload, session_factory):
    client = make_client(lambda r: httpx.Response(200, json=predictions_payload))
    # Agent says away win; baseline says home. Actual is home win (2-0) → baseline right, agent wrong.
    agent = PredictorAgent(client, session_factory, FakeReasoner(winner="away", home=0, away=1))
    agent.predict(101)
    _seed_match(session_factory, fixture_id=101, status="FT", home_goals=2, away_goals=0)

    settled = agent.settle(101)
    assert settled["actual_winner"] == "home"
    assert settled["baseline_correct"] == 1
    assert settled["agent_correct"] == 0


def test_settle_skips_unfinished(predictions_payload, session_factory):
    client = make_client(lambda r: httpx.Response(200, json=predictions_payload))
    agent = PredictorAgent(client, session_factory, FakeReasoner())
    agent.predict(101)
    _seed_match(session_factory, fixture_id=101, status="1H", home_goals=0, away_goals=0)

    settled = agent.settle(101)
    assert settled["actual_winner"] is None
    assert settled["agent_correct"] is None


def test_predict_does_not_overwrite_settled(predictions_payload, session_factory):
    client = make_client(lambda r: httpx.Response(200, json=predictions_payload))
    agent = PredictorAgent(client, session_factory, FakeReasoner(winner="away"))
    agent.predict(101)
    _seed_match(session_factory, fixture_id=101, status="FT", home_goals=2, away_goals=0)
    agent.settle(101)

    # A later predict() with a different reasoner must not clobber the settled row.
    agent2 = PredictorAgent(client, session_factory, FakeReasoner(winner="home"))
    row = agent2.predict(101)
    assert row["agent_winner"] == "away"  # unchanged
    assert row["actual_winner"] == "home"


def test_scoreboard_lift(predictions_payload, session_factory):
    client = make_client(lambda r: httpx.Response(200, json=predictions_payload))
    # Agent predicts home (correct); baseline also home (correct) → both 1.0, lift 0.
    agent = PredictorAgent(client, session_factory, FakeReasoner(winner="home", home=2, away=0))
    agent.predict(101)
    _seed_match(session_factory, fixture_id=101, status="FT", home_goals=2, away_goals=0)
    agent.settle(101)

    board = agent.scoreboard()
    assert board["settled"] == 1
    assert board["baseline_hit_rate"] == 1.0
    assert board["agent_hit_rate"] == 1.0
    assert board["lift"] == 0.0
    assert board["agent_exact"] == 1.0  # predicted 2-0, actual 2-0


def test_scoreboard_empty(session_factory):
    client = make_client(lambda r: httpx.Response(200, json={"response": []}))
    agent = PredictorAgent(client, session_factory, FakeReasoner())
    board = agent.scoreboard()
    assert board["settled"] == 0
    assert board["lift"] is None


def test_heuristic_reasoner_mirrors_baseline():
    out = HeuristicReasoner().reason({"baseline": {"winner": "away"}})
    assert out["winner"] == "away"
    assert out["home_score"] == 1 and out["away_score"] == 2


def test_validate_rejects_bad_winner():
    with pytest.raises(Exception):
        _validate({"winner": "nonsense", "home_score": 1, "away_score": 0, "rationale": "x"})


class _FakeOpenAI:
    """Minimal stand-in for an openai client: .chat.completions.create(...) → message.content.

    Records the kwargs of the last create() call so tests can assert on the request shape.
    """

    def __init__(self, content: str):
        self.last_kwargs: dict = {}
        message = SimpleNamespace(content=content)
        choice = SimpleNamespace(message=message)
        response = SimpleNamespace(choices=[choice])

        def _create(**kw):
            self.last_kwargs = kw
            return response

        self.chat = SimpleNamespace(completions=SimpleNamespace(create=_create))


def test_oss_reasoner_parses_json_response():
    fake = _FakeOpenAI('{"winner": "away", "home_score": 0, "away_score": 2, "rationale": "ok"}')
    reasoner = OpenAICompatibleReasoner(Settings(), client=fake)
    out = reasoner.reason({"home_team": "A", "away_team": "B", "baseline": {"winner": "home"}})
    assert out == {"winner": "away", "home_score": 0, "away_score": 2, "rationale": "ok"}


def test_oss_reasoner_raises_on_non_json():
    fake = _FakeOpenAI("the home team will probably win")
    reasoner = OpenAICompatibleReasoner(Settings(), client=fake)
    with pytest.raises(ReasonerError):
        reasoner.reason({"baseline": {"winner": "home"}})


def test_oss_reasoner_disables_thinking_and_caps_tokens():
    fake = _FakeOpenAI('{"winner": "home", "home_score": 1, "away_score": 0, "rationale": "x"}')
    settings = Settings(llm_enable_thinking=False, llm_max_tokens=8192, llm_model="qwen3.5:9b")
    OpenAICompatibleReasoner(settings, client=fake).reason({"baseline": {"winner": "home"}})

    kw = fake.last_kwargs
    assert kw["model"] == "qwen3.5:9b"
    assert kw["max_tokens"] == 8192
    assert kw["messages"][0]["content"].endswith("/no_think")  # Qwen3 thinking off


def test_oss_reasoner_keeps_thinking_when_enabled():
    fake = _FakeOpenAI('{"winner": "home", "home_score": 1, "away_score": 0, "rationale": "x"}')
    settings = Settings(llm_enable_thinking=True)
    OpenAICompatibleReasoner(settings, client=fake).reason({"baseline": {"winner": "home"}})
    assert "/no_think" not in fake.last_kwargs["messages"][0]["content"]


def test_reason_context_carries_no_history():
    """Each call passes only the structured data for that prediction — no cross-call history."""
    fake = _FakeOpenAI('{"winner": "home", "home_score": 1, "away_score": 0, "rationale": "x"}')
    reasoner = OpenAICompatibleReasoner(Settings(), client=fake)
    reasoner.reason({"home_team": "A", "away_team": "B", "baseline": {"winner": "home"}})
    messages = fake.last_kwargs["messages"]
    assert len(messages) == 2  # system + single user turn, nothing else
    assert messages[1]["role"] == "user"
