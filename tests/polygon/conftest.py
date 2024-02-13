import pytest
from brownie import config
from brownie import Contract
from brownie import interface, StrategyInsurance, project, accounts

 # TODO - Pull from coingecko
DQUICK_PRICE = 75.05

ORACLE = '0xEBd36016B3eD09D4693Ed4251c67Bd858c3c7C9C'
POOL_ADDRESS_PROVIDER = '0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb'

WMATICWHALE = "0x6Ffe747579eD4E807Dec9B40dBA18D15226c32dC"
WETHWHALE =  "0x3fd939B017b31eaADF9ae50C7fF7Fa5c0661d47C"

QUICK_FARM = "0x14977e7E263FF79c4c3159F497D9551fbE769625"

USDC = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
DQUICK = "0xf28164A485B0B2C90639E47b0f377b4a438a16B1"
WMATIC = "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270"

QUICKSWAP_ROUTER = "0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff"
SUSHISWAP_ROUTER = "0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506"

CONFIG = {
    "USDCWMATICQuick": {
        "token": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
        "whale": "0x1205f31718499dBf1fCa446663B532Ef87481fe1",
        'shortWhale' : WMATICWHALE,
        "deposit": 1e6,
        "harvest_token": "0xf28164A485B0B2C90639E47b0f377b4a438a16B1",
        "harvest_token_price": DQUICK_PRICE * 1e-12,
        "harvest_token_whale": "0x649aa6e6b6194250c077df4fb37c23ee6c098513",
        "lp_token": "0x6e7a5FAFcec6BB1e78bAE2A1F0B612012BF14827",
        "lp_whale": "0x14977e7E263FF79c4c3159F497D9551fbE769625",
        "lp_farm": "0x14977e7E263FF79c4c3159F497D9551fbE769625",
        "pid": 0,
        "router": QUICKSWAP_ROUTER,
    },
    "USDCWETHQuick": {
        "token": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
        "whale": "0x1205f31718499dBf1fCa446663B532Ef87481fe1",
        'shortWhale' : WETHWHALE,
        "deposit": 1e6,
        "harvest_token": "0xf28164A485B0B2C90639E47b0f377b4a438a16B1",
        "harvest_token_price": DQUICK_PRICE * 1e-12,
        "harvest_token_whale": "0x649aa6e6b6194250c077df4fb37c23ee6c098513",
        "lp_token": "0x853Ee4b2A13f8a742d64C8F088bE7bA2131f670d",
        "lp_whale": "0xbB703E95348424FF9e94fbE4FB524f6d280331B8",
        "lp_farm": "0xbB703E95348424FF9e94fbE4FB524f6d280331B8",
        "pid": 0,
        "router": QUICKSWAP_ROUTER,
    },

}

@pytest.fixture
def strategy_contract():
    yield  project.CoreStrategyProject.USDCWMATICQuick


@pytest.fixture
def conf(strategy_contract):
    yield CONFIG[strategy_contract._name]

@pytest.fixture
def gov(accounts):
    #yield accounts.at("0x7601630eC802952ba1ED2B6e4db16F699A0a5A87", force=True)
    yield accounts[1]

@pytest.fixture
def user(accounts):
    yield accounts[0]


@pytest.fixture
def rewards(accounts):
    yield accounts[1]


@pytest.fixture
def guardian(accounts):
    yield accounts[2]


@pytest.fixture
def management(accounts):
    yield accounts[3]


@pytest.fixture
def strategist(accounts):
    yield accounts[4]


@pytest.fixture
def keeper(accounts):
    yield accounts[5]


@pytest.fixture
def token(conf):
    yield interface.IERC20Extended(conf['token'])

@pytest.fixture
def router(conf):
    yield interface.IUniswapV2Router01(conf['router'])



@pytest.fixture
def whale(token, conf ,Contract, accounts) : 
    yield accounts.at(conf['whale'], True)

@pytest.fixture
def shortWhale(token, conf ,Contract, accounts) : 
    yield accounts.at(conf['shortWhale'], True)


@pytest.fixture
def amount(accounts, token, user, conf, whale):
    amount = 10_000 * 10 ** token.decimals()
    amount = min(amount, int(0.5*token.balanceOf(whale)))
    amount = min(amount, int(0.05*token.balanceOf(conf['lp_token'])))

    # In order to get some funds for the token you are about to use,
    # it impersonate an exchange address to use it's funds.
    reserve = accounts.at(whale, force=True)
    token.transfer(user, amount, {"from": reserve})
    yield amount

@pytest.fixture
def large_amount(accounts, token, user, conf, whale):
    amount = 10_000_000 * 10 ** token.decimals()
    # In order to get some funds for the token you are about to use,
    # it impersonate an exchange address to use it's funds.
    reserve = accounts.at(whale, force=True)

    amount = min(amount, int(0.5*token.balanceOf(reserve)))
    amount = min(amount, int(0.2*token.balanceOf(conf['lp_token'])))
    token.transfer(user, amount, {"from": reserve})
    yield amount


@pytest.fixture
def weth():
    token_address = "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270"
    yield interface.IERC20Extended(token_address)


@pytest.fixture
def weth_amout(user, weth):
    weth_amout = 10 ** weth.decimals()
    user.transfer(weth, weth_amout)
    yield weth_amout


@pytest.fixture
def vault(pm, gov, rewards, guardian, management, token):
    Vault = pm(config["dependencies"][0]).Vault
    vault = guardian.deploy(Vault)
    vault.initialize(token, gov, rewards, "", "", guardian, management)
    vault.setDepositLimit(2 ** 256 - 1, {"from": gov})
    vault.setManagement(management, {"from": gov})
    assert vault.token() == token.address
    yield vault

@pytest.fixture
def collatTarget():
    return 3500

@pytest.fixture
def collatLimit():
    return 4900



@pytest.fixture
def strategy(strategist, keeper, vault, strategy_contract, gov, collatTarget, collatLimit):
    # strategy = strategy_contract.deploy(vault, {'from': strategist,'gas_limit': 20000000})
    strategy = strategist.deploy(strategy_contract, vault)
    insurance = strategist.deploy(StrategyInsurance, strategy)
    strategy.setKeeper(keeper)
    strategy.setInsurance(insurance, {'from': gov})
    vault.addStrategy(strategy, 10_000, 0, 2 ** 256 - 1, 1_000, {"from": gov})

    # Custom values for the collateral of the strategies, comment out if the default ones are ok
    strategy.setCollateralThresholds(collatTarget - 700, collatTarget, collatTarget + 700, collatLimit)
    yield strategy

@pytest.fixture
def strategy_mock_oracle(token, amount, user, strategist, keeper, vault, strategy_contract, gov, MockAaveOracle, collatTarget, collatLimit):
    pool_address_provider = interface.IPoolAddressesProvider(POOL_ADDRESS_PROVIDER)
    old_oracle = pool_address_provider.getPriceOracle()
    # Set the mock price oracle
    oracle = MockAaveOracle.deploy(old_oracle, {'from': accounts[0]})

    admin = accounts.at(pool_address_provider.owner(), True)
    pool_address_provider.setPriceOracle(oracle, {'from': admin})

    strategy_mock_oracle = strategist.deploy(strategy_contract, vault)
    insurance = strategist.deploy(StrategyInsurance, strategy_mock_oracle)
    strategy_mock_oracle.setKeeper(keeper)
    strategy_mock_oracle.setInsurance(insurance, {'from': gov})
    vault.addStrategy(strategy_mock_oracle, 10_000, 0, 2 ** 256 - 1, 1_000, {"from": gov})

    # Custom values for the collateral of the strategies, comment out if the default ones are ok
    strategy_mock_oracle.setCollateralThresholds(collatTarget - 700, collatTarget, collatTarget + 700, collatLimit)
    yield strategy_mock_oracle


@pytest.fixture(scope="session")
def RELATIVE_APPROX():
    yield 1e-4

@pytest.fixture
def lp_token(conf):
    yield interface.ERC20(conf['lp_token'])

@pytest.fixture
def lp_whale(accounts, conf):
    yield accounts.at(conf['lp_whale'], True)

@pytest.fixture
def harvest_token(conf):
    yield interface.ERC20(conf['harvest_token'])

@pytest.fixture
def harvest_token_whale(conf, accounts):
    yield accounts.at(conf['harvest_token_whale'], True)

@pytest.fixture
def pid(conf):
    yield conf['pid']

@pytest.fixture
def lp_farm(conf):
    yield interface.IVectorPoolHelper(conf['lp_farm'])

@pytest.fixture
def lp_price(token, lp_token):
    yield (token.balanceOf(lp_token) * 2) / lp_token.totalSupply()  

@pytest.fixture
def deployed_vault(chain, accounts, gov, token, vault, strategy, user, strategist, amount, RELATIVE_APPROX):
    # Deposit to the vault
    token.approve(vault.address, amount, {"from": user})
    print("Amount: ", amount)
    print("User: ", user)
    vault.deposit(amount, {"from": user})
    assert token.balanceOf(vault.address) == amount
    
    # harvest
    chain.sleep(1)
    chain.mine(1)
    
    print("Vault: ",token.balanceOf(vault.address))
    print("Strategy: ",token.balanceOf(strategy.address))
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount
    yield vault 

@pytest.fixture
def deployed_vault_large_deposit(chain, accounts, gov, token, vault, strategy, user, strategist, large_amount, RELATIVE_APPROX):
    # Deposit to the vault
    token.approve(vault.address, large_amount, {"from": user})
    vault.deposit(large_amount, {"from": user})
    assert token.balanceOf(vault.address) == large_amount
    
    # harvest
    chain.sleep(1)
    chain.mine(1)
    #strategy.approveContracts({'from':gov})
    strategy.harvest()
    strat = strategy
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == large_amount
    yield vault  


@pytest.fixture
def strategy_mock_initialized_vault(chain, accounts, gov, token, vault, strategy_mock_oracle, user, strategist, amount, RELATIVE_APPROX):
    # Deposit to the vault
    token.approve(vault.address, amount, {"from": user})
    print("Amount: ", amount)
    print("User: ", user)
    vault.deposit(amount, {"from": user})
    assert token.balanceOf(vault.address) == amount
    
    # harvest
    chain.sleep(1)
    chain.mine(1)

    print("Vault: ",token.balanceOf(vault.address))
    print("Strategy: ",token.balanceOf(strategy_mock_oracle.address))
    strategy_mock_oracle.harvest()
    strat = strategy_mock_oracle
    assert pytest.approx(strategy_mock_oracle.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount
    yield vault 




# Function scoped isolation fixture to enable xdist.
# Snapshots the chain before each test and reverts after test completion.
@pytest.fixture(scope="function", autouse=True)
def shared_setup(fn_isolation):
    pass


