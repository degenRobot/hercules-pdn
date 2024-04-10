import pytest
from brownie import config
from brownie import Contract
from brownie import interface, StrategyInsurance, TorchManager, GrailManagerProxy, USDCWETHTORCH ,accounts
from tests.helper import encode_function_data

TORCH = '0xbB1676046C36BCd2F6fD08d8f60672c7087d9aDF'
TORCH_PRICE = 3000

ORACLE = '0x38D36e85E47eA6ff0d18B0adF12E5fC8984A6f8e'

POOL_ADDRESS_PROVIDER = '0xB9FABd7500B2C6781c35Dd48d54f81fc2299D7AF'
# Tokens
USDC = '0xEA32A96608495e54156Ae48931A7c20f0dcc1a21'
USDC_WHALE = '0x555982d2E211745b96736665e19D9308B615F78e'
WETH_WHALE = '0x555982d2E211745b96736665e19D9308B615F78e'
WMETIS = '0x75cb093E4D61d2A2e65D8e0BBb01DE8d89b53481'
WETH = ''
SUSHI = '0xd4d42F0b6DEF4CE0383636770eF773390d85c61A'

TORCH_ROUTER = '0x14679D1Da243B8c7d1A4c6d0523A2Ce614Ef027C'

SUSHISWAP_ROUTER = '0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506'
CONFIG = {
    'USDCWETHTORCH': {
        'token': USDC,
        'whale': USDC_WHALE,
        'shortWhale' : WETH_WHALE,
        'deposit': 1e6,
        'harvest_token': TORCH,
        'harvest_token_price': TORCH_PRICE * 1e-12, #note adjust by 1e-12 due to dif in decimals between USDC & GRAIL token i.e. 6 vs 18 
        'harvest_token_whale': '0x5A5A7C0108CEf44549b7782495b1Df2Ad5294Da3',
        'lp_token': '0x4C10a0E5fc4a6eDe720dEcdAD99B281076EAC0fA',
        'lp_whale': '0x3E5F2622F66f916Ba79cb12B40CB29727bb2130E',
        'lp_farm': '0xE67348414A5Ab2c065FA2b422144A6c5C925cEfF',
        'pid': 0,
        'router': TORCH_ROUTER,
    },

}

@pytest.fixture
def grail_manager_contract():
    yield  TorchManager

@pytest.fixture
def grail_manager_proxy_contract():
    yield GrailManagerProxy

@pytest.fixture
def strategy_contract():
    yield  USDCWETHTORCH


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
    yield interface.ICamelotRouter(conf['router'])


@pytest.fixture
def camelotRouter(conf):
    yield interface.ICamelotRouter(conf['router'])

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
def vault_mock_oracle(pm, gov, rewards, guardian, management, token):
    Vault = pm(config["dependencies"][0]).Vault
    vault = guardian.deploy(Vault)
    vault.initialize(token, gov, rewards, "", "", guardian, management)
    vault.setDepositLimit(2 ** 256 - 1, {"from": gov})
    assert vault.token() == token.address
    yield vault

@pytest.fixture
def strategy_before_set(strategist, keeper, vault, strategy_contract, gov, conf):
    # strategy = strategy_contract.deploy(vault, {'from': strategist,'gas_limit': 20000000})
    strategy = strategist.deploy(strategy_contract, vault)
    insurance = strategist.deploy(StrategyInsurance, strategy)
    strategy.setKeeper(keeper)
    strategy.setInsurance(insurance, {'from': gov})
    vault.addStrategy(strategy, 10_000, 0, 2 ** 256 - 1, 1_000, {"from": gov})
    yield strategy

@pytest.fixture
def grailManager(grail_manager_proxy_contract, strategy_before_set, grail_manager_contract, gov, conf) : 
    yieldBooster = '0xA4dEfAf0904529A1ffE04CC8A1eF3BC7d7F7b121'
    xGrail = '0xF192897fC39bF766F1011a858dE964457bcA5832'
    
    #grailManager = gov.deploy(grail_manager_contract)

    # grailManager.initialize(gov, strategy, grailConfig, {'from': gov})
    #grailConfig = [strategy_before_set.want(), conf['lp_token'], conf['harvest_token'], xGrail, conf['lp_farm'], conf['router'], yieldBooster]
    grailManager = grail_manager_contract.deploy(gov, strategy_before_set, strategy_before_set.want(), conf['lp_token'], conf['harvest_token'], xGrail, conf['lp_farm'], conf['router'], yieldBooster, {'from': gov})
    #encoded_initializer_function = encode_function_data(grailManager.initialize, gov, strategy_before_set, grailConfig)
    #grailManagerProxy = gov.deploy(grail_manager_proxy_contract, grailManager.address, encoded_initializer_function)
    yield grailManager

@pytest.fixture
def strategy(strategy_before_set, grailManager, gov):
    strategy_before_set.setGrailManager(grailManager, {'from': gov})
    yield strategy_before_set

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
def strategy_mock_initialized_vault(chain, accounts, gov, token, vault_mock_oracle, strategy_mock_oracle, user, strategist, amount, RELATIVE_APPROX):
    # Deposit to the vault
    token.approve(vault_mock_oracle.address, amount, {"from": user})
    print("Amount: ", amount)
    print("User: ", user)
    vault_mock_oracle.deposit(amount, {"from": user})
    assert token.balanceOf(vault_mock_oracle.address) == amount
    
    # harvest
    chain.sleep(1)
    
    print("Vault: ",token.balanceOf(vault_mock_oracle.address))
    print("Strategy: ",token.balanceOf(strategy_mock_oracle.address))
    strategy_mock_oracle.harvest()
    strat = strategy_mock_oracle
    assert pytest.approx(strategy_mock_oracle.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount
    yield vault_mock_oracle 

@pytest.fixture
def strategy_mock_oracle_before_set(token, amount, user, strategist, keeper, vault_mock_oracle, strategy_contract, gov ,MockAaveOracle, conf):
    pool_address_provider = interface.IPoolAddressesProvider(POOL_ADDRESS_PROVIDER)
    old_oracle = pool_address_provider.getPriceOracle()
    # Set the mock price oracle
    oracle = MockAaveOracle.deploy(old_oracle, {'from': accounts[0]})

    admin = accounts.at(pool_address_provider.owner(), True)
    pool_address_provider.setPriceOracle(oracle, {'from': admin})

    strategy_mock_oracle = strategist.deploy(strategy_contract, vault_mock_oracle)
    insurance = strategist.deploy(StrategyInsurance, strategy_mock_oracle)
    strategy_mock_oracle.setKeeper(keeper)
    strategy_mock_oracle.setInsurance(insurance, {'from': gov})

    vault_mock_oracle.addStrategy(strategy_mock_oracle, 10_000, 0, 2 ** 256 - 1, 1_000, {"from": gov})
    yield strategy_mock_oracle

@pytest.fixture
def grailManager_mock_oracle(grail_manager_proxy_contract, grail_manager_contract, gov, strategy_mock_oracle_before_set, conf) : 
    yieldBooster = '0xD27c373950E7466C53e5Cd6eE3F70b240dC0B1B1'
    xGrail = '0x3CAaE25Ee616f2C8E13C74dA0813402eae3F496b'
    
    grailManager = gov.deploy(grail_manager_contract)

    # grailManager.initialize(gov, strategy, grailConfig, {'from': gov})
    grailConfig = [strategy_mock_oracle_before_set.want(), conf['lp_token'], conf['harvest_token'], xGrail, conf['lp_farm'], conf['router'], yieldBooster]

    encoded_initializer_function = encode_function_data(grailManager.initialize, gov, strategy_mock_oracle_before_set, grailConfig)
    
    grailManagerProxy = gov.deploy(grail_manager_proxy_contract, grailManager.address, encoded_initializer_function)

    yield grailManagerProxy

@pytest.fixture
def strategy_mock_oracle(strategy_mock_oracle_before_set, grailManager_mock_oracle, gov):
    strategy_mock_oracle_before_set.setGrailManager(grailManager_mock_oracle, {'from': gov})
    yield strategy_mock_oracle_before_set


# Function scoped isolation fixture to enable xdist.
# Snapshots the chain before each test and reverts after test completion.
#@pytest.fixture(scope="function", autouse=True)
#def shared_setup(strategy, strategy_mock_oracle, grailManager, grailManager_mock_oracle):
#    pass
@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass
