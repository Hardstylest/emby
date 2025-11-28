#!/usr/bin/env python3
"""
Test script for scraper functionality
Tests AEBN and GayDVDEmpire scrapers
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, '/app/backend')

from server import AEBNScraper, GayDVDEmpireScraper, GEVIScraper

async def test_aebn_search():
    """Test AEBN search functionality"""
    print("\n" + "="*60)
    print("TEST: AEBN Search")
    print("="*60)
    
    query = "Falcon"
    print(f"Searching AEBN for: {query}")
    
    try:
        results = await AEBNScraper.search_movie(query)
        
        if results:
            print(f"✅ SUCCESS: Found {len(results)} results")
            for i, result in enumerate(results[:3], 1):
                print(f"  {i}. {result.get('title', 'N/A')} (ID: {result.get('id', 'N/A')})")
        else:
            print(f"❌ FAILED: No results found")
            
        return len(results) > 0
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def test_aebn_scrape():
    """Test AEBN scraping functionality"""
    print("\n" + "="*60)
    print("TEST: AEBN Scrape")
    print("="*60)
    
    # Test with a known movie ID
    movie_id = "172181"  # Example ID
    print(f"Scraping AEBN movie ID: {movie_id}")
    
    try:
        metadata = await AEBNScraper.scrape_movie(movie_id)
        
        if metadata and metadata.get('title'):
            print(f"✅ SUCCESS: Scraped movie")
            print(f"  Title: {metadata.get('title', 'N/A')}")
            print(f"  Year: {metadata.get('year', 'N/A')}")
            print(f"  Studio: {metadata.get('studio', 'N/A')}")
            print(f"  Actors: {len(metadata.get('actors', []))} actors")
            return True
        else:
            print(f"❌ FAILED: No metadata returned")
            return False
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def test_gaydvdempire_search():
    """Test GayDVDEmpire search functionality"""
    print("\n" + "="*60)
    print("TEST: GayDVDEmpire Search")
    print("="*60)
    
    query = "Falcon"
    print(f"Searching GayDVDEmpire for: {query}")
    
    try:
        results = await GayDVDEmpireScraper.search_movie(query)
        
        if results:
            print(f"✅ SUCCESS: Found {len(results)} results")
            for i, result in enumerate(results[:3], 1):
                print(f"  {i}. {result.get('title', 'N/A')} (ID: {result.get('id', 'N/A')})")
        else:
            print(f"❌ FAILED: No results found")
            
        return len(results) > 0
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def test_gaydvdempire_scrape():
    """Test GayDVDEmpire scraping functionality"""
    print("\n" + "="*60)
    print("TEST: GayDVDEmpire Scrape")
    print("="*60)
    
    # Test with a known movie ID
    movie_id = "1668727"  # Example ID
    print(f"Scraping GayDVDEmpire movie ID: {movie_id}")
    
    try:
        metadata = await GayDVDEmpireScraper.scrape_movie(movie_id)
        
        if metadata and metadata.get('title'):
            print(f"✅ SUCCESS: Scraped movie")
            print(f"  Title: {metadata.get('title', 'N/A')}")
            print(f"  Year: {metadata.get('year', 'N/A')}")
            print(f"  Studio: {metadata.get('studio', 'N/A')}")
            print(f"  Actors: {len(metadata.get('actors', []))} actors")
            return True
        else:
            print(f"❌ FAILED: No metadata returned")
            return False
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def test_gevi_scrape():
    """Test GEVI scraping functionality"""
    print("\n" + "="*60)
    print("TEST: GEVI Scrape")
    print("="*60)
    
    # Test with a known movie ID
    movie_id = "48797"  # Example ID
    print(f"Scraping GEVI movie ID: {movie_id}")
    
    try:
        metadata = await GEVIScraper.scrape_movie(movie_id)
        
        if metadata and metadata.get('title'):
            print(f"✅ SUCCESS: Scraped movie")
            print(f"  Title: {metadata.get('title', 'N/A')}")
            print(f"  Year: {metadata.get('year', 'N/A')}")
            print(f"  Studio: {metadata.get('studio', 'N/A')}")
            print(f"  Actors: {len(metadata.get('actors', []))} actors")
            return True
        else:
            print(f"❌ FAILED: No metadata returned")
            return False
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run all tests"""
    print("\n" + "#"*60)
    print("# SCRAPER TEST SUITE")
    print("#"*60)
    
    results = {}
    
    # Test AEBN
    results['aebn_search'] = await test_aebn_search()
    results['aebn_scrape'] = await test_aebn_scrape()
    
    # Test GayDVDEmpire
    results['gaydvdempire_search'] = await test_gaydvdempire_search()
    results['gaydvdempire_scrape'] = await test_gaydvdempire_scrape()
    
    # Test GEVI
    results['gevi_scrape'] = await test_gevi_scrape()
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name}: {status}")
    
    total = len(results)
    passed = sum(results.values())
    print(f"\nTotal: {passed}/{total} tests passed")
    
    return passed == total

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
