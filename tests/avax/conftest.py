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

VTX = '0x5817D4F0b62A59b17f75207DA1848C2cE75e7AF4'
VTX_PRICE = .2

WETH = '0x49D5c2BdFfac6CE2BFdB6640F4F80f226bc10bAB'
WETH_WHALE = '0x9ab2De34A33fB459b538c43f251eB825645e8595'

WAVAX = '0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7'
WAVAX_WHALE = '0x0e082F06FF657D94310cB8cE8B0D9a04541d8052'

BTCB = '0x152b9d0fdc40c096757f570a51e494bd4b943e50'
BTCB_WHALE = '0x209a0399a2905900c0d1a9a382fe23e37024dc84'

ORACLE = '0xEBd36016B3eD09D4693Ed4251c67Bd858c3c7C9C'
JOE_FARM = '0x4483f0b6e2F5486D06958C20f8C39A7aBe87bf8F'
POOL_ADDRESS_PROVIDER = '0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb'
# Tokens
USDC = '0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E'
USDC_WHALE = '0xB715808a78F6041E46d61Cb123C9B4A27056AE9C'

USDT = '0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7'
USDT_WHALE = '0x74b651eff97871ea99fcc14423e611d85eb0ea93'

SHORT_WHALE = '0xFE15c2695F1F920da45C30AAE47d11dE51007AF9'
JOE = '0x6e84a6216eA6dACC71eE8E6b0a5B7322EEbC0fDd'
JOE_PRICE = 0.19

JOE_ROUTER = '0x60aE616a2155Ee3d9A68541Ba4544862310933d4'
CONFIG = {
    'USDCWAVAXJOE': {
        'token': USDC,
        'whale': USDC_WHALE,
        'shortWhale' : SHORT_WHALE,
        'deposit': 1e6,
        'harvest_token': JOE,
        'harvest_token_price': JOE_PRICE * 1e-12,
        'harvest_token_whale': '0x1a731B2299E22FbAC282E7094EdA41046343Cb51',
        'lp_token': '0xf4003F4efBE8691B60249E6afbD307aBE7758adb',
        'lp_whale': '0x188bED1968b795d5c9022F6a0bb5931Ac4c18F00',
        'lp_farm': JOE_FARM,
        'pid': 0,
        'router': JOE_ROUTER,
    },
    'USDCWAVAXVTX': {
        'token': USDC,
        'whale': USDC_WHALE,
        'shortWhale' : SHORT_WHALE,
        'deposit': 1e6,
        'harvest_token': JOE,
        'harvest_token_price': JOE_PRICE * 1e-12,
        'harvest_token_whale': '0x1a731B2299E22FbAC282E7094EdA41046343Cb51',
        'lp_token': '0xf4003F4efBE8691B60249E6afbD307aBE7758adb',
        'lp_whale': JOE_FARM,
        'lp_farm': '0x7854B77c252dA067AcB59C4A25DCd407764Bd8eE',
        'pid': 0,
        'router': JOE_ROUTER,
    },
    'WAVAXUSDCVTX': {
        'token': WAVAX,
        'whale': WAVAX_WHALE,
        'shortWhale' : '0x1da20Ac34187b2d9c74F729B85acB225D3341b25',
        'deposit': 1e6,
        'harvest_token': JOE,
        'harvest_token_price': JOE_PRICE / 1000,
        'harvest_token_whale': '0x1a731B2299E22FbAC282E7094EdA41046343Cb51',
        'lp_token': '0xf4003F4efBE8691B60249E6afbD307aBE7758adb',
        'lp_whale': JOE_FARM,
        'lp_farm': '0x7854B77c252dA067AcB59C4A25DCd407764Bd8eE',
        'pid': 0,
        'router': JOE_ROUTER,
    },
    'WETHAVAXVTX': {
        'token': WETH,
        'whale': WETH_WHALE,
        'shortWhale' : '0xf4003F4efBE8691B60249E6afbD307aBE7758adb',
        'deposit': 1e6,
        'harvest_token': JOE,
        'harvest_token_price': JOE_PRICE / 1000,
        'harvest_token_whale': '0x1a731B2299E22FbAC282E7094EdA41046343Cb51',
        'lp_token': '0xFE15c2695F1F920da45C30AAE47d11dE51007AF9',
        'lp_whale': JOE_FARM,
        'lp_farm': '',
        'pid': 0,
        'router': JOE_ROUTER,
    },
    'BTCbAVAXBQIVTX': {
        'token': BTCB,
        'whale': BTCB_WHALE,
        'shortWhale' : '0xf4003F4efBE8691B60249E6afbD307aBE7758adb',
        'deposit': 1e6,
        'harvest_token': JOE,
        'harvest_token_price': JOE_PRICE / 1e10,
        'harvest_token_whale': '0x1a731B2299E22FbAC282E7094EdA41046343Cb51',
        'lp_token': '0x2fd81391e30805cc7f2ec827013ce86dc591b806',
        'lp_whale': JOE_FARM,
        'lp_farm': '0x1e893e5711F50a9D7C132f6E4752c7335bDFDBF8',
        'pid': 0,
        'router': JOE_ROUTER,
    },
    'USDTAVAXBQIVTX': {
        'token': USDT,
        'whale': USDT_WHALE,
        'shortWhale' : '0xf4003F4efBE8691B60249E6afbD307aBE7758adb',
        'deposit': 1e6,
        'harvest_token': JOE,
        'harvest_token_price': JOE_PRICE / 1e12,
        'harvest_token_whale': '0x1a731B2299E22FbAC282E7094EdA41046343Cb51',
        'lp_token': '0xbb4646a764358ee93c2a9c4a147d5aDEd527ab73',
        'lp_whale': JOE_FARM,
        'lp_farm': '0xfC1300fe68BC0b419b1eacE7f971B63F3186D489',
        'pid': 0,
        'router': JOE_ROUTER,
    }
}




@pytest.fixture
def strategy_contract():
    yield  project.CoreStrategyProject.USDTAVAXBQIVTX


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


# Function scoped isolation fixture to enable xdist.
# Snapshots the chain before each test and reverts after test completion.
@pytest.fixture(scope="function", autouse=True)
def shared_setup(fn_isolation):
    pass


