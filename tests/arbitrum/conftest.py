import pytest
from brownie import config
from brownie import Contract
from brownie import interface, StrategyInsurance, project, accounts

 # TODO - Pull from coingecko
DQUICK_PRICE = 159.41
FTM_PRICE = 1.57
WETH_PRICE = 3470
WBTC_PRICE = 46000
SPOOKY_PRICE = 11.78
SPIRIT_PRICE = 5.78
ZIP_PRICE = 0.01
SUSHI_PRICE = 1.7

SUSHI_FARM = '0xF4d73326C13a4Fc5FD7A064217e12780e9Bd62c3'

ORACLE = '0xb56c2F0B653B2e0b10C9b928C8580Ac5Df02C7C7'

POOL_ADDRESS_PROVIDER = '0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb'
# Tokens
USDC = '0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8'
USDC_WHALE = '0x489ee077994B6658eAfA855C308275EAd8097C4A'
WETH_WHALE = '0x489ee077994B6658eAfA855C308275EAd8097C4A'
SUSHI = '0xd4d42F0b6DEF4CE0383636770eF773390d85c61A'


SUSHISWAP_ROUTER = '0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506'
CONFIG = {
    'USDCWETHSUSHI': {
        'token': USDC,
        'whale': USDC_WHALE,
        'shortWhale' : WETH_WHALE,
        'deposit': 1e6,
        'harvest_token': SUSHI,
        'harvest_token_price': SUSHI_PRICE * 1e-12,
        'harvest_token_whale': '0x9873795F5DAb11e1c0342C4a58904c59827ede0c',
        'lp_token': '0x905dfCD5649217c42684f23958568e533C711Aa3',
        'lp_whale': '0xA626Bd40A8c88F59A4CF9b1821A7bD71faD96285',
        'lp_farm': SUSHI_FARM,
        'pid': 0,
        'router': SUSHISWAP_ROUTER,
    },

}


@pytest.fixture
def strategy_contract():
    yield  project.CoreStrategyProject.USDCWETHSUSHI


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
    amount = min(amount, int(0.005*token.balanceOf(conf['lp_token'])))

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
def strategy(strategist, keeper, vault, strategy_contract, gov):
    # strategy = strategy_contract.deploy(vault, {'from': strategist,'gas_limit': 20000000})
    strategy = strategist.deploy(strategy_contract, vault)
    insurance = strategist.deploy(StrategyInsurance, strategy)
    strategy.setKeeper(keeper)
    strategy.setInsurance(insurance, {'from': gov})
    vault.addStrategy(strategy, 10_000, 0, 2 ** 256 - 1, 1_000, {"from": gov})
    yield strategy


@pytest.fixture(scope="session")
def RELATIVE_APPROX():
    yield 1e-5

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
    yield interface.IMiniChefV2(conf['lp_farm'])

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
    
    print("Vault: ",token.balanceOf(vault.address))
    print("Strategy: ",token.balanceOf(strategy.address))
    strategy.harvest()
    strat = strategy
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
    
    print("Vault: ",token.balanceOf(vault.address))
    print("Strategy: ",token.balanceOf(strategy_mock_oracle.address))
    strategy_mock_oracle.harvest()
    strat = strategy_mock_oracle
    assert pytest.approx(strategy_mock_oracle.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount
    yield vault 

@pytest.fixture
def strategy_mock_oracle(token, amount, user, strategist, keeper, vault, strategy_contract, gov, MockAaveOracle):
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
    yield strategy_mock_oracle


# Function scoped isolation fixture to enable xdist.
# Snapshots the chain before each test and reverts after test completion.
@pytest.fixture(scope="function", autouse=True)
def shared_setup(fn_isolation):
    pass


