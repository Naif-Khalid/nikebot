#!/usr/bin/env python3
"""
Nike SNKRS Bot — Educational Web Automation Example (v2 — Stealth)
===================================================================
Fixes "Error parsing response from server" by using:
  • undetected-chromedriver (patches browser fingerprint)
  • Human-like typing with random delays
  • Nike API login as primary method (browser login as fallback)
  • Randomized mouse movements and scroll behavior
  • Proper cookie/session handling

⚠️  DISCLAIMER:
    - Using bots violates Nike's Terms of Service.
    - This script is for EDUCATIONAL PURPOSES ONLY.
    - The author is not responsible for any misuse or account bans.

Requirements:
    pip install undetected-chromedriver selenium requests
"""

import os
import sys
import time
import json
import random
import string
import logging
import imaplib
import email as email_lib
from email.header import decode_header
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional
import re

import requests
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    ElementClickInterceptedException,
    StaleElementReferenceException,
)


# ──────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────

@dataclass
class UserProfile:
    """All the info needed to log in and check out."""
    email: str = ""
    password: str = ""
    # IMAP settings for fetching Nike's 8-digit verification code
    # For Hotmail/Outlook: use an App Password from https://account.microsoft.com/security
    email_imap_server: str = "outlook.office365.com"
    email_imap_password: str = ""   # App password (NOT your regular password)
    first_name: str = ""
    last_name: str = ""
    address_line1: str = ""
    address_line2: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""
    phone: str = ""
    card_number: str = ""
    card_exp_month: str = ""
    card_exp_year: str = ""
    card_cvv: str = ""


@dataclass
class BotConfig:
    """Runtime configuration for the bot."""
    shoe_url: str = ""
    shoe_size: str = ""
    drop_time: Optional[str] = None
    refresh_interval: float = 3.0
    page_load_timeout: int = 20
    element_timeout: int = 12
    headless: bool = False
    retry_limit: int = 5
    log_level: str = "INFO"
    # Typing speed range (seconds between each keystroke)
    type_speed_min: float = 0.05
    type_speed_max: float = 0.15
    # Set to your Chrome major version (e.g. 144). 0 = auto-detect.
    chrome_version: int = 0


# ──────────────────────────────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────────────────────────────

def setup_logging(level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger("NikeBot")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("[%(asctime)s] %(levelname)-8s %(message)s", "%H:%M:%S")
    )
    if not logger.handlers:
        logger.addHandler(handler)
    return logger


# ──────────────────────────────────────────────────────────────────────
# Human-Like Behavior Helpers
# ──────────────────────────────────────────────────────────────────────

class HumanBehavior:
    """Simulate human-like interactions to avoid bot detection."""

    def __init__(self, driver, config: BotConfig):
        self.driver = driver
        self.config = config
        self.actions = ActionChains(driver)

    def random_sleep(self, min_s: float = 0.5, max_s: float = 2.0):
        """Sleep for a random duration."""
        time.sleep(random.uniform(min_s, max_s))

    def human_type(self, element, text: str):
        """
        Type text character by character with random delays,
        simulating real human typing patterns.
        """
        element.click()
        self.random_sleep(0.2, 0.5)

        for char in text:
            element.send_keys(char)
            # Variable delay — occasionally pause longer (like thinking)
            if random.random() < 0.1:
                time.sleep(random.uniform(0.2, 0.5))
            else:
                time.sleep(random.uniform(
                    self.config.type_speed_min,
                    self.config.type_speed_max
                ))

    def human_clear_and_type(self, element, text: str):
        """Clear a field with keyboard shortcuts then type humanly."""
        element.click()
        self.random_sleep(0.1, 0.3)
        # Select all and delete (more human than .clear())
        element.send_keys(Keys.CONTROL + "a")
        time.sleep(random.uniform(0.05, 0.15))
        element.send_keys(Keys.BACKSPACE)
        self.random_sleep(0.1, 0.3)
        self.human_type(element, text)

    def random_mouse_move(self):
        """Move the mouse to a random spot on the page."""
        try:
            body = self.driver.find_element(By.TAG_NAME, "body")
            x_offset = random.randint(100, 800)
            y_offset = random.randint(100, 500)
            self.actions.move_to_element_with_offset(body, x_offset, y_offset).perform()
            self.random_sleep(0.1, 0.3)
        except Exception:
            pass

    def random_scroll(self):
        """Scroll the page a little bit randomly."""
        scroll_amount = random.randint(100, 400)
        direction = random.choice([1, -1])
        self.driver.execute_script(f"window.scrollBy(0, {scroll_amount * direction});")
        self.random_sleep(0.3, 0.8)

    def human_click(self, element):
        """Move to element with slight offset, pause, then click."""
        try:
            x_off = random.randint(-3, 3)
            y_off = random.randint(-3, 3)
            ActionChains(self.driver) \
                .move_to_element_with_offset(element, x_off, y_off) \
                .pause(random.uniform(0.1, 0.3)) \
                .click() \
                .perform()
        except Exception:
            # Fallback to JS click
            self.driver.execute_script("arguments[0].click();", element)


# ──────────────────────────────────────────────────────────────────────
# Browser Setup — Undetected ChromeDriver
# ──────────────────────────────────────────────────────────────────────

def create_driver(config: BotConfig) -> uc.Chrome:
    """
    Create an UNDETECTED Chrome instance.
    This patches the ChromeDriver binary to avoid detection by
    services like Akamai, PerimeterX, DataDome, etc.
    """
    opts = uc.ChromeOptions()

    if config.headless:
        opts.add_argument("--headless=new")

    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1440,900")
    opts.add_argument("--disable-popup-blocking")
    opts.add_argument("--lang=en-US,en;q=0.9")

    # Detect Chrome version if not specified
    version = config.chrome_version
    if version == 0:
        version = _detect_chrome_version()

    kwargs = {"options": opts, "use_subprocess": True}
    if version:
        kwargs["version_main"] = version
        logging.getLogger("NikeBot").info(
            f"🌐  Using Chrome version {version}"
        )

    driver = uc.Chrome(**kwargs)
    driver.set_page_load_timeout(config.page_load_timeout)

    return driver


def _detect_chrome_version() -> int:
    """Try to auto-detect the installed Chrome major version."""
    import subprocess
    import re

    # Windows registry check
    try:
        result = subprocess.run(
            [
                "reg", "query",
                r"HKEY_CURRENT_USER\Software\Google\Chrome\BLBeacon",
                "/v", "version",
            ],
            capture_output=True, text=True, timeout=5,
        )
        match = re.search(r"(\d+)\.\d+\.\d+\.\d+", result.stdout)
        if match:
            return int(match.group(1))
    except Exception:
        pass

    # Fallback: try running chrome --version
    for path in [
        "chrome", "google-chrome",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]:
        try:
            result = subprocess.run(
                [path, "--version"],
                capture_output=True, text=True, timeout=5,
            )
            match = re.search(r"(\d+)\.\d+\.\d+", result.stdout)
            if match:
                return int(match.group(1))
        except Exception:
            continue

    return 0


# ──────────────────────────────────────────────────────────────────────
# Element Helper
# ──────────────────────────────────────────────────────────────────────

class ElementHelper:
    """Convenience wrappers around Selenium waits and actions."""

    def __init__(self, driver, timeout: int = 10):
        self.driver = driver
        self.timeout = timeout

    def wait_and_find(self, by: By, value: str, timeout: int = None):
        t = timeout or self.timeout
        return WebDriverWait(self.driver, t).until(
            EC.presence_of_element_located((by, value))
        )

    def wait_and_click(self, by: By, value: str, timeout: int = None):
        t = timeout or self.timeout
        el = WebDriverWait(self.driver, t).until(
            EC.element_to_be_clickable((by, value))
        )
        try:
            el.click()
        except ElementClickInterceptedException:
            self.driver.execute_script("arguments[0].click();", el)
        return el

    def element_exists(self, by: By, value: str) -> bool:
        try:
            self.driver.find_element(by, value)
            return True
        except NoSuchElementException:
            return False

    def switch_to_iframe(self, by: By, value: str, timeout: int = None):
        t = timeout or self.timeout
        iframe = WebDriverWait(self.driver, t).until(
            EC.presence_of_element_located((by, value))
        )
        self.driver.switch_to.frame(iframe)

    def switch_to_default(self):
        self.driver.switch_to.default_content()


# ──────────────────────────────────────────────────────────────────────
# Nike API Login
# ──────────────────────────────────────────────────────────────────────

class NikeAPILogin:
    """
    Log in via Nike's authentication API and inject the session
    cookies into the browser. This bypasses the browser-based login
    form entirely, avoiding the "Error parsing response" issue.
    """

    AUTH_URL = "https://unite.nike.com/loginWithSetCookie"
    CLIENT_ID = "HlHa2Cje3ctlaOqnxvgZXNaAs7T9nAuH"  # Nike's public client ID

    def __init__(self, driver, profile: UserProfile, log: logging.Logger):
        self.driver = driver
        self.profile = profile
        self.log = log

    def login(self) -> bool:
        """
        Attempt API-based login. Returns True on success.
        """
        self.log.info("🔑  Attempting Nike API login…")

        try:
            # Visit the regional Nike site to establish cookies
            # (skip this if it causes redirect issues — go straight to API)
            try:
                self.driver.get("https://www.nike.com/")
                time.sleep(random.uniform(2, 4))
            except Exception:
                pass

            # Build the API login payload
            payload = {
                "client_id": self.CLIENT_ID,
                "grant_type": "password",
                "keepMeLoggedIn": True,
                "password": self.profile.password,
                "username": self.profile.email,
                "ux_id": "com.nike.commerce.nikedotcom.web",
            }

            headers = {
                "User-Agent": self.driver.execute_script("return navigator.userAgent;"),
                "Content-Type": "application/json",
                "Origin": "https://www.nike.com",
                "Referer": "https://www.nike.com/",
            }

            # Grab existing cookies from the browser session
            browser_cookies = self.driver.get_cookies()
            cookie_str = "; ".join(
                f"{c['name']}={c['value']}" for c in browser_cookies
            )
            if cookie_str:
                headers["Cookie"] = cookie_str

            response = requests.post(
                self.AUTH_URL,
                json=payload,
                headers=headers,
                timeout=15,
            )

            if response.status_code == 200:
                data = response.json()
                self.log.info("✅  API login successful! Injecting session…")
                self._inject_session(data, response.cookies)
                return True
            else:
                self.log.warning(
                    f"⚠️  API login returned {response.status_code}: "
                    f"{response.text[:200]}"
                )
                return False

        except Exception as exc:
            self.log.warning(f"⚠️  API login failed: {exc}")
            return False

    def _inject_session(self, auth_data: dict, resp_cookies):
        """Inject authentication cookies and tokens into the browser."""
        # Make sure we're on a nike domain before adding cookies
        current_url = self.driver.current_url
        if "nike" not in current_url:
            try:
                self.driver.get("https://www.nike.com/")
                time.sleep(2)
            except Exception:
                pass

        # Add cookies from the API response
        for cookie in resp_cookies:
            try:
                cookie_dict = {
                    "name": cookie.name,
                    "value": cookie.value,
                    "domain": cookie.domain or ".nike.com",
                    "path": cookie.path or "/",
                }
                self.driver.add_cookie(cookie_dict)
            except Exception:
                pass

        # Set the access token as a cookie
        access_token = auth_data.get("access_token", "")
        if access_token:
            try:
                self.driver.add_cookie({
                    "name": "access_token",
                    "value": access_token,
                    "domain": ".nike.com",
                    "path": "/",
                })
            except Exception:
                pass

        # Set tokens in localStorage for Nike's SPA
        try:
            token_json = json.dumps(auth_data)
            self.driver.execute_script(
                f"window.localStorage.setItem('com.nike.commerce.nikedotcom.web.credential', "
                f"'{token_json}');"
            )
        except Exception:
            pass

        # Refresh to apply the session
        self.driver.refresh()
        time.sleep(random.uniform(2, 3))


# ──────────────────────────────────────────────────────────────────────
# Bot Core
# ──────────────────────────────────────────────────────────────────────

class NikeSNKRSBot:
    """
    Main bot class — full flow:
        1. Login (API first, browser fallback)
        2. Wait for drop time
        3. Navigate to shoe page
        4. Select size -> Add to cart
        5. Checkout (address -> shipping -> payment -> submit)
    """

    NIKE_LOGIN_URL = (
        "https://accounts.nike.com/lookup"
        "?client_id=4fd2d5e7db76e0f85a6bb56721bd51df"
        "&redirect_uri=https://www.nike.com/auth/login"
        "&response_type=code"
        "&scope=openid%20nike.digital%20profile%20email%20phone%20flow%20country"
        "&ui_locales=en-US"
        "&code_challenge_method=S256"
    )
    NIKE_BASE_URL = "https://www.nike.com"

    # Pages that count as "still logging in"
    LOGIN_PAGE_INDICATORS = [
        "accounts.nike.com",
        "/login",
        "/signin",
        "/lookup",
        "/auth/login",
    ]

    def __init__(self, profile: UserProfile, config: BotConfig):
        self.profile = profile
        self.config = config
        self.log = setup_logging(config.log_level)
        self.driver: Optional[uc.Chrome] = None
        self.helper: Optional[ElementHelper] = None
        self.human: Optional[HumanBehavior] = None

    # ── Lifecycle ─────────────────────────────────────────────────────

    def start(self):
        """Full bot lifecycle."""
        self.log.info("🚀  Nike SNKRS Bot (v2 Stealth) starting…")
        self._validate_config()
        self.driver = create_driver(self.config)
        self.helper = ElementHelper(self.driver, self.config.element_timeout)
        self.human = HumanBehavior(self.driver, self.config)

        try:
            self.login()
            self.wait_for_drop()
            self.navigate_to_shoe()
            self.select_size()
            self.add_to_cart()
            self.begin_checkout()
            self.fill_shipping()
            self.fill_payment()
            self.submit_order()
            self.log.info("🎉  Order submitted! Check your Nike account.")
        except KeyboardInterrupt:
            self.log.warning("Bot stopped by user (Ctrl+C).")
        except Exception as exc:
            self.log.error(f"❌  Fatal error: {exc}", exc_info=True)
        finally:
            self._screenshot("final_state")
            input("\nPress Enter to close the browser…")
            self.driver.quit()

    def _validate_config(self):
        if not self.profile.email or not self.profile.password:
            raise ValueError("Email and password are required.")
        if not self.config.shoe_url:
            raise ValueError("Shoe URL is required.")
        if not self.config.shoe_size:
            raise ValueError("Shoe size is required.")

    def _screenshot(self, name: str):
        try:
            path = f"screenshots/{name}_{int(time.time())}.png"
            os.makedirs("screenshots", exist_ok=True)
            self.driver.save_screenshot(path)
            self.log.info(f"📸  Screenshot -> {path}")
        except Exception:
            pass

    def _retry(self, func, step_name: str):
        for attempt in range(1, self.config.retry_limit + 1):
            try:
                return func()
            except Exception as exc:
                self.log.warning(
                    f"⚠️  {step_name} attempt {attempt}/{self.config.retry_limit} "
                    f"failed: {exc}"
                )
                self._screenshot(f"{step_name}_fail_{attempt}")
                if attempt == self.config.retry_limit:
                    raise
                time.sleep(random.uniform(1, 3))

    # ── 1. Login ──────────────────────────────────────────────────────

    def login(self):
        """
        Login strategy: Go directly to accounts.nike.com
        (Skip API login — it visits nike.com which redirects to nike.sa)
        """
        self.log.info("🔑  Logging in via accounts.nike.com…")
        self._retry(self._browser_login, "browser_login")

    def _browser_login(self):
        """
        Browser-based login with human-like behavior.
        
        Nike's current login flow (multi-step):
          Step 1: Go directly to accounts.nike.com (not nike.com which redirects regionally)
          Step 2: Enter email → click "Continue"
          Step 3: Nike defaults to "Enter 8-digit code" screen
                  → click "Use Password" to switch to password mode
          Step 4: Enter password → click "Sign In"
          Step 5: Handle 2FA if required
        """
        # Go DIRECTLY to accounts.nike.com — do NOT visit nike.com first
        # (nike.com redirects to nike.sa / nike.co.uk / etc. based on location)
        self.log.info(f"   🌐  Navigating to accounts.nike.com…")
        self.driver.get(self.NIKE_LOGIN_URL)
        self.human.random_sleep(3, 5)

        # Verify we're on accounts.nike.com and not redirected
        current = self.driver.current_url
        self.log.info(f"   📍  Current URL: {current}")

        # If we got redirected to a regional site, force back to accounts.nike.com
        if "accounts.nike.com" not in current:
            self.log.warning(f"   ⚠️  Redirected to {current} — forcing accounts.nike.com…")
            self.driver.get(self.NIKE_LOGIN_URL)
            self.human.random_sleep(3, 5)

        # Random mouse movement before interacting (looks human)
        self.human.random_mouse_move()
        self.human.random_sleep(0.5, 1.5)

        # ══════════════════════════════════════════════════════════════
        # STEP 1: Enter email
        # ══════════════════════════════════════════════════════════════
        self.log.info("   📧  Step 1: Entering email…")
        email_selectors = [
            'input[type="email"]',
            'input[name="emailAddress"]',
            'input[id="username"]',
            'input[autocomplete="email"]',
        ]
        email_field = self._find_first_element(email_selectors)
        if not email_field:
            raise NoSuchElementException("Email field not found.")

        self.human.random_mouse_move()
        self.human.random_sleep(0.3, 0.8)
        self.human.human_clear_and_type(email_field, self.profile.email)
        self.human.random_sleep(0.5, 1.0)

        # Click "Continue" / "Sign In" / submit button after email
        continue_btn = self._find_first_element([
            'button[type="submit"]',
            'input[type="submit"]',
            'button[data-qa="login-submit"]',
        ])
        if continue_btn:
            self.human.human_click(continue_btn)
            self.log.info("   ➡️  Clicked continue after email.")
            self.human.random_sleep(2, 4)
        else:
            # Some flows use Enter key to proceed
            email_field.send_keys(Keys.RETURN)
            self.human.random_sleep(2, 4)

        # ══════════════════════════════════════════════════════════════
        # STEP 2: Handle the verification method screen
        #
        # Nike shows "Enter the 8-digit code" by default.
        # We need to click "Use Password" to switch to password mode.
        # If the password field is already visible, skip this step.
        # ══════════════════════════════════════════════════════════════
        self.log.info("   🔄  Step 2: Checking for verification method…")

        # First check if password field is already visible (some accounts skip the code screen)
        password_field = self._find_first_element([
            'input[type="password"]',
            'input[name="password"]',
        ])

        if not password_field:
            # Password not visible — look for "Use Password" button
            self.log.info("   🔑  Code screen detected — clicking 'Use Password'…")

            use_password_selectors = [
                # Button text matching
                '//button[contains(text(), "Use Password")]',
                '//button[contains(text(), "Use password")]',
                '//button[contains(text(), "use password")]',
                '//a[contains(text(), "Use Password")]',
                '//a[contains(text(), "Use password")]',
                '//span[contains(text(), "Use Password")]/parent::button',
                '//span[contains(text(), "Use password")]/parent::button',
            ]

            clicked_use_password = False

            # Try XPath selectors (best for text matching)
            for xpath in use_password_selectors:
                try:
                    el = WebDriverWait(self.driver, 3).until(
                        EC.element_to_be_clickable((By.XPATH, xpath))
                    )
                    self.human.random_mouse_move()
                    self.human.random_sleep(0.3, 0.8)
                    self.human.human_click(el)
                    clicked_use_password = True
                    self.log.info("   ✅  Clicked 'Use Password'!")
                    self.human.random_sleep(2, 3)
                    break
                except (TimeoutException, NoSuchElementException):
                    continue

            # Fallback: search all buttons/links by visible text
            if not clicked_use_password:
                self.log.info("   🔍  Searching all buttons for 'Use Password'…")
                all_buttons = self.driver.find_elements(
                    By.CSS_SELECTOR, "button, a, [role='button']"
                )
                for btn in all_buttons:
                    btn_text = btn.text.strip().lower()
                    if "use password" in btn_text:
                        self.human.human_click(btn)
                        clicked_use_password = True
                        self.log.info("   ✅  Clicked 'Use Password' (text scan)!")
                        self.human.random_sleep(2, 3)
                        break

            if not clicked_use_password:
                self._screenshot("no_use_password_btn")
                raise NoSuchElementException(
                    "'Use Password' button not found. "
                    "Nike may be forcing email code verification."
                )

        # ══════════════════════════════════════════════════════════════
        # STEP 3: Enter password and sign in
        # ══════════════════════════════════════════════════════════════
        self.log.info("   🔒  Step 3: Entering password…")

        # Wait for the password field to appear after clicking "Use Password"
        password_selectors = [
            'input[type="password"]',
            'input[name="password"]',
            'input[id="password"]',
            'input[autocomplete="current-password"]',
        ]

        password_field = None
        for sel in password_selectors:
            try:
                password_field = WebDriverWait(self.driver, 8).until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, sel))
                )
                break
            except TimeoutException:
                continue

        if not password_field:
            self._screenshot("no_password_field")
            raise NoSuchElementException(
                "Password field not found after clicking 'Use Password'."
            )

        self.human.random_mouse_move()
        self.human.random_sleep(0.3, 0.8)
        self.human.human_clear_and_type(password_field, self.profile.password)
        self.human.random_sleep(0.5, 1.5)

        # Click "Sign In" button
        signin_btn = self._find_first_element([
            'button[type="submit"]',
            'input[type="submit"]',
            'button[data-qa="login-submit"]',
        ])

        # Fallback: find button by text
        if not signin_btn:
            all_buttons = self.driver.find_elements(By.CSS_SELECTOR, "button")
            for btn in all_buttons:
                if "sign in" in btn.text.strip().lower():
                    signin_btn = btn
                    break

        if not signin_btn:
            raise NoSuchElementException("Sign-in button not found.")

        self.human.random_mouse_move()
        self.human.random_sleep(0.2, 0.5)
        self.human.human_click(signin_btn)
        self.log.info("   ➡️  Clicked 'Sign In'.")

        # ══════════════════════════════════════════════════════════════
        # STEP 4: Handle 2FA — 8-digit email verification code
        #
        # Nike may ask for an 8-digit code sent to your email after
        # password entry. The bot pauses and lets you type it manually.
        # ══════════════════════════════════════════════════════════════
        self.human.random_sleep(3, 5)

        # Check if the 2FA code screen appeared
        code_input = self._find_first_element([
            'input[name="verificationCode"]',
            'input[name="code"]',
            'input[placeholder*="code"]',
            'input[placeholder*="Code"]',
            'input[aria-label*="code"]',
            'input[aria-label*="digit"]',
            'input[type="tel"]',
            'input[inputmode="numeric"]',
        ])

        # Also check for the heading text as a signal
        if not code_input:
            page_text = self.driver.page_source.lower()
            if "8-digit code" in page_text or "verification code" in page_text or "enter the" in page_text and "code" in page_text:
                # The code input might have a generic selector — find any visible input
                all_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input")
                for inp in all_inputs:
                    try:
                        if inp.is_displayed() and inp.get_attribute("type") in ("text", "tel", "number", ""):
                            code_input = inp
                            break
                    except StaleElementReferenceException:
                        continue

        if code_input:
            self.log.info("")
            self.log.info("=" * 60)
            self.log.info("📱  2FA VERIFICATION CODE REQUIRED")
            self.log.info("=" * 60)
            self.log.info("   Nike sent an 8-digit code to your email.")
            self.log.info("   Please enter the code in the browser window.")
            self.log.info("   The bot will wait and continue automatically")
            self.log.info("   once you're logged in.")
            self.log.info("=" * 60)
            self.log.info("")

            # Wait for the user to enter the code and get redirected
            # Poll every 2 seconds, up to 5 minutes
            max_wait = 300  # 5 minutes
            start_time = time.time()

            while time.time() - start_time < max_wait:
                if not self._is_on_login_page():
                    self.log.info("✅  2FA complete — logged in!")
                    return
                elapsed = int(time.time() - start_time)
                if elapsed % 30 == 0 and elapsed > 0:
                    remaining = max_wait - elapsed
                    self.log.info(f"   ⏳  Still waiting for code… ({remaining}s left)")
                time.sleep(2)

            raise RuntimeError(
                "Timed out waiting for 2FA code entry (5 min). "
                "Please try again."
            )
        
        # No 2FA screen — wait for normal login redirect
        try:
            WebDriverWait(self.driver, 20).until(
                lambda d: not self._is_on_login_page()
            )
        except TimeoutException:
            # Check for error messages
            error_selectors = [
                '[data-qa="login-error"]',
                '.nike-unite-error-message',
                '[class*="error"]',
                '[class*="Error"]',
            ]
            for sel in error_selectors:
                if self.helper.element_exists(By.CSS_SELECTOR, sel):
                    err_el = self.driver.find_element(By.CSS_SELECTOR, sel)
                    raise RuntimeError(f"Login error: {err_el.text}")
            raise RuntimeError("Login timed out — still on /login page.")

        self.log.info("✅  Browser login successful!")
        self.log.info(f"   📍  Post-login URL: {self.driver.current_url}")

    def _is_on_login_page(self) -> bool:
        """Check if the browser is still on any Nike login/auth page."""
        url = self.driver.current_url.lower()
        return any(indicator in url for indicator in self.LOGIN_PAGE_INDICATORS)

    def _verify_logged_in(self) -> bool:
        """Check if we're actually logged in after API token injection."""
        try:
            self.driver.get("https://www.nike.com/member/profile")
            time.sleep(3)
            if self._is_on_login_page():
                return False
            return True
        except Exception:
            return False

    def _find_first_element(self, selectors: list):
        """Return the first visible element matched from a list of CSS selectors."""
        for sel in selectors:
            try:
                el = self.driver.find_element(By.CSS_SELECTOR, sel)
                if el.is_displayed():
                    return el
            except NoSuchElementException:
                continue
        return None

    # ── 2. Wait for drop ─────────────────────────────────────────────

    def wait_for_drop(self):
        """Sleep until the configured drop time."""
        if not self.config.drop_time:
            self.log.info("⏩  No drop time set — proceeding now.")
            return

        target = datetime.fromisoformat(self.config.drop_time)
        now = datetime.now()

        if now >= target:
            self.log.info("⏩  Drop time already passed — proceeding now.")
            return

        delta = (target - now).total_seconds()
        self.log.info(
            f"⏰  Waiting for drop at {target.isoformat()} "
            f"({delta:.0f}s / {delta / 60:.1f}min away)"
        )

        # Keep the session alive with periodic light actions
        while True:
            remaining = (target - datetime.now()).total_seconds()
            if remaining <= 0:
                break

            if remaining > 120:
                self.log.info(f"   ⏳ {remaining:.0f}s remaining…")
                self._keep_session_alive()
                time.sleep(min(remaining - 10, 60))
            elif remaining > 5:
                time.sleep(1)
            else:
                time.sleep(0.05)

        self.log.info("🔔  DROP TIME — GO!")

    def _keep_session_alive(self):
        """Perform a light page action to prevent session timeout."""
        try:
            self.driver.execute_script("void(0);")
        except Exception:
            pass

    # ── 3. Navigate to shoe page ─────────────────────────────────────

    def navigate_to_shoe(self):
        """Load the product page, refreshing until sizes appear."""
        self.log.info(f"🌐  Loading shoe page: {self.config.shoe_url}")

        for attempt in range(1, self.config.retry_limit + 1):
            try:
                self.driver.get(self.config.shoe_url)
                self.human.random_sleep(1.5, 3.0)

                WebDriverWait(self.driver, self.config.element_timeout).until(
                    lambda d: (
                        d.find_elements(By.CSS_SELECTOR, '[data-qa="size-available"]')
                        or d.find_elements(By.CSS_SELECTOR, 'button[data-qa="add-to-cart"]')
                        or d.find_elements(By.CSS_SELECTOR, 'button[aria-label*="Add to"]')
                        or d.find_elements(By.CSS_SELECTOR, '.size-grid-button')
                        or d.find_elements(By.CSS_SELECTOR, '[class*="SizeGrid"] button')
                    )
                )
                self.log.info("✅  Shoe page loaded.")
                return
            except TimeoutException:
                self.log.warning(
                    f"⚠️  Sizes not found (attempt {attempt}). "
                    f"Refreshing in {self.config.refresh_interval}s…"
                )
                self._screenshot(f"shoe_page_{attempt}")
                time.sleep(self.config.refresh_interval)

        raise RuntimeError("Could not load shoe page with available sizes.")

    # ── 4. Select size ───────────────────────────────────────────────

    def select_size(self):
        """Click the button matching the desired shoe size."""
        self.log.info(f"👟  Selecting size {self.config.shoe_size}…")

        def _do_select():
            self.human.random_sleep(0.5, 1.0)

            # Strategy A: Specific selectors
            size_selectors = [
                f'button[data-qa="size-available"][aria-label*="{self.config.shoe_size}"]',
                f'button.size-grid-button[aria-label*="{self.config.shoe_size}"]',
                f'button[aria-label="US {self.config.shoe_size}"]',
                f'button[aria-label="M {self.config.shoe_size} / W"]',
            ]
            for sel in size_selectors:
                try:
                    el = WebDriverWait(self.driver, 3).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, sel))
                    )
                    self.human.human_click(el)
                    self.log.info(f"✅  Size {self.config.shoe_size} selected!")
                    self.human.random_sleep(0.3, 0.8)
                    return
                except (TimeoutException, NoSuchElementException):
                    continue

            # Strategy B: Text matching across all size-like buttons
            buttons = self.driver.find_elements(
                By.CSS_SELECTOR,
                '[data-qa="size-available"], .size-grid-button, '
                'button[class*="size"], div[class*="size"] button, '
                '[class*="SizeGrid"] button',
            )
            target = self.config.shoe_size.strip()

            for btn in buttons:
                txt = btn.text.strip()
                aria = btn.get_attribute("aria-label") or ""
                if (
                    txt == target
                    or txt.endswith(f" {target}")
                    or target in aria
                ):
                    self.human.human_click(btn)
                    self.log.info(f"✅  Size {target} selected (text match)!")
                    self.human.random_sleep(0.3, 0.8)
                    return

            available = [b.text.strip() for b in buttons if b.text.strip()]
            raise NoSuchElementException(
                f"Size '{target}' not found. Available: {available}"
            )

        self._retry(_do_select, "select_size")

    # ── 5. Add to cart ───────────────────────────────────────────────

    def add_to_cart(self):
        """Click 'Add to Cart' / 'Buy'."""
        self.log.info("🛒  Adding to cart…")

        def _do_add():
            add_selectors = [
                'button[data-qa="add-to-cart"]',
                'button[aria-label*="Add to Cart"]',
                'button[aria-label*="Add to Bag"]',
                'button[aria-label*="Buy"]',
                'button.add-to-cart-btn',
                'button.ncss-btn-primary-dark',
                'button[data-qa="feed-buy-cta"]',
            ]
            for sel in add_selectors:
                try:
                    el = WebDriverWait(self.driver, 4).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, sel))
                    )
                    self.human.human_click(el)
                    self.log.info("✅  Added to cart!")
                    self.human.random_sleep(2, 4)
                    return
                except (TimeoutException, NoSuchElementException):
                    continue

            raise NoSuchElementException("Add-to-cart button not found.")

        self._retry(_do_add, "add_to_cart")

    # ── 6. Begin checkout ────────────────────────────────────────────

    def begin_checkout(self):
        """Navigate to the checkout page."""
        self.log.info("💳  Starting checkout…")

        def _do_checkout():
            checkout_selectors = [
                'button[data-qa="checkout-link"]',
                'a[data-qa="checkout-link"]',
                'button[aria-label*="Checkout"]',
                'a[href*="/checkout"]',
                'button[data-qa="cart-checkout-button"]',
            ]
            for sel in checkout_selectors:
                try:
                    el = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, sel))
                    )
                    self.human.human_click(el)
                    self.human.random_sleep(2, 4)
                    if "/checkout" in self.driver.current_url:
                        self.log.info("✅  On checkout page.")
                        return
                except (TimeoutException, NoSuchElementException):
                    continue

            # Direct fallback
            self.driver.get(f"{self.NIKE_BASE_URL}/checkout")
            self.human.random_sleep(2, 3)

            if "/checkout" in self.driver.current_url:
                self.log.info("✅  On checkout page (direct URL).")
                return

            raise RuntimeError("Could not reach checkout page.")

        self._retry(_do_checkout, "begin_checkout")

    # ── 7. Fill shipping ─────────────────────────────────────────────

    def fill_shipping(self):
        """Fill the shipping/address form (skip if pre-filled)."""
        self.log.info("📦  Filling shipping info…")

        def _do_shipping():
            self.human.random_sleep(2, 3)

            if self._step_already_complete("shipping"):
                self.log.info("✅  Shipping already saved — skipping.")
                return

            field_map = {
                'input[id*="firstName"], input[name*="firstName"]': self.profile.first_name,
                'input[id*="lastName"], input[name*="lastName"]': self.profile.last_name,
                'input[id*="address1"], input[name*="address1"]': self.profile.address_line1,
                'input[id*="address2"], input[name*="address2"]': self.profile.address_line2,
                'input[id*="city"], input[name*="city"]': self.profile.city,
                'input[id*="state"], input[name*="state"], select[id*="state"]': self.profile.state,
                'input[id*="postalCode"], input[name*="postalCode"], input[id*="zip"]': self.profile.zip_code,
                'input[id*="phone"], input[name*="phone"]': self.profile.phone,
            }

            for selector_group, value in field_map.items():
                if not value:
                    continue
                for sel in selector_group.split(", "):
                    try:
                        el = self.driver.find_element(By.CSS_SELECTOR, sel)
                        if el.is_displayed():
                            self.human.human_clear_and_type(el, value)
                            self.human.random_sleep(0.2, 0.5)
                            break
                    except NoSuchElementException:
                        continue

            self.human.random_sleep(0.5, 1.0)
            self._click_continue_button()
            self.human.random_sleep(2, 3)
            self.log.info("✅  Shipping submitted.")

        self._retry(_do_shipping, "fill_shipping")

    # ── 8. Fill payment ──────────────────────────────────────────────

    def fill_payment(self):
        """Fill credit card details (often inside iframes)."""
        self.log.info("💳  Filling payment info…")

        def _do_payment():
            self.human.random_sleep(2, 3)

            if self._step_already_complete("payment"):
                self.log.info("✅  Payment already saved — skipping.")
                return

            exp_value = f"{self.profile.card_exp_month}/{self.profile.card_exp_year[-2:]}"

            iframe_card_map = {
                'iframe[title*="card number"], iframe[id*="cardNumber"]': (
                    'input[id*="cardNumber"], input[name*="cardNumber"], input[name*="credit-card-number"], input',
                    self.profile.card_number,
                ),
                'iframe[title*="expiration"], iframe[id*="expirationDate"]': (
                    'input[id*="expiration"], input[name*="expirationDate"], input',
                    exp_value,
                ),
                'iframe[title*="CVV"], iframe[title*="cvv"], iframe[id*="cvv"]': (
                    'input[id*="cvv"], input[name*="cvv"], input',
                    self.profile.card_cvv,
                ),
            }

            for iframe_sel_group, (input_sel_group, value) in iframe_card_map.items():
                if not value:
                    continue

                filled = False
                for iframe_sel in iframe_sel_group.split(", "):
                    if filled:
                        break
                    try:
                        self.helper.switch_to_iframe(
                            By.CSS_SELECTOR, iframe_sel, timeout=5
                        )
                        for inp_sel in input_sel_group.split(", "):
                            try:
                                inp = self.driver.find_element(By.CSS_SELECTOR, inp_sel)
                                self.human.human_clear_and_type(inp, value)
                                filled = True
                                break
                            except NoSuchElementException:
                                continue
                        self.helper.switch_to_default()
                    except (TimeoutException, NoSuchElementException):
                        self.helper.switch_to_default()

                # Non-iframe fallback
                if not filled:
                    for inp_sel in input_sel_group.split(", "):
                        try:
                            inp = self.driver.find_element(By.CSS_SELECTOR, inp_sel)
                            if inp.is_displayed():
                                self.human.human_clear_and_type(inp, value)
                                break
                        except NoSuchElementException:
                            continue

                self.human.random_sleep(0.3, 0.6)

            # Billing = Shipping checkbox
            try:
                billing_cb = self.driver.find_element(
                    By.CSS_SELECTOR,
                    'input[id*="billingAddress"], input[name*="sameAs"]'
                )
                if not billing_cb.is_selected():
                    self.human.human_click(billing_cb)
            except NoSuchElementException:
                pass

            self._click_continue_button()
            self.human.random_sleep(2, 3)
            self.log.info("✅  Payment submitted.")

        self._retry(_do_payment, "fill_payment")

    # ── 9. Submit order ──────────────────────────────────────────────

    def submit_order(self):
        """Click the final Place Order button."""
        self.log.info("🚀  Submitting order…")

        def _do_submit():
            self.human.random_sleep(1, 2)
            submit_selectors = [
                'button[data-qa="save-button"]',
                'button[data-qa="place-order"]',
                'button[aria-label*="Place Order"]',
                'button[aria-label*="Submit Order"]',
                'button.checkout-submit',
            ]
            for sel in submit_selectors:
                try:
                    el = WebDriverWait(self.driver, 6).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, sel))
                    )
                    self.human.human_click(el)
                    self.human.random_sleep(3, 5)
                    self.log.info("✅  Order submitted!")
                    self._screenshot("order_submitted")
                    return
                except (TimeoutException, NoSuchElementException):
                    continue

            raise NoSuchElementException("Submit order button not found.")

        self._retry(_do_submit, "submit_order")

    # ── Shared Helpers ───────────────────────────────────────────────

    def _click_continue_button(self):
        """Click a continue/save/next button."""
        selectors = [
            'button[data-qa="save-button"]',
            'button[data-qa="continue-button"]',
            'button[aria-label*="Continue"]',
            'button[aria-label*="Save"]',
            'button.continue-btn',
            'button[type="submit"]',
        ]
        for sel in selectors:
            try:
                el = WebDriverWait(self.driver, 3).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, sel))
                )
                self.human.human_click(el)
                return
            except (TimeoutException, NoSuchElementException):
                continue
        self.log.warning("⚠️  No continue/save button found.")

    def _step_already_complete(self, step_name: str) -> bool:
        """Check if a checkout step was pre-filled from the user's account."""
        indicators = {
            "shipping": ['[data-qa="payment"]', 'iframe[title*="card"]'],
            "payment": ['[data-qa="place-order"]', 'button[aria-label*="Place Order"]'],
        }
        for sel in indicators.get(step_name, []):
            if self.helper.element_exists(By.CSS_SELECTOR, sel):
                return True
        return False


# ──────────────────────────────────────────────────────────────────────
# Configuration Loader
# ──────────────────────────────────────────────────────────────────────

CONFIG_TEMPLATE = {
    "user": {
        "email": "your_email@example.com",
        "password": "your_password",
        "first_name": "John",
        "last_name": "Doe",
        "address_line1": "123 Sneaker Street",
        "address_line2": "",
        "city": "Portland",
        "state": "OR",
        "zip_code": "97201",
        "phone": "5031234567",
        "card_number": "4111111111111111",
        "card_exp_month": "12",
        "card_exp_year": "2027",
        "card_cvv": "123",
    },
    "bot": {
        "shoe_url": "https://www.nike.com/t/air-jordan-1-retro-high-og-shoes-XXXXXX",
        "shoe_size": "10",
        "drop_time": "2026-02-05T10:00:00",
        "refresh_interval": 3.0,
        "page_load_timeout": 20,
        "element_timeout": 12,
        "headless": False,
        "retry_limit": 5,
        "log_level": "INFO",
        "type_speed_min": 0.05,
        "type_speed_max": 0.15,
        "chrome_version": 0,
    },
}


def load_config(path: str = "config.json") -> tuple[UserProfile, BotConfig]:
    """Load config from JSON, or create a template if missing."""
    if not os.path.exists(path):
        with open(path, "w") as f:
            json.dump(CONFIG_TEMPLATE, f, indent=2)
        print(f"📝  Config template created at '{path}'")
        print("    Fill in your details and run again.")
        sys.exit(0)

    with open(path) as f:
        data = json.load(f)

    profile = UserProfile(**data.get("user", {}))
    config = BotConfig(**data.get("bot", {}))
    return profile, config


# ──────────────────────────────────────────────────────────────────────
# Entry Point
# ──────────────────────────────────────────────────────────────────────

def main():
    print(
        """
╔═══════════════════════════════════════════════════════════╗
║        👟  NIKE SNKRS BOT v2 — Stealth Edition  👟        ║
║                                                           ║
║  • undetected-chromedriver (bypasses fingerprinting)      ║
║  • Nike API login (bypasses browser form)                 ║
║  • Human-like typing & mouse movement                     ║
║                                                           ║
║  ⚠️  Educational only — violates Nike ToS                 ║
╚═══════════════════════════════════════════════════════════╝
"""
    )

    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.json"
    profile, config = load_config(config_path)

    bot = NikeSNKRSBot(profile, config)
    bot.start()


if __name__ == "__main__":
    main()