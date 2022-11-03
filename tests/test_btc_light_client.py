import pytest
import brownie
from web3 import Web3
from brownie import accounts
from .utils import expect_event, get_tracker
from .common import register_relayer
from .btc_block_data import btc_block_data


@pytest.fixture(scope="module", autouse=True)
def set_up(system_reward):
    register_relayer()
    # deposit to system reward contract
    accounts[0].transfer(system_reward.address, Web3.toWei(10, 'ether'))


@pytest.fixture(autouse=True)
def isolation():
    pass


def test_store_zero_block(btc_light_client):
    tx = btc_light_client.storeBlockHeader("0x0")
    expect_event(tx, "StoreHeaderFailed", {'returnCode': "10030"})


def test_store_wrong_length_block(btc_light_client):
    tx = btc_light_client.storeBlockHeader(btc_block_data[0][:80])
    expect_event(tx, "StoreHeaderFailed", {"returnCode": "10090"})


def test_store_change_nonce_block(btc_light_client):
    tx = btc_light_client.storeBlockHeader(btc_block_data[0][:80] + '00')
    expect_event(tx, "StoreHeaderFailed", {"returnCode": "10090"})


def test_store_block_success(btc_light_client):
    tx = btc_light_client.storeBlockHeader(btc_block_data[0])
    expect_event(tx, 'StoreHeader', {'height': '717697'})
    tx = btc_light_client.storeBlockHeader(btc_block_data[1])
    expect_event(tx, 'StoreHeader', {'height': '717698'})
    tx = btc_light_client.storeBlockHeader(btc_block_data[2])
    expect_event(tx, 'StoreHeader', {'height': '717699'})

    assert btc_light_client.isHeaderSynced("0x00000000000000000000794d6f4f6ee1c09e69a81469d7456e67be3d724223fb") is True
    assert btc_light_client.getSubmitter("0x00000000000000000000794d6f4f6ee1c09e69a81469d7456e67be3d724223fb") == accounts[0]


def test_get_submitter(btc_light_client):
    assert btc_light_client.getSubmitter("0x00000000000000000000794d6f4f6ee1c09e69a81469d7456e67be3d724223fb") == accounts[0]
    assert btc_light_client.getSubmitter("0x00000000000000000002c1572ed018e38f173f06dd9ab1de99ca4b8e276a65f5") == accounts[0]
    assert btc_light_client.getSubmitter("0x000000000000000000052c338c6d40ee82a9df507dd3597675dcf6fe6a66ea46") == accounts[0]


def test_store_no_previous_block(btc_light_client):
    tx = btc_light_client.storeBlockHeader(btc_block_data[4])
    expect_event(tx, "StoreHeaderFailed", {"returnCode": "10030"})
    tx = btc_light_client.storeBlockHeader(btc_block_data[2000])
    expect_event(tx, "StoreHeaderFailed", {"returnCode": "10030"})


def test_store_duplicate_block(btc_light_client):
    for data in btc_block_data[:3]:
        with brownie.reverts("can't sync duplicated header"):
            btc_light_client.storeBlockHeader(data)


def test_distribute_relayer_reward(btc_light_client, system_reward):
    chain_tip = btc_light_client.getChainTip()
    idx = btc_light_client.getHeight(chain_tip) - btc_light_client.INIT_CHAIN_HEIGHT()
    count_in_round = btc_light_client.countInRound()
    before_reward = btc_light_client.relayerRewardVault(accounts[0])

    while True:
        btc_light_client.storeBlockHeader(btc_block_data[idx])
        idx += 1
        count_in_round = btc_light_client.countInRound()
        if count_in_round == 0:
            # already distributed reward
            break

    after_reward = btc_light_client.relayerRewardVault(accounts[0])
    assert after_reward > before_reward

    if after_reward > brownie.web3.eth.get_balance(system_reward.address):
        after_reward = brownie.web3.eth.get_balance(system_reward.address)

    tracker = get_tracker(accounts[0])
    # claim reward
    tx = btc_light_client.claimRelayerReward(accounts[0], {'from': accounts[1]})
    assert tracker.delta() == after_reward
    expect_event(tx, "rewardTo", {"to": accounts[0], "amount": after_reward})


def test_get_prev_hash(btc_light_client):
    prev_hash = "0x0"
    btc_light_client.setBlock('0x1', '0x0', accounts[0].address, accounts[0].address)
    assert btc_light_client.getPrevHash('0x1') == prev_hash


def test_get_candidate(btc_light_client):
    candidate = accounts[1].address
    btc_light_client.setBlock('0x1', '0x0', accounts[0].address, candidate)
    assert btc_light_client.getCandidate('0x1') == candidate


def test_get_reward_address(btc_light_client):
    reward_address = accounts[1].address
    btc_light_client.setBlock('0x1', '0x0', reward_address, accounts[0].address)
    assert btc_light_client.getRewardAddress('0x1') == reward_address


def test_get_score(btc_light_client):
    btc_light_client.setBlock('0x1', '0x0', accounts[1].address, accounts[0].address)
    assert btc_light_client.getScore('0x1') == btc_light_client.mockScore()


def test_get_height(btc_light_client):
    btc_light_client.setBlock('0x1', '0x0', accounts[1].address, accounts[0].address)
    assert btc_light_client.getHeight('0x1') == btc_light_client._blockHeight()


def test_get_adjustment_index(btc_light_client):
    btc_light_client.setBlock('0x1', '0x0', accounts[1].address, accounts[0].address)
    assert btc_light_client.getAdjustmentIndex('0x1') == btc_light_client.mockAdjustment()


def test_get_round_powers(btc_light_client):
    btc_light_client.setMiners(1, accounts[0], accounts[2:3])
    btc_light_client.setMiners(1, accounts[1], accounts[3:5])
    round_powers = btc_light_client.getRoundPowers(1, accounts[:2])
    assert round_powers == [1, 2]


def test_get_round_miners(btc_light_client):
    miners = accounts[1:3]
    btc_light_client.setMiners(1, accounts[0], miners)
    result = btc_light_client.getRoundMiners(1, accounts[0])
    assert len(result) == 2
    for miner in result:
        assert miner in miners


def test_get_round_candidates(btc_light_client):
    candidates = accounts[:2]
    btc_light_client.setCandidates(1, candidates)
    result = btc_light_client.getRoundCandidates(1)
    assert len(result) == 2
    for c in candidates:
        assert c in result


