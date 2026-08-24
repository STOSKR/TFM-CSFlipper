from packages.marl.market_env import AGENT_IDS, AGENT_SPECS, MarketMARLEnvironment
from packages.marl.rllib_training import (
    RLLibMarketEnv,
    RLLibTrainingConfig,
    build_ppo_config,
)


def test_rllib_market_env_exposes_vector_spaces_and_steps() -> None:
    env = RLLibMarketEnv({"limit": 1})

    observations, infos = env.reset()

    assert set(observations) == set(AGENT_IDS)
    assert observations["scout"].shape == (len(AGENT_SPECS["scout"].observation_fields),)
    assert env.agent_observation_space("trader").shape == (
        len(AGENT_SPECS["trader"].observation_fields),
    )
    assert env.central_state_space().shape == (len(MarketMARLEnvironment.central_state_fields),)
    assert env.central_state().shape == env.central_state_space().shape
    assert env.agent_action_space("portfolio").n == 2
    assert infos["scout"]["route_selection"] == "candidate"
    assert infos["__common__"]["central_state"].shape == env.central_state_space().shape

    next_observations, rewards, terminations, truncations, step_infos = env.step(
        {"scout": 0, "trader": 0, "portfolio": 0}
    )

    assert set(rewards) == set(AGENT_IDS)
    assert "__all__" in terminations
    assert "__all__" in truncations
    assert step_infos["trader"]["cashflow"]["cash_destination"] == "reinvest"
    assert step_infos["__common__"]["central_state"].shape == env.central_state_space().shape
    assert next_observations

    final_observations = next_observations
    final_terminations = terminations
    final_infos = step_infos
    while final_observations:
        final_observations, _rewards, final_terminations, _truncations, final_infos = env.step(
            {"scout": 0, "trader": 0, "portfolio": 0}
        )

    assert final_observations == {}
    assert final_terminations["__all__"] is True
    assert final_infos == {}


def test_build_ppo_config_declares_one_policy_per_agent() -> None:
    config = build_ppo_config(
        env_name="csflipper-test",
        training_config=RLLibTrainingConfig(limit=8),
    )

    assert config.env == "csflipper-test"
    assert set(config.policies) == set(AGENT_IDS)
    assert config.count_steps_by == "env_steps"
