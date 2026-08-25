from decimal import Decimal

from packages.marl.rewards import (
    CooperativeRewardConfig,
    HybridRewardConfig,
    calculate_agent_reward_breakdowns,
    calculate_cooperative_reward,
    shared_reward_map,
)


def test_cooperative_reward_uses_roi_only_when_an_operation_closes() -> None:
    breakdown = calculate_cooperative_reward(closed_operation_roi=Decimal("0.10"))

    assert breakdown.closed_operation_roi == Decimal("0.060")
    assert breakdown.extra_hold_days == Decimal("0")
    assert breakdown.invalid_purchase == Decimal("0")
    assert breakdown.total == Decimal("0.060")


def test_cooperative_reward_clips_an_exceptional_roi() -> None:
    breakdown = calculate_cooperative_reward(closed_operation_roi=Decimal("4"))

    assert breakdown.closed_operation_roi == Decimal("0.60")
    assert breakdown.total == Decimal("0.60")


def test_cooperative_reward_penalizes_days_after_the_normal_hold() -> None:
    breakdown = calculate_cooperative_reward(
        closed_operation_roi=Decimal("0.10"),
        extra_hold_days=4,
        config=CooperativeRewardConfig(
            roi_weight=Decimal("0.60"),
            extra_hold_day_penalty=Decimal("0.01"),
            constraint_violation_penalty=Decimal("0.80"),
        ),
    )

    assert breakdown.closed_operation_roi == Decimal("0.060")
    assert breakdown.extra_hold_days == Decimal("-0.04")
    assert breakdown.total == Decimal("0.020")


def test_cooperative_reward_penalizes_invalid_purchase_by_violated_share() -> None:
    breakdown = calculate_cooperative_reward(constraint_violation_ratio=Decimal("0.25"))

    assert breakdown.invalid_purchase == Decimal("-0.2000")
    assert breakdown.total == Decimal("-0.2000")


def test_shared_reward_map_returns_same_common_reward_for_every_agent() -> None:
    breakdown = calculate_cooperative_reward(closed_operation_roi=Decimal("0.2"))

    assert shared_reward_map(("scout", "trader", "portfolio"), breakdown) == {
        "scout": 0.12,
        "trader": 0.12,
        "portfolio": 0.12,
    }


def test_hybrid_reward_adds_extra_penalty_to_scout_for_a_bad_mark() -> None:
    shared_breakdown = calculate_cooperative_reward(closed_operation_roi=Decimal("-0.2"))

    rewards = calculate_agent_reward_breakdowns(
        agents=("scout", "trader", "portfolio"),
        shared_breakdown=shared_breakdown,
        closed_operation_roi=Decimal("-0.2"),
        scout_marked_closed_item=True,
        hybrid_config=HybridRewardConfig(shared_weight=Decimal("0.70")),
    )

    assert rewards["scout"].shared_component == Decimal("-0.084")
    assert rewards["scout"].individual_signal == Decimal("-0.2")
    assert rewards["scout"].total == Decimal("-0.144")
    assert rewards["trader"].total == Decimal("-0.084")
    assert rewards["portfolio"].total == Decimal("-0.084")


def test_hybrid_reward_penalizes_missed_profitable_opportunity_when_affordable() -> None:
    shared_breakdown = calculate_cooperative_reward()

    rewards = calculate_agent_reward_breakdowns(
        agents=("scout", "trader", "portfolio"),
        shared_breakdown=shared_breakdown,
        missed_opportunity_roi=Decimal("0.25"),
        missed_opportunity_affordable=True,
        trader_declined_viable_purchase=True,
    )

    assert rewards["scout"].individual_signal == Decimal("-0.25")
    assert rewards["trader"].individual_signal == Decimal("-0.25")
    assert rewards["portfolio"].individual_signal == Decimal("0")


def test_hybrid_reward_penalizes_portfolio_for_rejecting_a_viable_opportunity() -> None:
    rewards = calculate_agent_reward_breakdowns(
        agents=("scout", "trader", "portfolio"),
        shared_breakdown=calculate_cooperative_reward(),
        missed_opportunity_roi=Decimal("0.25"),
        portfolio_rejected_viable_purchase=True,
    )

    assert rewards["scout"].individual_signal == Decimal("0")
    assert rewards["trader"].individual_signal == Decimal("0")
    assert rewards["portfolio"].individual_signal == Decimal("-0.25")


def test_hybrid_reward_penalizes_roles_that_propose_or_approve_invalid_purchase() -> None:
    shared_breakdown = calculate_cooperative_reward(constraint_violation_ratio=Decimal("0.25"))

    rewards = calculate_agent_reward_breakdowns(
        agents=("scout", "trader", "portfolio"),
        shared_breakdown=shared_breakdown,
        trader_proposed_invalid_purchase=True,
        portfolio_approved_invalid_purchase=True,
        constraint_violation_ratio=Decimal("0.25"),
    )

    assert rewards["scout"].total == Decimal("-0.1400")
    assert rewards["trader"].total == Decimal("-0.2150")
    assert rewards["portfolio"].total == Decimal("-0.2150")
