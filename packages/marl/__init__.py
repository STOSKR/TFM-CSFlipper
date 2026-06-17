"""MARL environment scaffolding for CSFlipper."""

from packages.marl.episodes import load_market_episode_steps
from packages.marl.market_env import (
    AGENT_IDS,
    AGENT_SPECS,
    AgentSpec,
    MarketEpisodeStep,
    MarketMARLEnvironment,
)
from packages.marl.rewards import (
    CooperativeRewardBreakdown,
    CooperativeRewardConfig,
    calculate_cooperative_reward,
)
from packages.marl.rllib_adapter import market_env_creator, register_market_env

__all__ = [
    "AGENT_IDS",
    "AGENT_SPECS",
    "AgentSpec",
    "MarketEpisodeStep",
    "MarketMARLEnvironment",
    "CooperativeRewardBreakdown",
    "CooperativeRewardConfig",
    "calculate_cooperative_reward",
    "load_market_episode_steps",
    "market_env_creator",
    "register_market_env",
]
