"""Integration tests for Insurance API — create, confirm, resolve, list."""

import uuid as _uuid

import pytest
from httpx import AsyncClient

from app.users.models import User


# ===== Create insurance event =====


@pytest.mark.asyncio
async def test_create_insurance_event_success(
    async_client: AsyncClient,
    banker_headers: dict,
    two_seated_players: dict,
    sample_flop_cards: dict,
):
    table = two_seated_players["table"]
    buyer = two_seated_players["buyer"]
    opponent = two_seated_players["opponent"]

    resp = await async_client.post(
        f"/api/tables/{table['id']}/insurance",
        json={
            "buyer_id": str(buyer.id),
            "opponent_id": str(opponent.id),
            **sample_flop_cards,
        },
        headers=banker_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["outs"] >= 0
    assert data["total_combinations"] == 990  # flop
    assert 0 <= data["win_probability"] <= 1
    assert data["odds"] >= 0
    assert data["buyer_hand"] == sample_flop_cards["buyer_hand"]


@pytest.mark.asyncio
async def test_create_insurance_invalid_cards(
    async_client: AsyncClient,
    banker_headers: dict,
    two_seated_players: dict,
):
    table = two_seated_players["table"]
    buyer = two_seated_players["buyer"]
    opponent = two_seated_players["opponent"]

    # Duplicate card
    resp = await async_client.post(
        f"/api/tables/{table['id']}/insurance",
        json={
            "buyer_id": str(buyer.id),
            "opponent_id": str(opponent.id),
            "buyer_hand": ["As", "Kh"],
            "opponent_hand": ["As", "Qc"],
            "community_cards": ["Js", "Td", "3c"],
        },
        headers=banker_headers,
    )
    assert resp.status_code == 400
    assert "uplicate" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_create_insurance_wrong_card_count(
    async_client: AsyncClient,
    banker_headers: dict,
    two_seated_players: dict,
):
    table = two_seated_players["table"]
    buyer = two_seated_players["buyer"]
    opponent = two_seated_players["opponent"]

    # buyer_hand only 1 card → 422 (Pydantic validation)
    resp = await async_client.post(
        f"/api/tables/{table['id']}/insurance",
        json={
            "buyer_id": str(buyer.id),
            "opponent_id": str(opponent.id),
            "buyer_hand": ["As"],
            "opponent_hand": ["Qd", "Qc"],
            "community_cards": ["Js", "Td", "3c"],
        },
        headers=banker_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_insurance_player_not_seated(
    async_client: AsyncClient,
    banker_headers: dict,
    two_seated_players: dict,
    sample_flop_cards: dict,
):
    table = two_seated_players["table"]
    opponent = two_seated_players["opponent"]

    resp = await async_client.post(
        f"/api/tables/{table['id']}/insurance",
        json={
            "buyer_id": str(_uuid.uuid4()),  # not seated
            "opponent_id": str(opponent.id),
            **sample_flop_cards,
        },
        headers=banker_headers,
    )
    assert resp.status_code == 400
    assert "not seated" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_insurance_table_not_open(
    async_client: AsyncClient,
    banker_headers: dict,
    two_seated_players: dict,
    sample_flop_cards: dict,
):
    table = two_seated_players["table"]
    buyer = two_seated_players["buyer"]
    opponent = two_seated_players["opponent"]

    # Move to SETTLING
    await async_client.patch(
        f"/api/tables/{table['id']}/status",
        json={"status": "SETTLING"},
        headers=banker_headers,
    )

    resp = await async_client.post(
        f"/api/tables/{table['id']}/insurance",
        json={
            "buyer_id": str(buyer.id),
            "opponent_id": str(opponent.id),
            **sample_flop_cards,
        },
        headers=banker_headers,
    )
    assert resp.status_code == 400


# ===== Confirm insurance =====


async def _create_insurance_event(
    async_client: AsyncClient,
    banker_headers: dict,
    two_seated_players: dict,
    sample_flop_cards: dict,
) -> dict:
    """Helper: create an insurance event and return the response data."""
    table = two_seated_players["table"]
    buyer = two_seated_players["buyer"]
    opponent = two_seated_players["opponent"]

    resp = await async_client.post(
        f"/api/tables/{table['id']}/insurance",
        json={
            "buyer_id": str(buyer.id),
            "opponent_id": str(opponent.id),
            **sample_flop_cards,
        },
        headers=banker_headers,
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.asyncio
async def test_confirm_insurance_success(
    async_client: AsyncClient,
    banker_headers: dict,
    two_seated_players: dict,
    sample_flop_cards: dict,
):
    table = two_seated_players["table"]
    event = await _create_insurance_event(
        async_client, banker_headers, two_seated_players, sample_flop_cards
    )

    resp = await async_client.patch(
        f"/api/tables/{table['id']}/insurance/{event['id']}/confirm",
        json={"insured_amount": 500},
        headers=banker_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["insured_amount"] == 500

    # Verify INSURANCE_BUY transaction exists
    txn_resp = await async_client.get(
        f"/api/tables/{table['id']}/transactions?player_id={data['buyer_id']}",
        headers=banker_headers,
    )
    txns = txn_resp.json()["transactions"]
    insurance_buy_txns = [t for t in txns if t["type"] == "INSURANCE_BUY"]
    assert len(insurance_buy_txns) == 1
    assert insurance_buy_txns[0]["amount"] == -500


@pytest.mark.asyncio
async def test_confirm_insurance_already_confirmed(
    async_client: AsyncClient,
    banker_headers: dict,
    two_seated_players: dict,
    sample_flop_cards: dict,
):
    table = two_seated_players["table"]
    event = await _create_insurance_event(
        async_client, banker_headers, two_seated_players, sample_flop_cards
    )

    # First confirm
    await async_client.patch(
        f"/api/tables/{table['id']}/insurance/{event['id']}/confirm",
        json={"insured_amount": 500},
        headers=banker_headers,
    )

    # Second confirm should fail
    resp = await async_client.patch(
        f"/api/tables/{table['id']}/insurance/{event['id']}/confirm",
        json={"insured_amount": 300},
        headers=banker_headers,
    )
    assert resp.status_code == 400
    assert "already confirmed" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_confirm_insurance_invalid_amount(
    async_client: AsyncClient,
    banker_headers: dict,
    two_seated_players: dict,
    sample_flop_cards: dict,
):
    table = two_seated_players["table"]
    event = await _create_insurance_event(
        async_client, banker_headers, two_seated_players, sample_flop_cards
    )

    # amount=0 → 422
    resp = await async_client.patch(
        f"/api/tables/{table['id']}/insurance/{event['id']}/confirm",
        json={"insured_amount": 0},
        headers=banker_headers,
    )
    assert resp.status_code == 422

    # amount=-100 → 422
    resp = await async_client.patch(
        f"/api/tables/{table['id']}/insurance/{event['id']}/confirm",
        json={"insured_amount": -100},
        headers=banker_headers,
    )
    assert resp.status_code == 422


# ===== Resolve insurance =====


@pytest.mark.asyncio
async def test_resolve_insurance_hit(
    async_client: AsyncClient,
    banker_headers: dict,
    two_seated_players: dict,
    sample_flop_cards: dict,
):
    table = two_seated_players["table"]
    event = await _create_insurance_event(
        async_client, banker_headers, two_seated_players, sample_flop_cards
    )

    # Confirm
    await async_client.patch(
        f"/api/tables/{table['id']}/insurance/{event['id']}/confirm",
        json={"insured_amount": 500},
        headers=banker_headers,
    )

    # Resolve — hit (buyer wins insurance)
    # final cards: original 3 flop cards + 2 more
    final_cards = sample_flop_cards["community_cards"] + ["4h", "9h"]
    resp = await async_client.patch(
        f"/api/tables/{table['id']}/insurance/{event['id']}/resolve",
        json={"is_hit": True, "final_community_cards": final_cards},
        headers=banker_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_hit"] is True
    assert data["payout_amount"] == int(500 * event["odds"])

    # Verify INSURANCE_PAYOUT transaction
    txn_resp = await async_client.get(
        f"/api/tables/{table['id']}/transactions?player_id={data['buyer_id']}",
        headers=banker_headers,
    )
    txns = txn_resp.json()["transactions"]
    payout_txns = [t for t in txns if t["type"] == "INSURANCE_PAYOUT"]
    assert len(payout_txns) == 1
    assert payout_txns[0]["amount"] == data["payout_amount"]


@pytest.mark.asyncio
async def test_resolve_insurance_miss(
    async_client: AsyncClient,
    banker_headers: dict,
    two_seated_players: dict,
    sample_flop_cards: dict,
):
    table = two_seated_players["table"]
    event = await _create_insurance_event(
        async_client, banker_headers, two_seated_players, sample_flop_cards
    )

    # Confirm
    await async_client.patch(
        f"/api/tables/{table['id']}/insurance/{event['id']}/confirm",
        json={"insured_amount": 500},
        headers=banker_headers,
    )

    # Resolve — miss
    final_cards = sample_flop_cards["community_cards"] + ["4d", "9c"]
    resp = await async_client.patch(
        f"/api/tables/{table['id']}/insurance/{event['id']}/resolve",
        json={"is_hit": False, "final_community_cards": final_cards},
        headers=banker_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_hit"] is False
    assert data["payout_amount"] == 0

    # No INSURANCE_PAYOUT transaction
    txn_resp = await async_client.get(
        f"/api/tables/{table['id']}/transactions?player_id={data['buyer_id']}",
        headers=banker_headers,
    )
    txns = txn_resp.json()["transactions"]
    payout_txns = [t for t in txns if t["type"] == "INSURANCE_PAYOUT"]
    assert len(payout_txns) == 0


@pytest.mark.asyncio
async def test_resolve_insurance_not_confirmed(
    async_client: AsyncClient,
    banker_headers: dict,
    two_seated_players: dict,
    sample_flop_cards: dict,
):
    table = two_seated_players["table"]
    event = await _create_insurance_event(
        async_client, banker_headers, two_seated_players, sample_flop_cards
    )

    # Try resolve without confirm
    final_cards = sample_flop_cards["community_cards"] + ["4d", "9c"]
    resp = await async_client.patch(
        f"/api/tables/{table['id']}/insurance/{event['id']}/resolve",
        json={"is_hit": True, "final_community_cards": final_cards},
        headers=banker_headers,
    )
    assert resp.status_code == 400
    assert "not yet confirmed" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_resolve_insurance_already_resolved(
    async_client: AsyncClient,
    banker_headers: dict,
    two_seated_players: dict,
    sample_flop_cards: dict,
):
    table = two_seated_players["table"]
    event = await _create_insurance_event(
        async_client, banker_headers, two_seated_players, sample_flop_cards
    )

    # Confirm + resolve
    await async_client.patch(
        f"/api/tables/{table['id']}/insurance/{event['id']}/confirm",
        json={"insured_amount": 500},
        headers=banker_headers,
    )
    final_cards = sample_flop_cards["community_cards"] + ["4d", "9c"]
    await async_client.patch(
        f"/api/tables/{table['id']}/insurance/{event['id']}/resolve",
        json={"is_hit": False, "final_community_cards": final_cards},
        headers=banker_headers,
    )

    # Second resolve should fail
    resp = await async_client.patch(
        f"/api/tables/{table['id']}/insurance/{event['id']}/resolve",
        json={"is_hit": True, "final_community_cards": final_cards},
        headers=banker_headers,
    )
    assert resp.status_code == 400
    assert "already resolved" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_resolve_community_cards_mismatch(
    async_client: AsyncClient,
    banker_headers: dict,
    two_seated_players: dict,
    sample_flop_cards: dict,
):
    table = two_seated_players["table"]
    event = await _create_insurance_event(
        async_client, banker_headers, two_seated_players, sample_flop_cards
    )

    # Confirm
    await async_client.patch(
        f"/api/tables/{table['id']}/insurance/{event['id']}/confirm",
        json={"insured_amount": 500},
        headers=banker_headers,
    )

    # Resolve with mismatched community cards (first 3 differ from original)
    resp = await async_client.patch(
        f"/api/tables/{table['id']}/insurance/{event['id']}/resolve",
        json={
            "is_hit": True,
            "final_community_cards": ["Ac", "Kd", "Qh", "4d", "9c"],
        },
        headers=banker_headers,
    )
    assert resp.status_code == 400
    assert "community cards" in resp.json()["detail"].lower()


# ===== Query =====


@pytest.mark.asyncio
async def test_list_insurance_events(
    async_client: AsyncClient,
    banker_headers: dict,
    two_seated_players: dict,
    sample_flop_cards: dict,
    sample_turn_cards: dict,
):
    table = two_seated_players["table"]
    buyer = two_seated_players["buyer"]
    opponent = two_seated_players["opponent"]

    # Create 2 events
    await async_client.post(
        f"/api/tables/{table['id']}/insurance",
        json={
            "buyer_id": str(buyer.id),
            "opponent_id": str(opponent.id),
            **sample_flop_cards,
        },
        headers=banker_headers,
    )
    await async_client.post(
        f"/api/tables/{table['id']}/insurance",
        json={
            "buyer_id": str(buyer.id),
            "opponent_id": str(opponent.id),
            **sample_turn_cards,
        },
        headers=banker_headers,
    )

    resp = await async_client.get(
        f"/api/tables/{table['id']}/insurance",
        headers=banker_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["events"]) == 2


# ===== Balance accuracy =====


@pytest.mark.asyncio
async def test_insurance_transactions_balance(
    async_client: AsyncClient,
    banker_headers: dict,
    two_seated_players: dict,
    sample_flop_cards: dict,
):
    table = two_seated_players["table"]
    buyer = two_seated_players["buyer"]
    opponent = two_seated_players["opponent"]

    # Initial buy-in was 5000 (from two_seated_players fixture)
    # Create insurance event
    event_resp = await async_client.post(
        f"/api/tables/{table['id']}/insurance",
        json={
            "buyer_id": str(buyer.id),
            "opponent_id": str(opponent.id),
            **sample_flop_cards,
        },
        headers=banker_headers,
    )
    event = event_resp.json()

    # Confirm with insured_amount=200
    await async_client.patch(
        f"/api/tables/{table['id']}/insurance/{event['id']}/confirm",
        json={"insured_amount": 200},
        headers=banker_headers,
    )

    # Check balance: 5000 - 200 = 4800
    txn_resp = await async_client.get(
        f"/api/tables/{table['id']}/transactions?player_id={str(buyer.id)}",
        headers=banker_headers,
    )
    txns = txn_resp.json()["transactions"]
    buy_txn = [t for t in txns if t["type"] == "INSURANCE_BUY"][0]
    assert buy_txn["balance_after"] == 4800

    # Resolve — hit
    final_cards = sample_flop_cards["community_cards"] + ["4h", "9h"]
    await async_client.patch(
        f"/api/tables/{table['id']}/insurance/{event['id']}/resolve",
        json={"is_hit": True, "final_community_cards": final_cards},
        headers=banker_headers,
    )

    # Check payout balance
    txn_resp2 = await async_client.get(
        f"/api/tables/{table['id']}/transactions?player_id={str(buyer.id)}",
        headers=banker_headers,
    )
    txns2 = txn_resp2.json()["transactions"]
    payout_txn = [t for t in txns2 if t["type"] == "INSURANCE_PAYOUT"][0]
    payout_amount = int(200 * event["odds"])
    assert payout_txn["amount"] == payout_amount
    assert payout_txn["balance_after"] == 4800 + payout_amount
