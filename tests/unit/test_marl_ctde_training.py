import torch

from packages.marl.ctde_training import _masked_logits, _models


def test_masked_logits_excludes_an_impossible_action() -> None:
    logits = torch.tensor([0.0, 0.2, 1.0])

    masked = _masked_logits(logits, (1, 1, 0))

    assert int(torch.argmax(masked).item()) == 1
    assert masked[2] < -1e30


def test_default_actors_start_with_neutral_logits() -> None:
    actors, _evaluator = _models()

    for actor in actors.values():
        observation = torch.zeros(actor.network[0].in_features)
        logits = actor(observation)

        assert torch.allclose(logits, torch.zeros_like(logits))
