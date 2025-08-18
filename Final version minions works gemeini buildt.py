# Fix bot # neuro_bot_illusion_lite.py
#
# REQUIRED DEPENDENCIES:
# pip install numpy selenium requests fake-useragent psutil "urllib3<2"
#
import time
import random
import threading
import smtplib
import json
import numpy as np
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta, date
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (NoSuchElementException,
                                        ElementClickInterceptedException,
                                        ElementNotInteractableException,
                                        TimeoutException,
                                        StaleElementReferenceException,
                                        WebDriverException,
                                        MoveTargetOutOfBoundsException)
import requests
from pathlib import Path
import hashlib
import platform
import psutil
from fake_useragent import UserAgent
import ssl
from urllib3.exceptions import InsecureRequestWarning
import socket
import traceback
import logging
import os
import sys

# Disable SSL warnings for requests (for proxy fetching/testing)
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# --- Logging Configuration ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[
                        logging.FileHandler("neuro_bot_illusion_lite.log", encoding='utf-8'),
                        logging.StreamHandler(sys.stdout)
                    ])
if platform.system() == "Windows":
    for handler in logging.root.handlers:
        if isinstance(handler, logging.StreamHandler):
            handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
            if hasattr(handler.stream, 'reconfigure'):
                handler.stream.reconfigure(encoding='utf-8')


# --- Constants ---
NEURO_VERSION = "2.7.1-IllusionLite-Intelligent-Fix" # Updated version for tracking
AD_CLICK_PROBABILITY = 0.9 # Set to 90%

# Using 2 threads is the stable, medium-risk recommendation
MAX_THREADS_DEFAULT = 2

MIN_SESSION_DURATION = 25
MAX_SESSION_DURATION = 70
MAX_AD_CLICKS = 5
MAX_RETRIES = 2
RETRY_DELAY_BASE = 5
PROXY_REFRESH_INTERVAL = 3600

# --- Illusion Engine Specific Constants ---
DAILY_VISIT_QUOTA = random.randint(500, 1000)

# --- Proxy Constants ---
TRUSTED_PROXIES = [] # Populate this list or use environment variable
PROXY_TEST_URLS = ["http://example.com", "http://google.com"]
PROXY_TEST_TIMEOUT = 8
PROXY_MAX_ATTEMPTS = 3

# --- Ad Detection Selectors ---
AD_SELECTORS = list(set([
    '.ad', '.ads', '.advertisement', '[class*="ad-"]',
    '[id*="ad-"]', '.banner-ad', '.ad-banner', '.ad-wrapper',
    '.ad-container', '.ad-unit', '.advert',
    '.adslot', '.ad-placeholder', '.adlink', '.adbox',
    '.product-ad', '.deal-ad', '.promo-box', '.sponsored',
    '.recommended', '.sponsored-content', '.partner-box',
    '[data-ad]', '[data-ad-id]', '[data-ad-target]',
    '[data-ad-client]', '[data-ad-slot]', '[data-ad-type]',
    'iframe[src*="ads"]', 'iframe[src*="adserver"]',
    'iframe[src*="doubleclick"]', 'iframe[src*="googleadservices"]',
    '.widget_sp_image', '.imagewidget', '.promoted-link',
    '.affiliate-link', '.partner-link'
]))

# --- NeuroPersonalityCore ---
class NeuroPersonalityCore:
    ARCHETYPES = {
        'ad_clicker': { # High ad interaction
            'traits': {'neuroticism': 0.6, 'openness': 0.5, 'extraversion': 0.4},
            'behavior': {'scroll_speed': 1.3, 'click_accuracy': 0.8, 'ad_avoidance': 0.1, 'reading_pattern': 'skimming'},
            'ad_behavior': {'click_probability': 0.9, 'max_clicks': MAX_AD_CLICKS},
            'session_duration_modifier': (0.9, 1.2)
        },
        'shopper': { # High ad interaction, product-focused
            'traits': {'extraversion': 0.6, 'openness': 0.5, 'neuroticism': 0.4},
            'behavior': {'scroll_speed': 1.2, 'click_accuracy': 0.8, 'ad_avoidance': 0.2, 'reading_pattern': 'scanning'},
            'ad_behavior': {'click_probability': 0.75, 'max_clicks': 4},
            'session_duration_modifier': (1.0, 1.3)
        },
        'casual_reader': { # Lower ad interaction, content-focused
            'traits': {'neuroticism': 0.3, 'conscientiousness': 0.7, 'agreeableness': 0.6},
            'behavior': {'scroll_speed': 1.0, 'click_accuracy': 0.6, 'ad_avoidance': 0.5, 'reading_pattern': 'linear'},
            'ad_behavior': {'click_probability': 0.3, 'max_clicks': 2},
            'session_duration_modifier': (1.0, 1.2)
        },
        'researcher': { # Very low ad interaction, deep content
            'traits': {'openness': 0.9, 'conscientiousness': 0.8, 'extraversion': 0.2},
            'behavior': {'scroll_speed': 0.8, 'click_accuracy': 0.9, 'ad_avoidance': 0.7, 'reading_pattern': 'deep'},
            'ad_behavior': {'click_probability': 0.1, 'max_clicks': 1},
            'session_duration_modifier': (1.1, 1.4)
        },
        'bouncer': { # Very short visit, high bounce
            'traits': {'neuroticism': 0.5, 'openness': 0.2, 'extraversion': 0.3},
            'behavior': {'scroll_speed': 1.8, 'click_accuracy': 0.5, 'ad_avoidance': 0.9, 'reading_pattern': 'none'},
            'ad_behavior': {'click_probability': 0.01, 'max_clicks': 0},
            'session_duration_modifier': (0.1, 0.25)
        },
        'skimmer': { # Fast reads, surface interaction, multiple pages if possible
            'traits': {'openness': 0.7, 'extraversion': 0.6, 'conscientiousness': 0.4},
            'behavior': {'scroll_speed': 1.7, 'click_accuracy': 0.7, 'ad_avoidance': 0.4, 'reading_pattern': 'skimming'},
            'ad_behavior': {'click_probability': 0.2, 'max_clicks': 1},
            'session_duration_modifier': (0.8, 1.1)
        },
        'idle_reader': { # Loads page, simulates idle presence, few interactions
            'traits': {'neuroticism': 0.2, 'conscientiousness': 0.5, 'agreeableness': 0.7},
            'behavior': {'scroll_speed': 0.9, 'click_accuracy': 0.6, 'ad_avoidance': 0.6, 'reading_pattern': 'linear_slow_start'},
            'ad_behavior': {'click_probability': 0.05, 'max_clicks': 1},
            'session_duration_modifier': (1.2, 1.8)
        }
    }

    @staticmethod
    def generate_personality():
        if random.random() < AD_CLICK_PROBABILITY:
            archetype_candidate = random.choice(['ad_clicker', 'shopper'])
        else:
            archetype_candidate = random.choice(['casual_reader', 'researcher', 'bouncer', 'skimmer', 'idle_reader'])

        if archetype_candidate == 'bouncer' and random.random() > 0.3:
            archetype_candidate = random.choice(['casual_reader', 'researcher', 'skimmer', 'idle_reader'])

        base = NeuroPersonalityCore.ARCHETYPES[archetype_candidate]

        traits = {
            'cognitive': {
                'openness': np.clip(base['traits'].get('openness', 0.5) + random.uniform(-0.2, 0.2), 0, 1),
                'curiosity': random.uniform(0, 1), 'learning_speed': random.uniform(0.3, 0.9)},
            'emotional': {
                'neuroticism': np.clip(base['traits'].get('neuroticism', 0.5) + random.uniform(-0.2, 0.2), 0, 1),
                'mood_stability': random.uniform(0.2, 0.8), 'stress_response': random.uniform(0.1, 0.9)},
            'social': {
                'extraversion': np.clip(base['traits'].get('extraversion', 0.5) + random.uniform(-0.2, 0.2), 0, 1),
                'agreeableness': np.clip(base['traits'].get('agreeableness', 0.5) + random.uniform(-0.2, 0.2), 0, 1),
                'trust': random.uniform(0.2, 0.8)},
            'motor': {
                'coordination': random.uniform(0.4, 0.9), 'speed_variability': random.uniform(0.1, 0.7),
                'accuracy': np.clip(base['behavior'].get('click_accuracy', 0.5) + random.uniform(-0.2, 0.2), 0, 1)}
        }
        behavior = {
            'scroll_speed': base['behavior'].get('scroll_speed', 1.0) * random.uniform(0.8, 1.2),
            'ad_avoidance': base['behavior'].get('ad_avoidance', 0.5) * random.uniform(0.7, 1.3),
            'reading_pattern': base['behavior'].get('reading_pattern', 'linear'),
            'attention_span': random.uniform(5, 45) * (0.5 if archetype_candidate == 'bouncer' else 1.0),
            'error_rate': 1 - traits['motor']['accuracy'],
            'device_preference': random.choice(['desktop', 'mobile', 'tablet']),
            'ad_click_probability': np.clip(base['ad_behavior']['click_probability'] * random.uniform(0.8, 1.2), 0, 1),
            'max_ad_clicks': min(MAX_AD_CLICKS, base['ad_behavior']['max_clicks'] + random.randint(-1, 1)),
            'session_duration_modifier': base.get('session_duration_modifier', (0.9, 1.1))
        }

        possible_referrers = [
            None, "https://www.google.com/", "https://www.bing.com/",
            "https://duckduckgo.com/", "https://t.co/", "https://www.facebook.com/",
        ]
        chosen_referrer = random.choice(possible_referrers)
        if archetype_candidate == 'bouncer' and random.random() < 0.7:
            chosen_referrer = None

        fingerprint = {
            'browser_taints': NeuroPersonalityCore.generate_browser_taints(),
            'device_profile': NeuroPersonalityCore.generate_device_profile(behavior['device_preference']),
            'network_profile': NeuroPersonalityCore.generate_network_profile(),
            'referrer_url': chosen_referrer
        }
        return {'archetype': archetype_candidate, 'traits': traits, 'behavior': behavior, 'fingerprint': fingerprint,
                'state': 'initializing', 'cognitive_load': 0.0,
                'session_goals': random.sample(['read_content', 'find_deals', 'social_interact', 'time_waste'], k=random.randint(1,2)),
                'ad_clicks': 0}

    @staticmethod
    def generate_browser_taints():
        return [f"canvas_noise:{random.randint(1, 10)}",
                f"audio_ctx_hash:{hashlib.md5(str(random.random()).encode()).hexdigest()[:8]}",
                f"webgl_vendor:{random.choice(['Intel Inc.', 'NVIDIA Corporation', 'AMD', 'Google Inc. (ANGLE)'])}",
                f"timezone_offset:{random.choice(range(-12*60, 14*60+1, 15))}",
                f"font_hash:{hashlib.sha256(str(random.random()).encode()).hexdigest()[:16]}"]

    @staticmethod
    def generate_device_profile(device_type):
        if device_type == 'mobile':
            return {'type': 'mobile', 'os': random.choice(['iOS 17.1', 'Android 13', 'iOS 16.5', 'Android 14']),
                    'screen': f"{random.choice([375, 390, 412, 414])}x{random.choice([667, 812, 844, 852, 896])}",
                    'touch': True, 'pixel_ratio': random.choice([2, 3])}
        elif device_type == 'tablet':
            return {'type': 'tablet', 'os': random.choice(['iPadOS 17', 'Android 13 Tablet', 'iPadOS 16.2']),
                    'screen': f"{random.choice([768, 810, 834])}x{random.choice([1024, 1080, 1112, 1180])}",
                    'touch': True, 'pixel_ratio': random.choice([1, 2])}
        else: # desktop
            return {'type': 'desktop', 'os': random.choice(['Windows 10', 'Windows 11', 'Mac OS X 10.15', 'Mac OS X 13.0']),
                    'screen': f"{random.choice([1280, 1366, 1440, 1536, 1920])}x{random.choice([720, 768, 800, 864, 900, 1080])}",
                    'touch': False, 'pixel_ratio': random.choice([1, 1.25, 1.5, 2])}

    @staticmethod
    def generate_network_profile():
        return {'latency': random.randint(10, 350),
                'bandwidth': random.choice(['DSL', 'Cable', 'Fiber', '4G LTE', '5G', 'Satellite']),
                'stability': random.uniform(0.6, 0.99)}

class AutoPilot:
    def __init__(self, driver, personality):
        self.driver = driver
        self.personality = personality
        self.state_machine = {
            'initializing': self._state_initializing, 'browsing': self._state_browsing,
            'reading': self._state_reading, 'interacting': self._state_interacting,
            'distracted': self._state_distracted, 'ad_scanning': self._state_ad_scanning,
            'idling': self._state_idling, 'bouncing': self._state_bouncing
            }
        self.current_state = 'initializing'
        self.last_state_change = time.time()
        self.cognitive_load = 0.0
        self.attention_span = personality['behavior']['attention_span']
        self.reading_progress = 0
        self.behavior_log = []
        self.ad_elements = []
        self.last_ad_scan = 0
        self.idle_cycles = 0

    def _human_scroll(self, scroll_amount=None):
        try:
            scroll_duration = random.uniform(0.8, 1.5)
            if scroll_amount is None:
                scroll_amount = random.uniform(0.2, 0.8)

            start_time = time.time()
            start_scroll_pos = self.driver.execute_script("return window.pageYOffset;")
            target_scroll_pos = start_scroll_pos + (self.driver.execute_script("return window.innerHeight;") * scroll_amount)

            while time.time() - start_time < scroll_duration:
                elapsed = time.time() - start_time
                progress = elapsed / scroll_duration
                # Use ease-in-out function for realistic acceleration/deceleration
                eased_progress = 0.5 - 0.5 * np.cos(np.pi * progress)
                current_scroll = start_scroll_pos + (target_scroll_pos - start_scroll_pos) * eased_progress
                self.driver.execute_script(f"window.scrollTo(0, {current_scroll});")
                time.sleep(0.01)

            # Final scroll to ensure we hit the target
            self.driver.execute_script(f"window.scrollTo(0, {target_scroll_pos});")
            self.cognitive_load += random.uniform(0.01, 0.05)
            self.behavior_log.append({'time': datetime.now().isoformat(), 'event': 'scroll', 'distance_factor': scroll_amount})
            logging.info(f"Scrolled down by {scroll_amount*100:.0f}% of viewport height.")
        except Exception as e:
            logging.error(f"Error during human scroll: {e}")

    def _human_click(self, element):
        try:
            # First, scroll to the element's location
            self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
            time.sleep(random.uniform(0.5, 1.5))

            # Simulate a slight hover and then a click
            actions = ActionChains(self.driver)
            actions.move_to_element(element)
            actions.pause(random.uniform(0.5, 1.5))
            actions.click(element)
            actions.perform()

            self.cognitive_load += random.uniform(0.1, 0.2)
            self.behavior_log.append({'time': datetime.now().isoformat(), 'event': 'click', 'element_tag': element.tag_name})
            logging.info(f"Clicked on an element with tag: {element.tag_name}")
            return True
        except (ElementClickInterceptedException, ElementNotInteractableException, MoveTargetOutOfBoundsException, StaleElementReferenceException) as e:
            logging.warning(f"Click failed: {e}. Trying JavaScript click as fallback.")
            try:
                self.driver.execute_script("arguments[0].click();", element)
                self.behavior_log.append({'time': datetime.now().isoformat(), 'event': 'js_click_fallback', 'element_tag': element.tag_name})
                logging.info(f"Successfully clicked via JavaScript fallback.")
                return True
            except Exception as e_js:
                logging.error(f"JavaScript click also failed: {e_js}")
                return False
        except Exception as e:
            logging.error(f"Unexpected error during human click: {e}")
            return False

    def _human_type(self, element, text):
        try:
            # Scroll to element and click to focus
            self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
            time.sleep(random.uniform(0.5, 1.0))
            element.click()
            time.sleep(random.uniform(0.2, 0.5))

            # Simulate typing character by character
            for char in text:
                element.send_keys(char)
                time.sleep(random.uniform(0.05, 0.2)) # Vary the typing speed

            self.cognitive_load += random.uniform(0.05, 0.1)
            self.behavior_log.append({'time': datetime.now().isoformat(), 'event': 'type', 'text_length': len(text)})
            logging.info(f"Typed {len(text)} characters.")
            return True
        except Exception as e:
            logging.error(f"Error during human type: {e}")
            return False

    def _update_cognitive_load(self):
        """Simulates mental fatigue and recovery."""
        self.cognitive_load = max(0.0, self.cognitive_load * 0.95 + (random.uniform(0.01, 0.05) * self.personality['traits']['cognitive']['neuroticism']))

    def _transition_to(self, new_state):
        if self.current_state != new_state:
            self.behavior_log.append({'time': datetime.now().isoformat(), 'event': 'state_transition', 'from': self.current_state, 'to': new_state})
            logging.info(f"Transitioning from {self.current_state} to {new_state}.")
            self.current_state = new_state
            self.last_state_change = time.time()

    def step(self):
        try:
            if self.personality['archetype'] == 'bouncer' and self.current_state != 'bouncing':
                if self.current_state == 'initializing' and (time.time() - self.last_state_change) > random.uniform(0.5,2):
                     self._transition_to('bouncing')
                elif self.current_state != 'initializing':
                     self._transition_to('bouncing')

            self._evaluate_state()
            if time.time() - self.last_ad_scan > random.uniform(10, 30):
                self._scan_for_ads()
                self.last_ad_scan = time.time()

            if self.current_state in self.state_machine: self.state_machine[self.current_state]()
            else:
                logging.warning(f"Unknown state: {self.current_state}, defaulting to browsing.")
                self._transition_to('browsing')
                self.state_machine['browsing']()
            self._update_cognitive_load()
        except Exception as e:
            self.behavior_log.append({'time': datetime.now().isoformat(), 'event': 'autopilot_step_error',
                                      'details': str(e), 'state': self.current_state, 'stacktrace': traceback.format_exc()})
            logging.error(f"Error within AutoPilot step (State: {self.current_state}): {type(e).__name__} - {e}", exc_info=False)

    def _scan_for_ads(self):
        current_ads = []
        unique_ad_locations = {}
        for selector in AD_SELECTORS:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elements:
                    try:
                        if not (el.is_enabled() and el.size['width'] > 10 and el.size['height'] > 10): continue
                        if el.is_displayed():
                            loc = el.location
                            pos_key = f"{loc['x']}_{loc['y']}_{el.size['width']}_{el.size['height']}"
                            if pos_key not in unique_ad_locations:
                                current_ads.append(el)
                                unique_ad_locations[pos_key] = el
                    except (StaleElementReferenceException, WebDriverException): continue
            except WebDriverException: continue
        self.ad_elements = current_ads
        if self.ad_elements:
             self.behavior_log.append({'time': datetime.now().isoformat(), 'event': 'ad_scan_completed',
                                   'ads_found_visible': len(self.ad_elements), 'state': self.current_state})

    # --- NEW: Ad Scoring System ---
    def _score_and_select_ad(self, clickable_ads):
        AD_KEYWORDS = [
            'sale', 'deal', 'discount', 'offer', 'save', 'shop now',
            'limited time', 'clearance', 'free shipping', 'buy now'
        ]

        scored_ads = []
        try:
            viewport_height = self.driver.execute_script("return window.innerHeight;")
        except WebDriverException:
            viewport_height = 800 # Fallback

        for ad in clickable_ads:
            score = 1.0
            try:
                # Score based on size (bigger is better)
                size = ad.size
                if size and size['width'] > 1 and size['height'] > 1:
                    score += (size['width'] * size['height']) / 10000.0 # Normalize

                # Score based on position (higher on page is better)
                location = ad.location
                if location and location['y'] < viewport_height * 1.5: # Is it near the visible area?
                    score += 15

                # Score based on enticing keywords
                # FIX: Safely access ad.text to prevent errors if it's None
                ad_text = (ad.text or "").lower()
                if any(keyword in ad_text for keyword in AD_KEYWORDS):
                    score *= 2.5 # Big bonus for good keywords
                    logging.info(f"Found high-value ad with text: '{ad.text[:50]}...'")

            except (StaleElementReferenceException, WebDriverException):
                continue # Skip stale elements

            scored_ads.append((ad, score))

        if not scored_ads:
            return None

        # Unpack ads and scores for weighted random choice
        ads, scores = zip(*scored_ads)
        return random.choices(ads, weights=scores, k=1)[0]

    def _state_ad_scanning(self):
        if (self.personality['ad_clicks'] >= self.personality['behavior']['max_ad_clicks'] or not self.ad_elements):
            self._transition_to('browsing')
            return

        clickable_ads = [ad for ad in self.ad_elements if ad.is_displayed() and ad.is_enabled()]
        if not clickable_ads:
            self._transition_to('browsing')
            return

        if random.random() < self.personality['behavior']['ad_click_probability']:
            # MODIFICATION: Use the scoring system to select the best ad
            ad_to_click = self._score_and_select_ad(clickable_ads)
            if not ad_to_click:
                self._transition_to('browsing')
                return

            ad_loc_before_click_val = None
            try: ad_loc_before_click_val = ad_to_click.location_once_scrolled_into_view
            except StaleElementReferenceException: logging.warning("Ad element for location stale.")

            # --- NEW: Reconsideration Scroll ---
            if random.random() < 0.4: # 40% chance to perform this human-like hesitation
                logging.info("Humanizing: Performing a 'reconsideration' scroll...")
                self._human_scroll(random.uniform(0.1, 0.2)) # Scroll a little bit past the ad
                time.sleep(random.uniform(1.0, 2.5))
                # The _human_click method will automatically scroll back to the element

            try:
                logging.info(f"Personality {self.personality['archetype']} hovering over ad.")
                ActionChains(self.driver).move_to_element(ad_to_click).pause(random.uniform(2, 5)).perform()
            except Exception as e_hover: logging.warning(f"Error during pre-ad-click hover: {e_hover}")

            if self._human_click(ad_to_click):
                self.personality['ad_clicks'] += 1
                self.behavior_log.append({'time': datetime.now().isoformat(), 'event': 'ad_click',
                                          'ad_position': ad_loc_before_click_val,
                                          'total_ad_clicks_this_session': self.personality['ad_clicks']})
                logging.info(f"Clicked ad. Total ad clicks: {self.personality['ad_clicks']}")
                time.sleep(random.uniform(3, 8)) # Pause on ad page

                if len(self.driver.window_handles) > 1:
                    original_window = self.driver.current_window_handle
                    for handle in self.driver.window_handles:
                        if handle != original_window:
                            self.driver.switch_to.window(handle)
                            time.sleep(random.uniform(0.5,1.0))
                            self.driver.close()
                            break
                    self.driver.switch_to.window(original_window)
                else:
                    try:
                        self.driver.back()
                        time.sleep(random.uniform(0.5,1.0))
                    except WebDriverException as e: logging.warning(f"Error navigating back after ad: {e}")
                time.sleep(random.uniform(0.5, 1.5))
            else: logging.warning("Attempted ad click failed by _human_click.")
        self._transition_to('browsing')

    def _evaluate_state(self):
        now = time.time()
        state_duration = now - self.last_state_change

        if self.personality['archetype'] == 'bouncer' and self.current_state not in ['bouncing', 'initializing']:
            self._transition_to('bouncing')
            return

        if self.personality['archetype'] == 'idle_reader':
            if self.current_state not in ['initializing', 'idling'] and state_duration > random.uniform(10,20) and random.random() < 0.6:
                 self._transition_to('idling')
                 return
            elif self.current_state == 'idling' and self.idle_cycles > random.randint(2,4) and random.random() < 0.4:
                self._transition_to(random.choice(['browsing', 'reading']))
                self.idle_cycles=0
                return

        # Check if it's time to consider clicking an ad
        if (self.current_state != 'ad_scanning' and self.ad_elements and
            self.personality['ad_clicks'] < self.personality['behavior']['max_ad_clicks'] and
            state_duration > random.uniform(3,10)):

            # Ad-focused personalities are much more likely to get 'distracted' by ads
            is_ad_focused = self.personality['archetype'] in ['ad_clicker', 'shopper']
            transition_probability = 0.80 if is_ad_focused else 0.35

            if random.random() < transition_probability:
                self._transition_to('ad_scanning')
                return

        if self.current_state == 'reading' and self.reading_progress >= 1.0:
            self._transition_to(random.choice(['browsing', 'interacting']))
            return
        elif random.random() < (0.03 + self.cognitive_load * 0.05) and state_duration > 7:
            self._transition_to('distracted')
            return

        if self.current_state not in ['bouncing', 'idling']:
            transition_probabilities = {
                'browsing': {'reading': 0.4, 'interacting': 0.2, 'distracted': 0.1, 'ad_scanning':0.15},
                'reading': {'browsing': 0.5, 'interacting': 0.15, 'distracted': 0.1},
                'interacting': {'browsing': 0.6, 'reading': 0.1, 'distracted': 0.15},
                'distracted': {'browsing': 0.7, 'reading': 0.1, 'interacting': 0.1}}
            current_probs_map = transition_probabilities.get(self.current_state, {'browsing': 0.8})
            choices = list(current_probs_map.keys())
            weights = list(current_probs_map.values())
            if choices and sum(weights) > 0:
                if abs(sum(weights) - 1.0) > 0.001: weights = [w / sum(weights) for w in weights]
                next_state = random.choices(choices, weights=weights, k=1)[0]
                if next_state != self.current_state: self._transition_to(next_state)
            elif self.current_state != 'browsing': self._transition_to('browsing')

    def _state_initializing(self):
        self._transition_to('browsing')

    def _state_browsing(self):
        if random.random() < 0.8:
            self._human_scroll()
        else:
            try:
                links = self.driver.find_elements(By.TAG_NAME, 'a')
                if links:
                    clickable_links = [link for link in links if link.is_displayed() and link.is_enabled()]
                    if clickable_links:
                        link_to_click = random.choice(clickable_links)
                        self._human_click(link_to_click)
                        time.sleep(random.uniform(2, 5))
            except Exception as e:
                logging.error(f"Error during browsing state: {e}")
        self._transition_to(random.choice(['browsing', 'reading', 'interacting']))

    def _state_reading(self):
        reading_speed = self.personality['behavior']['scroll_speed']
        self.reading_progress += random.uniform(0.05, 0.2) * reading_speed
        self._human_scroll(random.uniform(0.1, 0.3) * reading_speed)
        time.sleep(random.uniform(2, 5))
        if self.reading_progress >= 1.0:
            self.reading_progress = 0
            self._transition_to('browsing')

    def _state_interacting(self):
        try:
            input_fields = self.driver.find_elements(By.CSS_SELECTOR, "input[type='text'], input[type='search'], textarea")
            if input_fields and random.random() < 0.5:
                field = random.choice(input_fields)
                self._human_type(field, "test query")
            else:
                # FIX: Check if clickable elements exist before choosing one to prevent crash
                clickable_elements = (self.driver.find_elements(By.TAG_NAME, 'button') +
                                      self.driver.find_elements(By.TAG_NAME, 'a'))
                interactable = [el for el in clickable_elements if el.is_displayed() and el.is_enabled()]
                if interactable:
                    self._human_click(random.choice(interactable))

            time.sleep(random.uniform(1, 3))
        except Exception as e:
            logging.error(f"Error during interacting state: {e}")
        self._transition_to('browsing')

    def _state_distracted(self):
        time.sleep(random.uniform(5, 15))
        self._transition_to(random.choice(['browsing', 'reading']))

    def _state_idling(self):
        time.sleep(random.uniform(5, 10))
        self.idle_cycles += 1

    def _state_bouncing(self):
        time.sleep(random.uniform(1, 5))
        # The session will terminate shortly after this, as it's designed to be short

# --- Utility Functions ---

def get_proxy_list(proxy_file='proxies.txt'):
    """Reads a list of proxies from a file."""
    try:
        with open(proxy_file, 'r') as f:
            proxies = [line.strip() for line in f if line.strip()]
        logging.info(f"Loaded {len(proxies)} proxies from {proxy_file}")
        return proxies
    except FileNotFoundError:
        logging.error(f"Proxy file not found: {proxy_file}")
        return []

def get_url_list(url_file='urls.txt'):
    """Reads a list of URLs from a file."""
    try:
        with open(url_file, 'r') as f:
            urls = [line.strip() for line in f if line.strip()]
        logging.info(f"Loaded {len(urls)} URLs from {url_file}")
        return urls
    except FileNotFoundError:
        logging.error(f"URL file not found: {url_file}")
        return []

def check_and_create_files():
    """Ensures proxies.txt and urls.txt exist with sample content."""
    files_to_check = {
        'proxies.txt': ['1.1.1.1:8080', '2.2.2.2:8080'],
        'urls.txt': ['https://example.com', 'https://blog.example.com']
    }
    for filename, content in files_to_check.items():
        if not os.path.exists(filename):
            logging.warning(f"File {filename} not found. Creating a sample file.")
            with open(filename, 'w') as f:
                f.write('\n'.join(content) + '\n')
            logging.info(f"Created {filename} with sample data. Please replace with your actual data.")

# --- The visit_blog function for a single thread ---

def visit_blog(thread_id, url, proxy, master_end_time, visit_counter, total_visits):
    """
    Simulates a single user's browsing session.
    """
    driver = None
    try:
        if time.time() > master_end_time:
            return

        personality = NeuroPersonalityCore.generate_personality()

        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument(f"--user-agent={UserAgent().random}")
        chrome_options.add_argument(f'--proxy-server={proxy}')

        # Human-like browser options
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("window-size=1920,1080")
        chrome_options.add_argument("--disable-dev-shm-usage")

        # FIX: Add stealth options to avoid detection
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        # Add a random referrer if available
        if personality['fingerprint']['referrer_url']:
            chrome_options.add_argument(f'--referer={personality["fingerprint"]["referrer_url"]}')

        logging.info(f"Thread {thread_id}: Starting new session with personality '{personality['archetype']}' for {url} via {proxy}")

        try:
            driver = webdriver.Chrome(options=chrome_options)

            # FIX: Execute JS to hide webdriver flag from navigator
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            # Set a reasonable page load timeout
            driver.set_page_load_timeout(30)

            driver.get(url)
            WebDriverWait(driver, 10).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )

            # --- AutoPilot Logic ---
            autopilot = AutoPilot(driver, personality)
            session_duration_mod = random.uniform(*personality['behavior']['session_duration_modifier'])
            session_end_time = time.time() + (random.uniform(MIN_SESSION_DURATION, MAX_SESSION_DURATION) * session_duration_mod)

            while time.time() < session_end_time and time.time() < master_end_time:
                autopilot.step()
                time.sleep(random.uniform(0.5, 2.5))

            # Record final state
            visit_counter.increment()
            logging.info(f"Thread {thread_id}: Session for {url} finished. Total visits: {visit_counter.get()}")

        except TimeoutException:
            logging.warning(f"Thread {thread_id}: Page load timed out for {url} (proxy: {proxy})")
        except WebDriverException as e:
            # FIX: Improved handling for common proxy errors
            error_str = str(e).lower()
            if "err_proxy_connection_failed" in error_str or "timed out receiving message from renderer" in error_str:
                logging.warning(f"Thread {thread_id}: Proxy {proxy} failed to connect for {url}. Aborting session.")
            else:
                logging.error(f"Thread {thread_id}: WebDriver error during session: {str(e).splitlines()[0]}")
        except Exception as e:
            logging.error(f"Thread {thread_id}: An unexpected error occurred: {e}", exc_info=True)

    finally:
        if driver:
            driver.quit()

# --- NeuroThreadManager ---

class VisitCounter:
    """A simple thread-safe counter for tracking visits."""
    def __init__(self):
        self.count = 0
        self.lock = threading.Lock()

    def increment(self):
        with self.lock:
            self.count += 1

    def get(self):
        with self.lock:
            return self.count

class NeuroThreadManager:
    def __init__(self, urls, proxies, max_threads):
        self.urls = urls
        self.proxies = proxies
        self.max_threads = max_threads
        self.visit_counter = VisitCounter()
        self.active_threads = []

    def start_sessions(self, run_duration_hours):
        master_end_time = time.time() + (run_duration_hours * 3600)
        logging.info(f"Starting NeuroBot. Target run duration: {run_duration_hours} hours. Ending at: {datetime.fromtimestamp(master_end_time).isoformat()}")

        thread_id = 0
        while time.time() < master_end_time and self.visit_counter.get() < DAILY_VISIT_QUOTA:
            # Clean up finished threads
            self.active_threads = [t for t in self.active_threads if t.is_alive()]

            if len(self.active_threads) < self.max_threads:
                url = random.choice(self.urls)
                proxy = random.choice(self.proxies)

                thread = threading.Thread(target=visit_blog, args=(
                    thread_id, url, proxy, master_end_time, self.visit_counter, DAILY_VISIT_QUOTA
                ))
                self.active_threads.append(thread)
                thread.start()
                thread_id += 1

            time.sleep(1) # Wait before checking again

        logging.info("Master time limit or daily quota reached. Waiting for active threads to finish...")
        for t in self.active_threads:
            if t.is_alive():
                t.join(timeout=60) # Wait for remaining threads to finish

        logging.info(f"NeuroBot finished. Total visits completed: {self.visit_counter.get()}")

# --- Main Execution Block ---

if __name__ == "__main__":
    check_and_create_files()

    urls_to_visit = get_url_list()
    proxies_to_use = get_proxy_list()

    if not urls_to_visit:
        logging.error("No URLs found. Please add URLs to urls.txt.")
        sys.exit(1)

    if not proxies_to_use:
        logging.error("No proxies found. Please add proxies to proxies.txt.")
        sys.exit(1)

    # Set the total run duration for the bot (e.g., 24 hours)
    TOTAL_RUN_DURATION_HOURS = 24

    manager = NeuroThreadManager(urls_to_visit, proxies_to_use, MAX_THREADS_DEFAULT)
    manager.start_sessions(TOTAL_RUN_DURATION_HOURS)