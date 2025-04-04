# eSIM Bot

A Telegram bot for purchasing eSIM top-ups using cryptocurrency payments.

## Installation

This project has a complex dependency structure due to incompatibilities between packages. To install correctly, use the provided installation script:

```bash
chmod +x install_deps.sh
./install_deps.sh
```

### Manual Installation

If you need to install manually, follow these steps:

1. First install base dependencies:
   ```bash
   pip install python-dotenv==1.0.1 requests==2.31.0 aiohttp==3.9.3 certifi==2024.2.2 solders==0.19.0 base58==2.1.1
   ```

2. Install httpx at a version compatible with solana:
   ```bash
   pip install httpx==0.23.3
   ```

3. Install solana from source:
   ```bash
   mkdir -p /tmp/solana-py
   curl -L https://github.com/michaelhly/solana-py/archive/refs/tags/v0.31.0.tar.gz | tar -xz -C /tmp/solana-py --strip-components=1
   cd /tmp/solana-py
   sed -i 's/httpx>=0.23.0,<0.24.0/httpx==0.23.3/g' pyproject.toml
   pip install -e .
   cd -
   ```

4. Upgrade httpx for python-telegram-bot:
   ```bash
   pip install --upgrade httpx~=0.26.0
   ```

5. Install python-telegram-bot:
   ```bash
   pip install python-telegram-bot==20.8
   ```

## Environment Variables

Create a `.env` file with the following variables:

```
# Telegram Bot Token
TELEGRAM_BOT_TOKEN=your_token_here

# Airalo API Credentials
AIRALO_CLIENT_ID=your_client_id
AIRALO_CLIENT_SECRET=your_client_secret

# Solana configuration
SOLANA_NETWORK=mainnet-beta
SPL_TOKEN_MINT=your_token_mint_address
SPL_TOKEN_SYMBOL=ESIM
SPL_TOKEN_DECIMALS=9
SOLANA_MAIN_WALLET=your_wallet_address
SOLANA_MAIN_WALLET_PRIVATE_KEY=your_private_key
SOLANA_MAIN_WALLET_TOKEN_ACCOUNT=your_token_account

# Testing mode settings
TESTING_MODE=true
TESTING_PAYMENT_MULTIPLIER=0.01
MOCK_PAYMENT_SUCCESS=false
```

## Running the Bot

Start the bot with:

```bash
python bot.py
```