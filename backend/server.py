from fastapi import FastAPI, APIRouter, HTTPException, Body
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone
import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from xml.dom import minidom
import re
import json
from playwright.async_api import async_playwright
import asyncio
import time
import sys

# Windows-spezifische Event Loop Policy für Playwright
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI(title="Adult Media Metadata Scraper for Emby")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Models
class MovieMetadata(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source: str  # gaydvdempire, aebn, gevi
    source_id: str
    title: str
    original_title: Optional[str] = None
    year: Optional[int] = None
    release_date: Optional[str] = None
    plot: Optional[str] = None
    runtime: Optional[int] = None
    studio: Optional[str] = None
    director: Optional[str] = None
    genres: List[str] = []
    actors: List[Dict[str, str]] = []  # [{"name": "...", "role": "..."}]
    tags: List[str] = []
    poster_url: Optional[str] = None
    backdrop_url: Optional[str] = None
    rating: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ScrapeRequest(BaseModel):
    source: str  # gaydvdempire, aebn, gevi
    movie_id: str

class SearchRequest(BaseModel):
    source: str
    query: str

class NFOGenerateRequest(BaseModel):
    metadata: Dict[str, Any]
    output_path: Optional[str] = None

# Scraper Classes
class GayDVDEmpireScraper:
    BASE_URL = "https://www.gaydvdempire.com"
    
    @staticmethod
    async def search_movie(query: str) -> List[Dict[str, Any]]:
        """Search for movies on Gay DVD Empire - Hybrid approach using Playwright for cookies and requests for content"""
        try:
            logger.info(f"Searching Gay DVD Empire for: {query}")
            
            # Step 1: Use Playwright to accept age gate and get cookies
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                )
                page = await context.new_page()
                
                # Visit homepage and accept age gate
                await page.goto(GayDVDEmpireScraper.BASE_URL, wait_until='domcontentloaded', timeout=30000)
                await page.wait_for_timeout(1000)
                
                # Check for age gate and click
                try:
                    if 'AgeConfirmation' in page.url or await page.locator('button').count() > 0:
                        await page.click('button')
                        await page.wait_for_timeout(2000)
                        logger.info("Age gate accepted")
                except:
                    pass
                
                # Get cookies after age gate
                cookies = await context.cookies()
                await browser.close()
                
                # Convert to requests format
                session_cookies = {c['name']: c['value'] for c in cookies}
            
            # Step 2: Use requests with cookies to get search results
            search_url = f"{GayDVDEmpireScraper.BASE_URL}/allsearch/search?q={query.replace(' ', '+')}"
            logger.info(f"Fetching search results from: {search_url}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': GayDVDEmpireScraper.BASE_URL
            }
            
            response = requests.get(search_url, headers=headers, cookies=session_cookies, timeout=30)
            
            if response.status_code != 200:
                logger.error(f"Search request failed with status {response.status_code}")
                return []
            
            # Step 3: Parse HTML with BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')
            results = []
            
            # Find all grid-item divs (grid view format)
            grid_items = soup.find_all('div', class_='grid-item')
            logger.info(f"Found {len(grid_items)} grid-item results")
            
            seen_ids = set()
            for item in grid_items[:15]:  # Process up to 15 items
                try:
                    # Find the product card inside the grid item
                    product_card = item.find('div', class_='product-card')
                    if not product_card:
                        continue
                    
                    # Extract movie ID from card id (format: "card2646442")
                    card_id = product_card.get('id', '')
                    movie_id = card_id.replace('card', '') if card_id.startswith('card') else None
                    
                    # Find the title link in product-details__item-title
                    title_container = item.find('div', class_='product-details__item-title')
                    if not title_container:
                        continue
                    
                    title_link = title_container.find('a')
                    if not title_link:
                        continue
                    
                    # Extract title and URL
                    title = title_link.get('title') or title_link.get_text(strip=True)
                    href = title_link.get('href', '')
                    
                    # If we didn't get movie_id from card, extract from href
                    if not movie_id and href:
                        id_match = re.search(r'/(\d+)/', href)
                        if id_match:
                            movie_id = id_match.group(1)
                    
                    # Skip duplicates and invalid entries
                    if not movie_id or not title or movie_id in seen_ids:
                        continue
                    
                    seen_ids.add(movie_id)
                    
                    # Build full URL
                    full_url = f"{GayDVDEmpireScraper.BASE_URL}{href}" if not href.startswith('http') else href
                    
                    result = {
                        'id': movie_id,
                        'title': title,
                        'url': full_url
                    }
                    
                    # Try to extract poster image
                    boxcover = item.find('div', class_='boxcover-container')
                    if boxcover:
                        img_tag = boxcover.find('img')
                        if img_tag:
                            poster_url = img_tag.get('data-src') or img_tag.get('src')
                            if poster_url and 'blank' not in poster_url:
                                result['poster_url'] = poster_url
                    
                    results.append(result)
                    
                    if len(results) >= 10:
                        break
                        
                except Exception as e:
                    logger.warning(f"Error parsing grid item: {str(e)}")
                    continue
            
            logger.info(f"Gay DVD Empire search found {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Error searching Gay DVD Empire: {str(e)}", exc_info=True)
            return []

    
    @staticmethod
    async def scrape_movie(movie_id_or_url: str) -> Dict[str, Any]:
        """Scrape movie metadata from Gay DVD Empire using Playwright to bypass age gate
        
        Args:
            movie_id_or_url: Either movie ID (e.g., '1668727') or full URL
        """
        # Determine if input is URL or movie_id
        if movie_id_or_url.startswith('http'):
            url = movie_id_or_url
            # Extract ID from URL for metadata
            # URL format: https://www.gaydvdempire.com/1668727/title/
            id_match = re.search(r'/(\d+)/', movie_id_or_url)
            if id_match:
                movie_id = id_match.group(1)
            else:
                # Fallback: try to get from end of URL
                movie_id = movie_id_or_url.rstrip('/').split('/')[-2] if movie_id_or_url.rstrip('/').split('/')[-1] else movie_id_or_url.rstrip('/').split('/')[-1]
        else:
            movie_id = movie_id_or_url
            url = f"{GayDVDEmpireScraper.BASE_URL}/{movie_id}/"
        
        try:
            logger.info(f"Scraping Gay DVD Empire movie: {url}")
            
            async with async_playwright() as p:
                # Launch browser with enhanced anti-detection
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage',
                        '--no-sandbox'
                    ]
                )
                context = await browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    viewport={'width': 1920, 'height': 1080},
                    locale='en-US',
                    timezone_id='America/New_York',
                    extra_http_headers={
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.9',
                        'Accept-Encoding': 'gzip, deflate, br',
                        'DNT': '1',
                        'Connection': 'keep-alive',
                        'Upgrade-Insecure-Requests': '1'
                    }
                )
                
                # Add JavaScript to mask automation
                page = await context.new_page()
                await page.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                """)
                
                # First, visit the homepage to establish a normal session
                logger.info("Establishing session by visiting homepage...")
                await page.goto(GayDVDEmpireScraper.BASE_URL, wait_until='domcontentloaded', timeout=30000)
                await page.wait_for_timeout(1000 + int(__import__('random').random() * 1000))
                
                # Navigate to the movie page (will redirect to age gate)
                logger.info(f"Navigating to movie page: {url}")
                response = await page.goto(url, wait_until='domcontentloaded', timeout=30000)
                await page.wait_for_timeout(500 + int(__import__('random').random() * 500))
                
                # Check if we're on the age confirmation page
                if 'AgeConfirmation' in page.url:
                    logger.info("Age gate detected, accepting...")
                    # Wait for and click the age confirmation button
                    try:
                        await page.wait_for_selector('button', timeout=5000)
                        await page.wait_for_timeout(300 + int(__import__('random').random() * 300))
                        # Click the button with human-like delay
                        await page.click('button', delay=50 + int(__import__('random').random() * 50))
                        # Wait for cookies/session to be set
                        await page.wait_for_timeout(1500 + int(__import__('random').random() * 1000))
                        logger.info("Age confirmation accepted")
                        
                        # Now navigate to the movie page again with the age cookie set
                        await page.goto(url, wait_until='load', timeout=40000)
                        logger.info(f"Second navigation completed: {page.url}")
                        
                        # Check if we're still on age gate (shouldn't be)
                        if 'AgeConfirmation' in page.url:
                            logger.error("Still on age gate after bypass attempt")
                            await browser.close()
                            raise HTTPException(status_code=500, detail="Age gate bypass failed - still on confirmation page")
                    except Exception as e:
                        logger.error(f"Failed to bypass age gate: {str(e)}")
                        await browser.close()
                        raise HTTPException(status_code=500, detail=f"Age gate bypass failed: {str(e)}")
                
                # Wait for the title element to be loaded
                try:
                    await page.wait_for_selector('h1', timeout=10000)
                    logger.info("Page content loaded")
                except:
                    logger.warning("Title element not found, continuing anyway")
                
                # Wait a bit more for any dynamic content
                await page.wait_for_timeout(3000)
                
                # Get the HTML content
                html_content = await page.content()
                await browser.close()
                
                # Parse with BeautifulSoup
                soup = BeautifulSoup(html_content, 'html.parser')
                
                metadata = {
                    'source': 'gaydvdempire',
                    'source_id': movie_id,
                    'title': '',
                    'year': None,
                    'plot': '',
                    'runtime': None,
                    'studio': '',
                    'director': '',
                    'genres': [],
                    'actors': [],
                    'tags': [],
                    'poster_url': '',
                    'release_date': ''
                }
                
                # Extract title - using correct selector for logged-out page
                title_elem = soup.select_one('h1.movie-page__heading__title')
                if title_elem:
                    title_text = title_elem.get_text(strip=True)
                    # Clean up title by removing sale text
                    title_text = re.sub(r'-\s*On Sale!.*$', '', title_text, flags=re.IGNORECASE)
                    title_text = re.sub(r'\s*Pre-Black Friday.*$', '', title_text, flags=re.IGNORECASE)
                    metadata['title'] = title_text.strip()
                
                # Extract year and studio from movie info section
                movie_info = soup.select_one('div.movie-page__heading__movie-info')
                if movie_info:
                    # Studio is the link in movie info
                    studio_elem = movie_info.find('a')
                    if studio_elem:
                        metadata['studio'] = studio_elem.get_text(strip=True)
                    
                    # Year is in the small tag
                    year_elem = movie_info.find('small')
                    if year_elem:
                        year_text = year_elem.get_text(strip=True)
                        year_match = re.search(r'(\d{4})', year_text)
                        if year_match:
                            metadata['year'] = int(year_match.group(1))
                
                # Extract poster image from Boxcover div
                poster_div = soup.select_one('div#Boxcover')
                if poster_div:
                    poster = poster_div.find('img')
                    if poster and poster.get('src'):
                        poster_url = poster['src']
                        if poster_url.startswith('//'):
                            poster_url = 'https:' + poster_url
                        elif poster_url.startswith('/'):
                            poster_url = GayDVDEmpireScraper.BASE_URL + poster_url
                        metadata['poster_url'] = poster_url
                
                # Extract plot from synopsis
                synopsis_div = soup.select_one('div.synopsis-content')
                if synopsis_div:
                    plot_elem = synopsis_div.find('p')
                    if plot_elem:
                        metadata['plot'] = plot_elem.get_text(strip=True)
                
                # Extract cast/performers
                performers_div = soup.select_one('div.movie-page__content-tags__performers')
                if performers_div:
                    cast_links = performers_div.find_all('a')
                    for actor_link in cast_links:
                        actor_name = actor_link.get_text(strip=True)
                        if actor_name:
                            metadata['actors'].append({
                                'name': actor_name,
                                'role': ''
                            })
                
                # Extract genres/categories
                categories_div = soup.select_one('div.movie-page__content-tags__categories')
                if categories_div:
                    category_links = categories_div.find_all('a')
                    for cat_link in category_links:
                        genre = cat_link.get_text(strip=True)
                        if genre and genre not in metadata['genres']:
                            metadata['genres'].append(genre)
                
                # Extract runtime from Product Information section (most accurate)
                # Look for "Length: X hrs. Y mins." pattern
                runtime_found = False
                all_text = soup.get_text()
                # Pattern: "1 hrs. 34 mins." or "94 mins."
                runtime_match = re.search(r'Length:\s*(?:(\d+)\s*hrs?\.)?\s*(\d+)\s*mins?\.', all_text, re.IGNORECASE)
                if runtime_match:
                    hours = int(runtime_match.group(1)) if runtime_match.group(1) else 0
                    minutes = int(runtime_match.group(2))
                    metadata['runtime'] = (hours * 60) + minutes
                    runtime_found = True
                    logger.info(f"Found runtime in Product Information: {metadata['runtime']} min ({hours}h {minutes}m)")
                
                # Fallback: sum all scene durations if Product Information not found
                if not runtime_found:
                    scene_durations = []
                    for span in soup.find_all('span', class_=''):
                        text = span.get_text(strip=True)
                        runtime_match = re.match(r'^(\d+)\s*min$', text)
                        if runtime_match:
                            scene_durations.append(int(runtime_match.group(1)))
                    
                    if scene_durations:
                        metadata['runtime'] = sum(scene_durations)
                        logger.info(f"Runtime from scenes: {len(scene_durations)} scenes, total: {metadata['runtime']} min")
                
                logger.info(f"Successfully scraped movie {movie_id} from Gay DVD Empire")
                logger.info(f"Scraped data: Title={metadata['title']}, Year={metadata['year']}, Studio={metadata['studio']}, Actors={len(metadata['actors'])}, Genres={len(metadata['genres'])}")
                return metadata
            
        except Exception as e:
            logger.error(f"Error scraping Gay DVD Empire movie {movie_id}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Scraping failed: {str(e)}")

class AEBNScraper:
    BASE_URL = "https://gay.aebn.com/gay/movies"
    
    @staticmethod
    async def search_movie(query: str) -> List[Dict[str, Any]]:
        """Search for movies on AEBN"""
        try:
            logger.info(f"Searching AEBN for: {query}")
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                )
                
                # Set age gate cookie
                await context.add_cookies([{
                    'name': 'AVS_COOKIE',
                    'value': 'yes',
                    'domain': '.aebn.com',
                    'path': '/'
                }])
                
                page = await context.new_page()
                
                # Navigate to search page
                search_url = f"https://gay.aebn.com/gay/search"
                await page.goto(search_url, wait_until='domcontentloaded', timeout=30000)
                
                # Fill search form
                await page.fill('input[name="criteria"]', query)
                await page.select_option('select[name="type"]', 'movie')
                await page.click('button[type="submit"], input[type="submit"]')
                
                await page.wait_for_timeout(3000)
                
                html = await page.content()
                await browser.close()
                
                soup = BeautifulSoup(html, 'html.parser')
                results = []
                
                # Find movie links
                for link in soup.find_all('a', href=re.compile(r'/gay/movies/\d+')):
                    result = {}
                    
                    # Get title from link text or nearby element
                    title = link.get_text(strip=True)
                    if not title:
                        # Try parent or sibling elements
                        parent = link.find_parent('div', class_='title') or link.find_parent('h3')
                        if parent:
                            title = parent.get_text(strip=True)
                    
                    if title:
                        result['title'] = title
                        
                        # Extract ID from URL
                        href = link.get('href')
                        id_match = re.search(r'/movies/(\d+)', href)
                        if id_match:
                            result['id'] = id_match.group(1)
                            result['url'] = f"https://gay.aebn.com{href}" if not href.startswith('http') else href
                            
                            results.append(result)
                            
                            if len(results) >= 10:
                                break
                
                logger.info(f"AEBN search found {len(results)} results")
                return results
                
        except Exception as e:
            logger.error(f"Error searching AEBN: {str(e)}")
            return []

    
    @staticmethod
    async def scrape_movie(movie_id_or_url: str) -> Dict[str, Any]:
        """Scrape movie metadata from AEBN using Playwright
        
        Args:
            movie_id_or_url: Either movie ID (e.g., '172181') or full URL
        """
        # Determine if input is URL or movie_id
        if movie_id_or_url.startswith('http'):
            url = movie_id_or_url
            # Extract ID from URL for metadata
            # URL format: https://gay.aebn.com/gay/movies/172181/title
            movie_id = movie_id_or_url.split('/movies/')[-1].split('/')[0]
        else:
            movie_id = movie_id_or_url
            url = f"{AEBNScraper.BASE_URL}/{movie_id}"
        
        try:
            logger.info(f"Scraping AEBN movie: {url}")
            
            async with async_playwright() as p:
                # Launch browser with anti-detection
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage',
                        '--no-sandbox'
                    ]
                )
                
                # Create context with cookies to bypass age gate
                context = await browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    viewport={'width': 1920, 'height': 1080}
                )
                
                page = await context.new_page()
                
                # Navigate to the movie page
                await page.goto(url, wait_until='domcontentloaded', timeout=40000)
                logger.info(f"Navigated to: {page.url}")
                
                # Check if we hit the age gate
                if 'avs/gate' in page.url or 'age' in page.url.lower():
                    logger.info("Age gate detected, attempting to bypass...")
                    
                    # Try to find and click the "Enter" or confirmation button
                    try:
                        # Look for common age gate button selectors
                        enter_button = None
                        
                        # Try different selectors for the enter button
                        selectors = [
                            'a:has-text("Enter")',
                            'button:has-text("Enter")',
                            'a:has-text("I am 18")',
                            'button:has-text("I am 18")',
                            'a[href*="verified"]',
                            'button[type="submit"]',
                            '.btn-enter',
                            '.enter-button'
                        ]
                        
                        for selector in selectors:
                            try:
                                if await page.locator(selector).count() > 0:
                                    enter_button = page.locator(selector).first
                                    logger.info(f"Found age gate button with selector: {selector}")
                                    break
                            except:
                                continue
                        
                        if enter_button:
                            await enter_button.click()
                            logger.info("Clicked age gate button")
                            await page.wait_for_load_state('networkidle', timeout=20000)
                            logger.info(f"After clicking, navigated to: {page.url}")
                        else:
                            logger.warning("Could not find age gate button, trying direct navigation")
                            # If no button found, try to navigate directly with verified parameter
                            verified_url = url + "?avs=verified"
                            await page.goto(verified_url, wait_until='networkidle', timeout=40000)
                            logger.info(f"Direct navigation to: {page.url}")
                    except Exception as gate_error:
                        logger.warning(f"Error handling age gate: {str(gate_error)}")
                
                # Wait for the content to load
                await page.wait_for_timeout(3000)
                
                # Get the page HTML
                html_content = await page.content()
                soup = BeautifulSoup(html_content, 'html.parser')
                
                await browser.close()
            
            metadata = {
                'source': 'aebn',
                'source_id': movie_id,
                'title': '',
                'year': None,
                'plot': '',
                'runtime': None,
                'studio': '',
                'director': '',
                'genres': [],
                'actors': [],
                'tags': [],
                'poster_url': '',
                'release_date': ''
            }
            
            # Extract title from main heading (skip noscript messages)
            title_elems = soup.find_all('h1')
            for title_elem in title_elems:
                title_text = title_elem.get_text(strip=True)
                # Skip noscript error messages
                if title_text and 'javascript' not in title_text.lower() and 'needs more' not in title_text.lower():
                    metadata['title'] = title_text
                    logger.info(f"Title: {metadata['title']}")
                    break
            
            # Extract poster from boxcover image
            poster_img = soup.find('img', alt=re.compile(r'Adult Movie.*front box cover'))
            if poster_img and poster_img.get('src'):
                poster_url = poster_img['src']
                if poster_url.startswith('//'):
                    poster_url = 'https:' + poster_url
                # Remove query parameters for cleaner URL
                poster_url = poster_url.split('?')[0]
                metadata['poster_url'] = poster_url
                logger.info(f"Poster URL: {metadata['poster_url']}")
            
            # Extract description
            description_div = soup.find('div', class_='dts-section-page-detail-description-body')
            if description_div:
                metadata['plot'] = description_div.get_text(strip=True)
                logger.info(f"Plot length: {len(metadata['plot'])} chars")
            
            # Extract metadata from list attributes
            info_list = soup.find('ul', class_='section-detail')
            if not info_list:
                info_list = soup.find('div', class_='section-detail')
            
            if info_list:
                list_items = info_list.find_all('li')
                for item in list_items:
                    item_text = item.get_text(strip=True)
                    
                    # Studio
                    if 'Studio:' in item_text:
                        studio_link = item.find('a')
                        if studio_link:
                            metadata['studio'] = studio_link.get_text(strip=True)
                            logger.info(f"Studio: {metadata['studio']}")
                    
                    # Running Time
                    elif 'Running Time:' in item_text:
                        runtime_match = re.search(r'(\d{2}):(\d{2}):(\d{2})', item_text)
                        if runtime_match:
                            hours = int(runtime_match.group(1))
                            minutes = int(runtime_match.group(2))
                            seconds = int(runtime_match.group(3))
                            metadata['runtime'] = hours * 60 + minutes
                            logger.info(f"Runtime: {metadata['runtime']} minutes")
                    
                    # Release date
                    elif 'Released:' in item_text:
                        date_text = item_text.replace('Released:', '').strip()
                        metadata['release_date'] = date_text
                        # Extract year
                        year_match = re.search(r'(\d{4})', date_text)
                        if year_match:
                            metadata['year'] = int(year_match.group(1))
                            logger.info(f"Year: {metadata['year']}")
                    
                    # Directors
                    elif 'Director' in item_text:
                        director_links = item.find_all('a')
                        directors = [link.get_text(strip=True) for link in director_links if link.get_text(strip=True)]
                        # Join and clean up any double commas
                        metadata['director'] = ', '.join(directors).replace(',,', ',').strip(', ')
                        logger.info(f"Directors: {metadata['director']}")
            
            # Extract categories/genres
            categories_div = soup.find('div', class_='dts-detail-movie-categories-content')
            if categories_div:
                category_links = categories_div.find_all('a')
                for link in category_links:
                    genre = link.get_text(strip=True)
                    if genre and genre not in metadata['genres']:
                        metadata['genres'].append(genre)
                logger.info(f"Genres: {metadata['genres']}")
            
            # Extract actors/stars from the movie detail section
            stars_section = soup.find('div', class_='dts-detail-movie-stars-label')
            if stars_section:
                # Find the parent container
                stars_container = stars_section.find_parent('div', class_='dts-hide-queue-scrollbars')
                if stars_container:
                    actor_links = stars_container.find_all('a', href=re.compile(r'/gay/stars/'))
                    for link in actor_links:
                        actor_name = link.get_text(strip=True)
                        if actor_name:
                            metadata['actors'].append({
                                'name': actor_name,
                                'role': ''
                            })
                    logger.info(f"Actors: {[a['name'] for a in metadata['actors']]}")
            
            # Validate that we actually got movie data (not an error page or empty result)
            if not metadata['title'] or 'not found' in metadata['title'].lower() or 'error' in metadata['title'].lower():
                logger.error(f"Movie {movie_id} not found on AEBN or returned error page")
                raise HTTPException(status_code=404, detail=f"Movie {movie_id} not found on AEBN")
            
            logger.info(f"Successfully scraped movie {movie_id} from AEBN")
            return metadata
            
        except HTTPException:
            # Re-raise HTTP exceptions as-is
            raise
        except Exception as e:
            logger.error(f"Error scraping AEBN movie {movie_id}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Scraping failed: {str(e)}")

class GEVIScraper:
    BASE_URL = "https://gayeroticvideoindex.com"
    
    @staticmethod
    async def search_movie(query: str) -> List[Dict[str, Any]]:
        """Search for movies on GEVI using Playwright
        
        Uses Playwright to handle JavaScript rendering and age gate
        GEVI's search is NOT working via DataTables - returns empty results
        This is a known issue and we'll disable GEVI search for now
        """
        try:
            logger.warning(f"GEVI search is currently not functional due to DataTables AJAX loading issues")
            logger.warning(f"Attempted search query: {query}")
            logger.warning("Please use GEVI scraper with direct video IDs instead")
            # Return empty results with a message
            return []
                
        except Exception as e:
            logger.error(f"Error searching GEVI: {str(e)}")
            return []
    
    @staticmethod
    async def scrape_movie(movie_id_or_url: str) -> Dict[str, Any]:
        """Scrape movie metadata from GEVI using Playwright for JavaScript rendering
        
        Args:
            movie_id_or_url: Either movie ID (e.g., '48797') or full URL
        """
        # Determine if input is URL or movie_id
        if movie_id_or_url.startswith('http'):
            url = movie_id_or_url
            # Extract ID from URL for metadata
            movie_id = movie_id_or_url.split('/video/')[-1].split('/')[0].split('.')[0]
        else:
            movie_id = movie_id_or_url
            url = f"{GEVIScraper.BASE_URL}/video/{movie_id}"
        
        try:
            logger.info(f"Scraping GEVI movie: {url}")
            
            async with async_playwright() as p:
                # Launch browser with anti-detection
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage',
                        '--no-sandbox'
                    ]
                )
                context = await browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    viewport={'width': 1920, 'height': 1080}
                )
                
                page = await context.new_page()
                
                # Set localStorage to bypass age gate (like clicking "Enter" button)
                await page.goto(GEVIScraper.BASE_URL, wait_until='domcontentloaded', timeout=30000)
                
                # Set the "entered" localStorage item with expiry (2 days from now)
                await page.evaluate("""
                    () => {
                        let date = new Date();
                        localStorage.setItem("entered", JSON.stringify(date.getTime() + 24 * 60 * 60 * 2 * 1000));
                    }
                """)
                logger.info("Age gate bypassed via localStorage")
                
                # Now navigate to the movie page
                await page.goto(url, wait_until='networkidle', timeout=40000)
                logger.info(f"Navigated to: {page.url}")
                
                # Wait for the main data section to be visible (not hidden)
                try:
                    await page.wait_for_selector('section#data:not(.hidden)', timeout=10000)
                    logger.info("Main data section loaded")
                except:
                    logger.warning("Data section not found or still hidden")
                
                # Wait for content to load
                await page.wait_for_timeout(3000)
                
                # Get HTML content
                html_content = await page.content()
                await browser.close()
                
                # Parse with BeautifulSoup
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # Only parse from the #data section (ignore hidden elements)
                data_section = soup.find('section', id='data')
                if not data_section:
                    logger.error("Could not find data section")
                    await browser.close()
                    raise HTTPException(status_code=500, detail="Could not parse movie page")
                
                metadata = {
                    'source': 'gevi',
                    'source_id': movie_id,
                    'title': '',
                    'year': None,
                    'plot': '',
                    'runtime': None,
                    'studio': '',
                    'director': '',
                    'genres': [],
                    'actors': [],
                    'tags': [],
                    'poster_url': '',
                    'release_date': ''
                }
                
                # Extract title (h1 with yellow text) from data section
                title_elem = data_section.find('h1', class_='text-yellow-300')
                if title_elem:
                    metadata['title'] = title_elem.get_text(strip=True)
                    logger.info(f"Title: {metadata['title']}")
                
                # Extract year and studio from table
                table = data_section.find('table')
                if table:
                    rows = table.find_all('tr')
                    for row in rows:
                        cells = row.find_all('td')
                        if len(cells) >= 2:
                            # Distributor (first column)
                            distributor = cells[0].get_text(strip=True)
                            if distributor and not metadata['studio']:
                                metadata['studio'] = distributor
                            
                            # Released year (second column)
                            year_text = cells[1].get_text(strip=True)
                            year_match = re.search(r'(\d{4})', year_text)
                            if year_match:
                                metadata['year'] = int(year_match.group(1))
                                metadata['release_date'] = year_text
                
                # Extract poster/cover image (try to get full-size, not thumbnail)
                cover_img = data_section.select_one('#coverContainer img')
                if cover_img:
                    # Try to get the largest available image
                    # Check for data-src, data-original, or href attributes first
                    poster_url = cover_img.get('data-src') or cover_img.get('data-original') or cover_img.get('src', '')
                    
                    # Also check if there's a parent link with a larger image
                    parent_link = cover_img.find_parent('a')
                    if parent_link and parent_link.get('href'):
                        link_href = parent_link.get('href')
                        # If the link points to an image, use that instead
                        if any(ext in link_href.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                            poster_url = link_href
                    
                    if poster_url:
                        # Convert thumbnail URL to full-size by removing size parameters
                        # e.g., image_thumb.jpg -> image.jpg or image-small.jpg -> image.jpg
                        poster_url = poster_url.replace('_thumb', '').replace('-thumb', '').replace('_small', '').replace('-small', '')
                        
                        # For GEVI: Replace /Covers/Icons/ with /Covers/ to get full-size image
                        poster_url = poster_url.replace('/Covers/Icons/', '/Covers/')
                        
                        if poster_url.startswith('//'):
                            poster_url = 'https:' + poster_url
                        elif not poster_url.startswith('http'):
                            # Relative URL - add base
                            poster_url = GEVIScraper.BASE_URL + '/' + poster_url.lstrip('/')
                        metadata['poster_url'] = poster_url
                        logger.info(f"Poster: {poster_url}")
                
                # Extract description
                desc_divs = data_section.find_all('div', class_='text-justify')
                for div in desc_divs:
                    text = div.get_text(strip=True)
                    # Look for description (usually longer text with "Description source:")
                    if len(text) > 100 and 'Description source:' not in text:
                        # Remove "Description source:" part if present
                        parts = text.split('Description source:')
                        if len(parts) > 1:
                            metadata['plot'] = parts[1].strip()
                        else:
                            metadata['plot'] = text
                        break
                
                # Extract additional info from grid
                grid_divs = data_section.find_all('div', class_='grid')
                for grid in grid_divs:
                    text = grid.get_text()
                    
                    # Extract studio (additional field)
                    if 'Studio:' in text:
                        lines = text.split('\n')
                        for i, line in enumerate(lines):
                            if 'Studio:' in line and i + 1 < len(lines):
                                studio_text = lines[i + 1].strip()
                                if studio_text and studio_text != 'various':
                                    metadata['studio'] = studio_text
                    
                    # Extract category as genre
                    if 'Category:' in text:
                        lines = text.split('\n')
                        for i, line in enumerate(lines):
                            if 'Category:' in line and i + 1 < len(lines):
                                category = lines[i + 1].strip()
                                if category and category not in metadata['genres']:
                                    metadata['genres'].append(category)
                
                # Extract directors - find the "Director:" label, then get links from next sibling
                # Structure: <div class="text-yellow-200 pr-2">Director:</div>
                #            <div class="flex flex-col"><a href='director/...'>Name</a>...</div>
                director_label = None
                for div in data_section.find_all('div', class_='text-yellow-200'):
                    if 'Director:' in div.get_text(strip=True):
                        director_label = div
                        break
                
                if director_label:
                    # Get the next sibling div
                    director_container = director_label.find_next_sibling('div')
                    if director_container:
                        # Find all director links in this specific container
                        # Note: href might be 'director/123' or '/director/123'
                        director_links = director_container.find_all('a', href=re.compile(r'director/'))
                        directors = []
                        for link in director_links:
                            director_name = link.get_text(strip=True)
                            if director_name:
                                directors.append(director_name)
                        if directors:
                            metadata['director'] = ', '.join(directors)
                            logger.info(f"Directors: {metadata['director']}")
                
                # Extract cast - find all performer links
                actor_links = data_section.find_all('a', href=re.compile(r'/performer/'))
                seen_actors = set()
                for actor_link in actor_links:
                    actor_name = actor_link.get_text(strip=True)
                    if actor_name and actor_name not in seen_actors:
                        seen_actors.add(actor_name)
                        metadata['actors'].append({
                            'name': actor_name,
                            'role': ''
                        })
                logger.info(f"Found {len(metadata['actors'])} actors")
                
                logger.info(f"Successfully scraped movie {movie_id} from GEVI")
                return metadata
            
        except Exception as e:
            logger.error(f"Error scraping GEVI movie {movie_id}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Scraping failed: {str(e)}")

class RadVideoScraper:
    BASE_URL = "https://www.radvideo.com"
    
    
    @staticmethod
    def search_movie(query: str) -> List[Dict[str, Any]]:
        """Search for movies on RadVideo"""
        import requests
        from bs4 import BeautifulSoup
        
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        try:
            # RadVideo search URL
            search_url = f"{RadVideoScraper.BASE_URL}/catalogsearch/result/"
            response = session.get(search_url, params={'q': query}, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            results = []
            
            # Find product links (format: /product-name.html)
            product_links = soup.find_all('a', class_='product-item-link')
            
            for link in product_links[:10]:  # Limit to 10 results
                result = {}
                
                # Get title
                result['title'] = link.get_text(strip=True)
                
                # Get URL
                href = link.get('href', '')
                if href:
                    result['url'] = href
                    # Extract ID/slug from URL (e.g., /twinks-on-all-4-s-dvd.html)
                    if href.endswith('.html'):
                        slug = href.rstrip('/').split('/')[-1].replace('.html', '')
                        result['id'] = slug
                
                if result.get('title') and result.get('id'):
                    results.append(result)
            
            logger.info(f"RadVideo search for '{query}' found {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Error searching RadVideo: {str(e)}")
            return []

    @staticmethod
    async def scrape_movie(movie_id_or_url: str) -> Dict[str, Any]:
        """Scrape movie metadata from RadVideo using Playwright
        
        Args:
            movie_id_or_url: Either movie slug (e.g., 'twinks-on-all-4-s-dvd') or full URL
        """
        # Determine if input is URL or movie_id
        if movie_id_or_url.startswith('http'):
            url = movie_id_or_url
        else:
            url = f"{RadVideoScraper.BASE_URL}/{movie_id_or_url}.html"
        
        try:
            logger.info(f"Scraping RadVideo movie: {url}")
            
            async with async_playwright() as p:
                # Launch browser with anti-detection
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage',
                        '--no-sandbox'
                    ]
                )
                
                context = await browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    viewport={'width': 1920, 'height': 1080}
                )
                
                page = await context.new_page()
                
                # Navigate to the movie page
                await page.goto(url, wait_until='domcontentloaded', timeout=40000)
                logger.info(f"Navigated to: {page.url}")
                
                # Check if we hit the age gate
                if 'enter-splash' in await page.content() or await page.locator('.enter-splash').count() > 0:
                    logger.info("Age gate detected, attempting to bypass...")
                    
                    try:
                        # Click the "Enter website" button
                        enter_button = page.locator('.btn-enter-site').first
                        if await enter_button.count() > 0:
                            await enter_button.click()
                            logger.info("Clicked age gate enter button")
                            await page.wait_for_load_state('networkidle', timeout=20000)
                            logger.info(f"After clicking, navigated to: {page.url}")
                    except Exception as gate_error:
                        logger.warning(f"Error handling age gate: {str(gate_error)}")
                
                # Wait for the content to load
                await page.wait_for_timeout(3000)
                
                # Get the page HTML
                html_content = await page.content()
                soup = BeautifulSoup(html_content, 'html.parser')
                
                await browser.close()
            
            metadata = {
                'source': 'radvideo',
                'source_id': movie_id_or_url,
                'title': '',
                'year': None,
                'plot': '',
                'runtime': None,
                'studio': '',
                'director': '',
                'genres': [],
                'actors': [],
                'tags': [],
                'poster_url': '',
                'release_date': ''
            }
            
            # Extract title
            title_elem = soup.find('h1', class_='page-title')
            if title_elem:
                title_span = title_elem.find('span', class_='base')
                if title_span:
                    metadata['title'] = title_span.get_text(strip=True)
                    logger.info(f"Title: {metadata['title']}")
            
            # Extract poster image
            poster_img = soup.find('img', class_='gallery-placeholder__image')
            if poster_img and poster_img.get('src'):
                poster_url = poster_img['src']
                if poster_url.startswith('//'):
                    poster_url = 'https:' + poster_url
                metadata['poster_url'] = poster_url
                logger.info(f"Poster: {metadata['poster_url']}")
            
            # Extract description/plot
            # Structure: <div class="product attribute product-attribute overview">
            #              <span class="value" itemprop="description"><p>text</p></span>
            #            </div>
            description_div = soup.find('div', class_='overview')
            
            if description_div:
                # Find span with class="value" and itemprop="description"
                value_span = description_div.find('span', class_='value', itemprop='description')
                if value_span:
                    # Get text from paragraph inside
                    p_tag = value_span.find('p')
                    if p_tag:
                        metadata['plot'] = p_tag.get_text(strip=True)
                        logger.info(f"Plot extracted from <p> tag, length: {len(metadata['plot'])} chars")
                    else:
                        # Fallback: get text directly from span
                        metadata['plot'] = value_span.get_text(strip=True)
                        logger.info(f"Plot extracted from <span>, length: {len(metadata['plot'])} chars")
                else:
                    # Last resort: get all text from div
                    metadata['plot'] = description_div.get_text(strip=True)
                    logger.info(f"Plot extracted from <div>, length: {len(metadata['plot'])} chars")
            
            # Extract metadata from additional-attributes section
            attributes_section = soup.find('div', class_='additional-attributes')
            if attributes_section:
                items = attributes_section.find_all('div', class_='item')
                
                for item in items:
                    dt = item.find('dt')
                    dd = item.find('dd')
                    
                    if dt and dd:
                        label = dt.get_text(strip=True).lower()
                        
                        # Studio
                        if 'studio' in label:
                            studio_link = dd.find('a')
                            if studio_link:
                                metadata['studio'] = studio_link.get_text(strip=True)
                            else:
                                metadata['studio'] = dd.get_text(strip=True)
                            logger.info(f"Studio: {metadata['studio']}")
                        
                        # Director
                        elif 'director' in label:
                            metadata['director'] = dd.get_text(strip=True)
                            logger.info(f"Director: {metadata['director']}")
                        
                        # Release Date
                        elif 'release date' in label:
                            date_text = dd.get_text(strip=True)
                            metadata['release_date'] = date_text
                            # Extract year
                            year_match = re.search(r'(\d{4})', date_text)
                            if year_match:
                                metadata['year'] = int(year_match.group(1))
                                logger.info(f"Year: {metadata['year']}")
                        
                        # Runtime
                        elif 'run time' in label:
                            runtime_text = dd.get_text(strip=True)
                            runtime_match = re.search(r'(\d+)', runtime_text)
                            if runtime_match:
                                metadata['runtime'] = int(runtime_match.group(1))
                                logger.info(f"Runtime: {metadata['runtime']} minutes")
                        
                        # Actors
                        elif 'actors' in label:
                            actor_links = dd.find_all('a')
                            for link in actor_links:
                                actor_name = link.get_text(strip=True)
                                if actor_name:
                                    metadata['actors'].append({
                                        'name': actor_name,
                                        'role': ''
                                    })
                            logger.info(f"Actors: {[a['name'] for a in metadata['actors']]}")
            
            # Also try to extract studio from product-meta-data section
            if not metadata['studio']:
                meta_data = soup.find('div', class_='product-meta-data')
                if meta_data:
                    studio_link = meta_data.find('a')
                    if studio_link:
                        metadata['studio'] = studio_link.get_text(strip=True)
                        logger.info(f"Studio (from meta): {metadata['studio']}")
            
            # Extract genres/tags from product-icons (like "Bareback")
            product_icons = soup.find_all('span', class_=lambda x: x and x.startswith('dream-'))
            for icon in product_icons:
                genre = icon.get('title', '')
                if genre and genre not in metadata['genres']:
                    metadata['genres'].append(genre)
            
            if metadata['genres']:
                logger.info(f"Genres: {metadata['genres']}")
            
            # Validate that we got movie data
            if not metadata['title']:
                logger.error(f"Movie not found on RadVideo: {movie_id_or_url}")
                raise HTTPException(status_code=404, detail=f"Movie not found on RadVideo")
            
            logger.info(f"Successfully scraped movie from RadVideo")
            return metadata
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error scraping RadVideo movie: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Scraping failed: {str(e)}")

# Helper function to download images
def download_image(url: str, output_path: str) -> bool:
    """Download an image from URL and save it to output_path"""
    try:
        if not url:
            return False
        
        logger.info(f"Downloading image from: {url}")
        response = requests.get(url, timeout=30, stream=True)
        response.raise_for_status()
        
        # Save image
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        logger.info(f"Image saved to: {output_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to download image from {url}: {str(e)}")
        return False

# NFO Generator
class NFOGenerator:
    @staticmethod
    def generate_nfo(metadata: Dict[str, Any]) -> str:
        """Generate Emby-compatible NFO XML content"""
        
        movie = ET.Element('movie')
        
        # Add title
        if metadata.get('title'):
            title = ET.SubElement(movie, 'title')
            title.text = metadata['title']
            
            originaltitle = ET.SubElement(movie, 'originaltitle')
            originaltitle.text = metadata.get('original_title', metadata['title'])
        
        # Add year
        if metadata.get('year'):
            year = ET.SubElement(movie, 'year')
            year.text = str(metadata['year'])
        
        # Add release date
        if metadata.get('release_date'):
            premiered = ET.SubElement(movie, 'premiered')
            premiered.text = metadata['release_date']
        
        # Add plot
        if metadata.get('plot'):
            plot = ET.SubElement(movie, 'plot')
            plot.text = metadata['plot']
            
            outline = ET.SubElement(movie, 'outline')
            outline.text = metadata['plot'][:200] + '...' if len(metadata['plot']) > 200 else metadata['plot']
        
        # Add runtime
        if metadata.get('runtime'):
            runtime = ET.SubElement(movie, 'runtime')
            runtime.text = str(metadata['runtime'])
        
        # Add studio
        if metadata.get('studio'):
            studio = ET.SubElement(movie, 'studio')
            studio.text = metadata['studio']
        
        # Add director
        if metadata.get('director'):
            director = ET.SubElement(movie, 'director')
            director.text = metadata['director']
        
        # Add genres
        for genre in metadata.get('genres', []):
            genre_elem = ET.SubElement(movie, 'genre')
            genre_elem.text = genre
        
        # Add tags
        for tag in metadata.get('tags', []):
            tag_elem = ET.SubElement(movie, 'tag')
            tag_elem.text = tag
        
        # Add actors
        for actor_data in metadata.get('actors', []):
            actor = ET.SubElement(movie, 'actor')
            
            name = ET.SubElement(actor, 'name')
            name.text = actor_data.get('name', '')
            
            if actor_data.get('role'):
                role = ET.SubElement(actor, 'role')
                role.text = actor_data['role']
        
        # Add poster
        if metadata.get('poster_url'):
            thumb = ET.SubElement(movie, 'thumb')
            thumb.text = metadata['poster_url']
            
            poster = ET.SubElement(movie, 'poster')
            poster.text = metadata['poster_url']
        
        # Add backdrop/fanart
        if metadata.get('backdrop_url'):
            fanart = ET.SubElement(movie, 'fanart')
            fanart.text = metadata['backdrop_url']
        
        # Add rating
        if metadata.get('rating'):
            rating = ET.SubElement(movie, 'mpaa')
            rating.text = metadata['rating']
        
        # Add source information as tags
        source_tag = ET.SubElement(movie, 'tag')
        source_tag.text = f"Source: {metadata.get('source', 'unknown')}"
        
        id_tag = ET.SubElement(movie, 'tag')
        id_tag.text = f"SourceID: {metadata.get('source_id', '')}"
        
        # Pretty print XML
        xml_str = ET.tostring(movie, encoding='unicode')
        dom = minidom.parseString(xml_str)
        pretty_xml = dom.toprettyxml(indent='  ')
        
        # Remove extra blank lines
        pretty_xml = '\n'.join([line for line in pretty_xml.split('\n') if line.strip()])
        
        return pretty_xml

# API Routes
@api_router.get("/")
async def root():
    return {
        "message": "Adult Media Metadata Scraper API",
        "version": "1.0.0",
        "supported_sources": ["gaydvdempire", "aebn", "gevi", "radvideo"]
    }

@api_router.post("/scrape", response_model=MovieMetadata)
async def scrape_movie(request: ScrapeRequest):
    """
    Scrape movie metadata from specified source
    """
    try:
        source = request.source.lower()
        movie_id = request.movie_id
        
        if source == "gaydvdempire":
            metadata = await GayDVDEmpireScraper.scrape_movie(movie_id)
        elif source == "aebn":
            metadata = await AEBNScraper.scrape_movie(movie_id)
        elif source == "gevi":
            metadata = await GEVIScraper.scrape_movie(movie_id)
        elif source == "radvideo":
            metadata = await RadVideoScraper.scrape_movie(movie_id)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported source: {source}")
        
        # Save to database
        movie_obj = MovieMetadata(**metadata)
        doc = movie_obj.model_dump()
        doc['created_at'] = doc['created_at'].isoformat()
        await db.movies.insert_one(doc)
        
        return movie_obj
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in scrape endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/search")
async def search_movies(request: SearchRequest):
    """
    Search for movies on specified source
    """
    try:
        source = request.source.lower()
        query = request.query
        
        if source == "gevi":
            results = await GEVIScraper.search_movie(query)
        elif source == "gaydvdempire":
            results = await GayDVDEmpireScraper.search_movie(query)
        elif source == "aebn":
            results = await AEBNScraper.search_movie(query)
        elif source == "radvideo":
            results = RadVideoScraper.search_movie(query)
        else:
            return {"results": [], "message": f"Unknown source: {source}"}
        
        return {"results": results}
        
    except Exception as e:
        logger.error(f"Error in search endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/generate-nfo")
async def generate_nfo(request: NFOGenerateRequest):
    """
    Generate NFO file content from metadata and download images
    """
    try:
        metadata = request.metadata
        output_path = request.output_path
        
        # Generate NFO content
        nfo_content = NFOGenerator.generate_nfo(metadata)
        
        # Generate NFO filename with year (for Emby compatibility)
        nfo_title = metadata.get('title', 'movie').replace('/', '-').replace('\\', '-').replace(':', '-')
        if metadata.get('year'):
            nfo_filename = f"{nfo_title} ({metadata['year']}).nfo"
        else:
            nfo_filename = f"{nfo_title}.nfo"
        
        # Prepare response
        response = {
            "nfo_content": nfo_content,
            "filename": nfo_filename,
            "images_downloaded": []
        }
        
        # Download images if output_path is provided
        if output_path:
            output_path_obj = Path(output_path)
            
            # Check if output_path is a directory or a file path
            if output_path.endswith(('\\', '/')):
                # It's a directory path (ends with slash)
                output_dir = output_path_obj
                # Build title with year for Emby compatibility
                movie_title = metadata.get('title', 'movie').replace('/', '-').replace('\\', '-').replace(':', '-')
                if metadata.get('year'):
                    movie_title = f"{movie_title} ({metadata['year']})"
            elif output_path_obj.suffix in ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.mpg', '.mpeg']:
                # It's a video file path - use exact video filename
                output_dir = output_path_obj.parent
                movie_title = output_path_obj.stem  # Use video filename as-is (preserves year if present)
            else:
                # Assume it's a directory if no video extension
                output_dir = output_path_obj
                # Build title with year for Emby compatibility
                movie_title = metadata.get('title', 'movie').replace('/', '-').replace('\\', '-').replace(':', '-')
                if metadata.get('year'):
                    movie_title = f"{movie_title} ({metadata['year']})"
            
            logger.info(f"Output directory: {output_dir}")
            logger.info(f"Movie title for images: {movie_title}")
            
            # Download poster/cover
            if metadata.get('poster_url'):
                poster_path = output_dir / f"{movie_title}-poster.jpg"
                if download_image(metadata['poster_url'], str(poster_path)):
                    response["images_downloaded"].append(str(poster_path))
                    logger.info(f"Poster downloaded: {poster_path}")
            
            # Download thumb as fanart (if available and different from poster)
            if metadata.get('thumb_url') and metadata.get('thumb_url') != metadata.get('poster_url'):
                fanart_path = output_dir / f"{movie_title}-fanart.jpg"
                if download_image(metadata['thumb_url'], str(fanart_path)):
                    response["images_downloaded"].append(str(fanart_path))
                    logger.info(f"Fanart downloaded: {fanart_path}")
            
            # Also save the NFO file automatically
            nfo_file_path = output_dir / nfo_filename
            try:
                with open(nfo_file_path, 'w', encoding='utf-8') as f:
                    f.write(nfo_content)
                response["nfo_saved"] = str(nfo_file_path)
                logger.info(f"NFO file saved: {nfo_file_path}")
            except Exception as e:
                logger.error(f"Failed to save NFO file: {str(e)}")
                response["nfo_saved"] = None
        
        return response
        
    except Exception as e:
        logger.error(f"Error generating NFO: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/movies", response_model=List[MovieMetadata])
async def get_movies():
    """
    Get all scraped movies from database
    """
    try:
        movies = await db.movies.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
        
        # Convert ISO string timestamps back to datetime objects
        for movie in movies:
            if isinstance(movie.get('created_at'), str):
                movie['created_at'] = datetime.fromisoformat(movie['created_at'])
        
        return movies
        
    except Exception as e:
        logger.error(f"Error fetching movies: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.delete("/movies/{movie_id}")
async def delete_movie(movie_id: str):
    """
    Delete a movie from database
    """
    try:
        result = await db.movies.delete_one({"id": movie_id})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Movie not found")
        
        return {"message": "Movie deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting movie: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Folder Monitoring Endpoints
from folder_monitor import get_monitor_service

class MonitorConfigRequest(BaseModel):
    folder_path: Optional[str] = None
    preferred_source: Optional[str] = None
    auto_scrape_enabled: Optional[bool] = None

class ScanFolderRequest(BaseModel):
    folder_path: str

@api_router.get("/monitor/status")
async def get_monitor_status():
    """
    Get folder monitoring status
    """
    try:
        monitor = get_monitor_service(db)
        status = await monitor.get_status()
        return status
    except Exception as e:
        logger.error(f"Error getting monitor status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/monitor/start")
async def start_monitoring():
    """
    Start folder monitoring service
    """
    try:
        monitor = get_monitor_service(db)
        await monitor.start_monitoring()
        return {"message": "Monitoring started", "status": await monitor.get_status()}
    except Exception as e:
        logger.error(f"Error starting monitor: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/monitor/stop")
async def stop_monitoring():
    """
    Stop folder monitoring service
    """
    try:
        monitor = get_monitor_service(db)
        await monitor.stop_monitoring()
        return {"message": "Monitoring stopped"}
    except Exception as e:
        logger.error(f"Error stopping monitor: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/monitor/add-folder")
async def add_watched_folder(request: MonitorConfigRequest):
    """
    Add a folder to watch list
    """
    try:
        if not request.folder_path:
            raise HTTPException(status_code=400, detail="folder_path is required")
        
        monitor = get_monitor_service(db)
        success = await monitor.add_watched_folder(request.folder_path)
        
        if success:
            return {
                "message": "Folder added successfully",
                "folder": request.folder_path,
                "status": await monitor.get_status()
            }
        else:
            raise HTTPException(status_code=400, detail="Failed to add folder")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding folder: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.delete("/monitor/folder")
async def remove_watched_folder(request: MonitorConfigRequest):
    """
    Remove a folder from watch list
    """
    try:
        if not request.folder_path:
            raise HTTPException(status_code=400, detail="folder_path is required")
        
        monitor = get_monitor_service(db)
        success = await monitor.remove_watched_folder(request.folder_path)
        
        if success:
            return {"message": "Folder removed successfully"}
        else:
            raise HTTPException(status_code=404, detail="Folder not in watch list")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing folder: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/monitor/scan-folder")
async def scan_folder(request: ScanFolderRequest):
    """
    Manually scan a folder for videos without NFO files
    """
    try:
        monitor = get_monitor_service(db)
        files = await monitor.scan_existing_files(request.folder_path)
        
        return {
            "folder": request.folder_path,
            "files_without_nfo": files,
            "count": len(files)
        }
        
    except Exception as e:
        logger.error(f"Error scanning folder: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.put("/monitor/config")
async def update_monitor_config(request: MonitorConfigRequest):
    """
    Update monitor configuration
    """
    try:
        monitor = get_monitor_service(db)
        
        if request.preferred_source:
            monitor.preferred_source = request.preferred_source
        
        if request.auto_scrape_enabled is not None:
            monitor.auto_scrape_enabled = request.auto_scrape_enabled
        
        await monitor.save_config()
        
        return {
            "message": "Configuration updated",
            "status": await monitor.get_status()
        }
        
    except Exception as e:
        logger.error(f"Error updating config: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/monitor/processed-files")
async def get_processed_files():
    """
    Get list of processed files
    """
    try:
        files = await db.processed_files.find({}, {"_id": 0}).sort("processed_at", -1).to_list(100)
        return {"files": files, "count": len(files)}
    except Exception as e:
        logger.error(f"Error fetching processed files: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# System Info Endpoints
@api_router.get("/system/info")
async def get_system_info():
    """
    Get system information and service status
    """
    try:
        import platform
        import psutil
        
        # Get process info for backend
        current_process = psutil.Process()
        
        info = {
            "platform": {
                "system": platform.system(),
                "release": platform.release(),
                "version": platform.version(),
                "machine": platform.machine(),
                "processor": platform.processor(),
                "python_version": platform.python_version()
            },
            "resources": {
                "cpu_percent": psutil.cpu_percent(interval=1),
                "cpu_count": psutil.cpu_count(),
                "memory": {
                    "total": psutil.virtual_memory().total,
                    "available": psutil.virtual_memory().available,
                    "percent": psutil.virtual_memory().percent,
                    "used": psutil.virtual_memory().used
                },
                "disk": {
                    "total": psutil.disk_usage('/').total,
                    "used": psutil.disk_usage('/').used,
                    "free": psutil.disk_usage('/').free,
                    "percent": psutil.disk_usage('/').percent
                }
            },
            "backend": {
                "pid": current_process.pid,
                "cpu_percent": current_process.cpu_percent(),
                "memory_mb": current_process.memory_info().rss / 1024 / 1024,
                "threads": current_process.num_threads(),
                "uptime_seconds": time.time() - current_process.create_time()
            },
            "database": {
                "connected": True,
                "url": os.environ.get('MONGO_URL', 'mongodb://localhost:27017').split('@')[-1]  # Hide credentials
            },
            "scrapers": {
                "available": ["gaydvdempire", "aebn", "gevi", "radvideo"],
                "total": 4
            }
        }
        
        return info
    except Exception as e:
        logger.error(f"Error getting system info: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/system/logs")
async def get_system_logs(lines: int = 100, service: str = "backend"):
    """
    Get system logs
    
    Args:
        lines: Number of lines to retrieve (default: 100)
        service: Which service logs to get (backend/frontend/all)
    """
    try:
        import subprocess
        
        logs = {}
        
        if service in ["backend", "all"]:
            try:
                # Try to read supervisor logs first
                backend_log = subprocess.run(
                    ["tail", "-n", str(lines), "/var/log/supervisor/backend.out.log"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if backend_log.returncode == 0:
                    logs["backend"] = backend_log.stdout
            except:
                logs["backend"] = "Backend logs not available"
        
        if service in ["frontend", "all"]:
            try:
                frontend_log = subprocess.run(
                    ["tail", "-n", str(lines), "/var/log/supervisor/frontend.out.log"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if frontend_log.returncode == 0:
                    logs["frontend"] = frontend_log.stdout
            except:
                logs["frontend"] = "Frontend logs not available"
        
        return {
            "service": service,
            "lines": lines,
            "logs": logs,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting logs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/system/restart")
async def restart_backend():
    """
    Restart the backend service via supervisor
    
    Returns:
        Success message if restart command was sent
    """
    try:
        import subprocess
        
        # Execute supervisorctl restart command
        result = subprocess.run(
            ["sudo", "supervisorctl", "restart", "backend"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            return {
                "success": True,
                "message": "Backend restart initiated",
                "output": result.stdout,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        else:
            logger.error(f"Restart failed: {result.stderr}")
            raise HTTPException(
                status_code=500, 
                detail=f"Restart failed: {result.stderr}"
            )
            
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Restart command timed out")
    except Exception as e:
        logger.error(f"Error restarting backend: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/proxy/image")
async def proxy_image(url: str):
    """
    Proxy endpoint to fetch images from external sources and serve them
    This bypasses CORS/ORB restrictions for images from sites like GEVI
    """
    try:
        logger.info(f"Proxying image from: {url}")
        
        # Validate URL
        if not url.startswith(('http://', 'https://')):
            raise HTTPException(status_code=400, detail="Invalid URL")
        
        # Fetch the image
        response = requests.get(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'image/*'
            },
            timeout=30,
            stream=True
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Failed to fetch image: HTTP {response.status_code}"
            )
        
        # Determine content type
        content_type = response.headers.get('Content-Type', 'image/jpeg')
        
        # Return the image with proper headers
        from fastapi.responses import StreamingResponse
        return StreamingResponse(
            response.iter_content(chunk_size=8192),
            media_type=content_type,
            headers={
                'Cache-Control': 'public, max-age=86400',  # Cache for 24 hours
                'Access-Control-Allow-Origin': '*'
            }
        )
        
    except requests.RequestException as e:
        logger.error(f"Error proxying image: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch image: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error in image proxy: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
