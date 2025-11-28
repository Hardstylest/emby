import os
import re
import time
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone
import xml.etree.ElementTree as ET
from xml.dom import minidom

logger = logging.getLogger(__name__)

# Supported video extensions
VIDEO_EXTENSIONS = {
    '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm',
    '.m4v', '.mpg', '.mpeg', '.3gp', '.m2ts', '.ts'
}

class MovieFileHandler(FileSystemEventHandler):
    """Handles new video file detection"""
    
    def __init__(self, monitor_service):
        self.monitor_service = monitor_service
        self.processing = set()  # Track files being processed
        
    def on_created(self, event):
        """Called when a file is created"""
        if event.is_directory:
            return
            
        file_path = Path(event.src_path)
        
        # Check if it's a video file
        if file_path.suffix.lower() in VIDEO_EXTENSIONS:
            # Avoid duplicate processing
            if str(file_path) not in self.processing:
                self.processing.add(str(file_path))
                logger.info(f"New video file detected: {file_path.name}")
                
                # Schedule async processing
                asyncio.create_task(
                    self.monitor_service.process_new_file(file_path)
                )
    
    def on_moved(self, event):
        """Called when a file is moved into the watched folder"""
        if event.is_directory:
            return
            
        dest_path = Path(event.dest_path)
        
        if dest_path.suffix.lower() in VIDEO_EXTENSIONS:
            if str(dest_path) not in self.processing:
                self.processing.add(str(dest_path))
                logger.info(f"Video file moved into folder: {dest_path.name}")
                
                asyncio.create_task(
                    self.monitor_service.process_new_file(dest_path)
                )

class FolderMonitorService:
    """Service for monitoring folders and auto-generating NFO files"""
    
    def __init__(self, db):
        self.db = db
        self.observer = None
        self.watched_folders = []
        self.is_running = False
        self.preferred_source = "radvideo"  # Default to RadVideo (most reliable search)
        self.auto_scrape_enabled = True
        
    async def load_config(self):
        """Load monitoring configuration from database"""
        config = await self.db.monitor_config.find_one({"_id": "main"})
        if config:
            self.watched_folders = config.get('watched_folders', [])
            self.preferred_source = config.get('preferred_source', 'radvideo')
            self.auto_scrape_enabled = config.get('auto_scrape_enabled', True)
            logger.info(f"Loaded config: {len(self.watched_folders)} folders, source: {self.preferred_source}")
    
    async def save_config(self):
        """Save monitoring configuration to database"""
        config = {
            '_id': 'main',
            'watched_folders': self.watched_folders,
            'preferred_source': self.preferred_source,
            'auto_scrape_enabled': self.auto_scrape_enabled,
            'updated_at': datetime.now(timezone.utc).isoformat()
        }
        await self.db.monitor_config.update_one(
            {'_id': 'main'},
            {'$set': config},
            upsert=True
        )
        logger.info("Configuration saved")
    
    async def add_watched_folder(self, folder_path: str) -> bool:
        """Add a folder to the watch list"""
        path = Path(folder_path)
        
        if not path.exists():
            logger.error(f"Folder does not exist: {folder_path}")
            return False
            
        if not path.is_dir():
            logger.error(f"Path is not a directory: {folder_path}")
            return False
        
        folder_str = str(path.absolute())
        
        if folder_str not in self.watched_folders:
            self.watched_folders.append(folder_str)
            await self.save_config()
            
            # Start monitoring if not already running
            if self.is_running:
                self._watch_folder(folder_str)
            
            logger.info(f"Added watched folder: {folder_str}")
            return True
        
        logger.info(f"Folder already being watched: {folder_str}")
        return True
    
    async def remove_watched_folder(self, folder_path: str) -> bool:
        """Remove a folder from the watch list"""
        folder_str = str(Path(folder_path).absolute())
        
        if folder_str in self.watched_folders:
            self.watched_folders.remove(folder_str)
            await self.save_config()
            logger.info(f"Removed watched folder: {folder_str}")
            return True
        
        return False
    
    def _watch_folder(self, folder_path: str):
        """Add a folder to the observer"""
        event_handler = MovieFileHandler(self)
        self.observer.schedule(event_handler, folder_path, recursive=False)
        logger.info(f"Now watching: {folder_path}")
    
    async def start_monitoring(self):
        """Start the folder monitoring service"""
        if self.is_running:
            logger.warning("Monitoring already running")
            return
        
        await self.load_config()
        
        if not self.watched_folders:
            logger.info("No folders configured for monitoring")
            return
        
        self.observer = Observer()
        
        for folder in self.watched_folders:
            if Path(folder).exists():
                self._watch_folder(folder)
            else:
                logger.warning(f"Watched folder no longer exists: {folder}")
        
        self.observer.start()
        self.is_running = True
        logger.info("Folder monitoring started")
    
    async def stop_monitoring(self):
        """Stop the folder monitoring service"""
        if not self.is_running:
            return
        
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None
        
        self.is_running = False
        logger.info("Folder monitoring stopped")
    
    def extract_movie_info(self, filename: str) -> Dict[str, Any]:
        """
        Extract movie title and year from filename
        Supports formats like:
        - Movie Title (2023).mp4
        - Movie.Title.2023.1080p.mp4
        - Movie_Title_2023.mkv
        """
        # Remove extension
        name = Path(filename).stem
        
        info = {
            'title': '',
            'year': None,
            'quality': None
        }
        
        # Extract year in parentheses: (2023) or (2020)
        year_match = re.search(r'\((\d{4})\)', name)
        if year_match:
            info['year'] = int(year_match.group(1))
            name = name.replace(year_match.group(0), '').strip()
        else:
            # Extract year without parentheses: 2023 or 2020
            year_match = re.search(r'\b(19\d{2}|20\d{2})\b', name)
            if year_match:
                info['year'] = int(year_match.group(1))
                name = name[:year_match.start()].strip()
        
        # Extract quality tags
        quality_tags = ['1080p', '720p', '2160p', '4K', 'BluRay', 'WEB-DL', 'HDRip']
        for tag in quality_tags:
            if tag.lower() in name.lower():
                info['quality'] = tag
                name = re.sub(re.escape(tag), '', name, flags=re.IGNORECASE)
        
        # Clean up the title
        # Replace dots, underscores, and multiple spaces with single space
        name = re.sub(r'[._]+', ' ', name)
        name = re.sub(r'\s+', ' ', name)
        name = name.strip()
        
        info['title'] = name
        
        return info
    
    async def search_movie(self, title: str, year: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        Search for a movie using the preferred scraper
        """
        from server import GayDVDEmpireScraper, GEVIScraper, AEBNScraper, RadVideoScraper
        
        logger.info(f"Searching for: {title} ({year if year else 'no year'}) using {self.preferred_source}")
        
        try:
            # Use the preferred scraper for search
            if self.preferred_source == "gaydvdempire":
                results = await GayDVDEmpireScraper.search_movie(title)
            elif self.preferred_source == "aebn":
                results = await AEBNScraper.search_movie(title)
            elif self.preferred_source == "gevi":
                results = await GEVIScraper.search_movie(title)
            elif self.preferred_source == "radvideo":
                results = RadVideoScraper.search_movie(title)
            else:
                logger.warning(f"Unknown source: {self.preferred_source}, using GEVI")
                results = await GEVIScraper.search_movie(title)
            
            if not results:
                logger.warning(f"No results found for: {title}")
                return None
            
            # Try to find best match based on year if provided
            if year:
                for result in results:
                    if str(year) in result.get('title', ''):
                        logger.info(f"Found match with year: {result.get('title')}")
                        return result
            
            # Return first result if no year match
            logger.info(f"Using first result: {results[0].get('title')}")
            return results[0]
            
        except Exception as e:
            logger.error(f"Error searching for movie: {str(e)}")
            return None
    
    async def scrape_and_generate_nfo(self, movie_id: str, source: str, file_path: Path) -> bool:
        """
        Scrape metadata, generate NFO file, and download images
        """
        from server import GayDVDEmpireScraper, AEBNScraper, GEVIScraper, NFOGenerator, download_image
        
        try:
            # Scrape metadata based on source
            if source == "gaydvdempire":
                metadata = await GayDVDEmpireScraper.scrape_movie(movie_id)
            elif source == "aebn":
                metadata = await AEBNScraper.scrape_movie(movie_id)
            elif source == "gevi":
                metadata = await GEVIScraper.scrape_movie(movie_id)
            elif source == "radvideo":
                from server import RadVideoScraper
                metadata = await RadVideoScraper.scrape_movie(movie_id)
            else:
                logger.error(f"Unknown source: {source}")
                return False
            
            # Generate NFO content
            nfo_content = NFOGenerator.generate_nfo(metadata)
            
            # Generate NFO file path (same name as video file, but .nfo extension)
            nfo_path = file_path.with_suffix('.nfo')
            
            # Check if NFO already exists
            if nfo_path.exists():
                logger.info(f"NFO already exists: {nfo_path.name}")
                return False
            
            # Write NFO file
            with open(nfo_path, 'w', encoding='utf-8') as f:
                f.write(nfo_content)
            
            logger.info(f"✅ NFO file created: {nfo_path.name}")
            
            # Download images
            movie_title = file_path.stem  # Use video filename without extension
            
            # Download poster/cover
            if metadata.get('poster_url'):
                poster_path = file_path.parent / f"{movie_title}-poster.jpg"
                if download_image(metadata['poster_url'], str(poster_path)):
                    logger.info(f"✅ Poster downloaded: {poster_path.name}")
            
            # Download fanart/backdrop (if thumb_url exists and is different from poster)
            if metadata.get('thumb_url') and metadata.get('thumb_url') != metadata.get('poster_url'):
                fanart_path = file_path.parent / f"{movie_title}-fanart.jpg"
                if download_image(metadata['thumb_url'], str(fanart_path)):
                    logger.info(f"✅ Fanart downloaded: {fanart_path.name}")
            
            # Save to database
            await self.log_processed_file(file_path, metadata, nfo_path)
            
            return True
            
        except Exception as e:
            logger.error(f"Error generating NFO: {str(e)}")
            return False
    
    async def process_new_file(self, file_path: Path):
        """
        Process a newly detected video file
        """
        try:
            logger.info(f"Processing: {file_path.name}")
            
            # Check if auto-scraping is enabled
            if not self.auto_scrape_enabled:
                logger.info("Auto-scraping disabled, skipping")
                return
            
            # Wait a bit to ensure file is fully copied
            await asyncio.sleep(2)
            
            # Check if NFO already exists
            nfo_path = file_path.with_suffix('.nfo')
            if nfo_path.exists():
                logger.info(f"NFO already exists for: {file_path.name}")
                return
            
            # Extract movie info from filename
            movie_info = self.extract_movie_info(file_path.name)
            
            if not movie_info['title']:
                logger.warning(f"Could not extract title from: {file_path.name}")
                return
            
            logger.info(f"Extracted: Title='{movie_info['title']}', Year={movie_info['year']}")
            
            # Search for the movie
            search_result = await self.search_movie(
                movie_info['title'],
                movie_info['year']
            )
            
            if not search_result or not search_result.get('id'):
                logger.warning(f"Could not find movie: {movie_info['title']}")
                await self.log_failed_file(file_path, movie_info, "No search results")
                return
            
            # Scrape and generate NFO using the preferred source
            # The search_result['id'] matches the preferred_source scraper
            success = await self.scrape_and_generate_nfo(
                search_result['id'],
                self.preferred_source,
                file_path
            )
            
            if success:
                logger.info(f"✅ Successfully processed: {file_path.name}")
            else:
                logger.warning(f"Failed to process: {file_path.name}")
                
        except Exception as e:
            logger.error(f"Error processing file {file_path.name}: {str(e)}")
            await self.log_failed_file(file_path, {}, str(e))
    
    async def log_processed_file(self, file_path: Path, metadata: Dict, nfo_path: Path):
        """Log successfully processed file to database"""
        doc = {
            'file_path': str(file_path),
            'nfo_path': str(nfo_path),
            'title': metadata.get('title'),
            'source': metadata.get('source'),
            'source_id': metadata.get('source_id'),
            'processed_at': datetime.now(timezone.utc).isoformat(),
            'status': 'success'
        }
        await self.db.processed_files.insert_one(doc)
    
    async def log_failed_file(self, file_path: Path, movie_info: Dict, error: str):
        """Log failed file processing to database"""
        doc = {
            'file_path': str(file_path),
            'extracted_info': movie_info,
            'error': error,
            'processed_at': datetime.now(timezone.utc).isoformat(),
            'status': 'failed'
        }
        await self.db.processed_files.insert_one(doc)
    
    async def scan_existing_files(self, folder_path: str):
        """
        Manually scan a folder for existing files without NFO
        """
        path = Path(folder_path)
        if not path.exists() or not path.is_dir():
            return []
        
        files_to_process = []
        
        for file in path.iterdir():
            if file.suffix.lower() in VIDEO_EXTENSIONS:
                nfo_file = file.with_suffix('.nfo')
                if not nfo_file.exists():
                    files_to_process.append(str(file))
        
        logger.info(f"Found {len(files_to_process)} files without NFO in {folder_path}")
        return files_to_process
    
    async def get_status(self) -> Dict[str, Any]:
        """Get monitoring service status"""
        return {
            'is_running': self.is_running,
            'watched_folders': self.watched_folders,
            'preferred_source': self.preferred_source,
            'auto_scrape_enabled': self.auto_scrape_enabled,
            'folder_count': len(self.watched_folders)
        }

# Global instance
monitor_service = None

def get_monitor_service(db) -> FolderMonitorService:
    """Get or create the global monitor service instance"""
    global monitor_service
    if monitor_service is None:
        monitor_service = FolderMonitorService(db)
    return monitor_service
