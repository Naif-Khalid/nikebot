# 👟 Nike SNKRS Bot

An automated Nike sneaker checkout bot built with Python and Selenium. Designed to log into Nike, wait for a scheduled shoe drop, select your size, and race through checkout — all as fast as possible.

> ⚠️ **Disclaimer:** This project is for **educational purposes only**. Using bots violates Nike's Terms of Service and may result in account bans. Use at your own risk.

---

## Features

- **Stealth Browser** — Uses `undetected-chromedriver` to bypass Nike's bot detection (Akamai, fingerprinting, etc.)
- **Human-Like Behavior** — Randomized typing speed, mouse movements, scroll patterns, and click offsets
- **Nike OAuth Login** — Logs in through `accounts.nike.com` with full multi-step flow support
- **2FA Support** — Detects Nike's 8-digit email verification code screen and pauses for manual entry (5 min timeout)
- **Scheduled Drops** — Set a drop time and the bot sleeps until the exact moment, then fires instantly
- **Auto Size Selection** — Matches your size using multiple strategies (aria-labels, text matching, data attributes)
- **Full Checkout Flow** — Fills shipping address, payment info, and submits the order automatically
- **Smart Retries** — Every step retries up to 5 times with automatic screenshots on failure
- **Chrome Version Detection** — Auto-detects your installed Chrome version to avoid driver mismatch errors
- **JSON Config** — All settings in one `config.json` file, no code editing needed

## How It Works

```
1. Login        → accounts.nike.com (email → "Use Password" → password → 2FA)
2. Wait         → Sleeps until configured drop time with session keep-alive
3. Navigate     → Loads shoe page, refreshes until sizes appear
4. Select Size  → Finds and clicks your size button
5. Add to Cart  → Clicks Add to Cart / Buy
6. Checkout     → Navigates to checkout page
7. Shipping     → Auto-fills address (skips if saved on account)
8. Payment      → Fills card details including iframe-embedded fields
9. Submit       → Clicks Place Order
```

## Requirements

- Python 3.10+
- Google Chrome installed
- A Nike account

## Installation

```bash
# Clone the repo
git clone https://github.com/Naif-Khalid/nikebot.git
cd nikebot

# Create virtual environment
python -m venv venv

# Activate it
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Configuration

Edit `config.json` with your details:

```json
{
  "user": {
    "email": "your_email@example.com",
    "password": "your_nike_password",
    "first_name": "John",
    "last_name": "Doe",
    "address_line1": "123 Sneaker St",
    "address_line2": "",
    "city": "Portland",
    "state": "OR",
    "zip_code": "97201",
    "phone": "5031234567",
    "card_number": "4111111111111111",
    "card_exp_month": "12",
    "card_exp_year": "2027",
    "card_cvv": "123"
  },
  "bot": {
    "shoe_url": "https://www.nike.com/launch/t/your-shoe-here",
    "shoe_size": "10",
    "drop_time": "2026-02-05T10:00:00",
    "refresh_interval": 3.0,
    "page_load_timeout": 20,
    "element_timeout": 12,
    "headless": false,
    "retry_limit": 5,
    "log_level": "INFO",
    "type_speed_min": 0.05,
    "type_speed_max": 0.15,
    "chrome_version": 0
  }
}
```

### Config Options

| Field | Description |
|---|---|
| `shoe_url` | Full Nike product/launch URL |
| `shoe_size` | Your size (e.g. `"10"`, `"10.5"`, `"11C"` for kids) |
| `drop_time` | ISO format drop time (e.g. `"2026-02-05T10:00:00"`), or `null` to skip waiting |
| `chrome_version` | Your Chrome major version (e.g. `144`). Set `0` for auto-detect |
| `headless` | Run browser invisibly (`true`/`false`) |
| `retry_limit` | Max retries per step before failing |
| `type_speed_min/max` | Keystroke delay range in seconds (simulates human typing) |

## Usage

```bash
python nike_snkrs_bot.py
```

Or specify a custom config path:

```bash
python nike_snkrs_bot.py my_config.json
```

### What to Expect

1. Chrome opens and navigates to Nike's login page
2. Bot enters your email and password with human-like typing
3. If Nike asks for a **2FA code**, you'll see a prompt in the terminal — enter the code manually in the browser
4. Bot navigates to the shoe page and handles checkout
5. Screenshots are saved to `screenshots/` on any failures

## Troubleshooting

**`ModuleNotFoundError: No module named 'distutils'`**
> Python 3.12+ removed distutils. Fix: `pip install setuptools`

**`SessionNotCreatedException: This version of ChromeDriver only supports Chrome version X`**
> Set `"chrome_version"` in config.json to match your Chrome. Check your version at `chrome://version`

**Nike redirects to regional site (e.g. nike.sa)**
> The bot goes directly to `accounts.nike.com` to avoid regional redirects. If issues persist, check that `shoe_url` uses `nike.com`

**`Password field not found`**
> Nike defaults to an 8-digit code login. The bot clicks "Use Password" automatically. If this fails, Nike may have changed their UI — open an issue.

## Project Structure

```
nikebot/
├── nike_snkrs_bot.py   # Main bot script
├── config.json          # Your configuration (DO NOT commit with real credentials)
├── requirements.txt     # Python dependencies
├── screenshots/         # Auto-captured screenshots on failures
├── .gitignore
└── README.md
```

## ⚠️ Security Note

**Never commit `config.json` with real credentials.** Add it to `.gitignore`:

```
config.json
venv/
screenshots/
```

## License

This project is for educational purposes only. No warranty is provided. Use responsibly.