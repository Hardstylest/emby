#!/usr/bin/env python3
"""
Backend API Test Suite for Emby Metadata Scraper
Tests all scraper endpoints: GayDVDEmpire, AEBN, GEVI, RadVideo
"""

import requests
import sys
import json
from datetime import datetime

# Get backend URL from environment
BACKEND_URL = "https://metadata-scraper.preview.emergentagent.com/api"

class ScraperAPITester:
    def __init__(self, base_url=BACKEND_URL):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []

    def log_test(self, name, passed, details=""):
        """Log test result"""
        self.tests_run += 1
        if passed:
            self.tests_passed += 1
        
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"\n{status} - {name}")
        if details:
            print(f"   {details}")
        
        self.test_results.append({
            "name": name,
            "passed": passed,
            "details": details
        })

    def test_gaydvdempire_search(self):
        """Test Gay DVD Empire search functionality"""
        print("\n" + "="*60)
        print("TEST: Gay DVD Empire Search")
        print("="*60)
        
        try:
            response = requests.post(
                f"{self.base_url}/search",
                json={"source": "gaydvdempire", "query": "Falcon"},
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])
                
                if len(results) > 0:
                    self.log_test(
                        "GayDVDEmpire Search",
                        True,
                        f"Found {len(results)} results. First result: {results[0].get('title', 'N/A')}"
                    )
                    return True
                else:
                    self.log_test(
                        "GayDVDEmpire Search",
                        False,
                        "No results returned"
                    )
                    return False
            else:
                self.log_test(
                    "GayDVDEmpire Search",
                    False,
                    f"Status code: {response.status_code}, Response: {response.text[:200]}"
                )
                return False
                
        except Exception as e:
            self.log_test("GayDVDEmpire Search", False, f"Exception: {str(e)}")
            return False

    def test_gaydvdempire_scrape(self):
        """Test Gay DVD Empire scraping by ID"""
        print("\n" + "="*60)
        print("TEST: Gay DVD Empire Scrape by ID")
        print("="*60)
        
        # Test with a known movie ID
        movie_id = "1668727"
        
        try:
            response = requests.post(
                f"{self.base_url}/scrape",
                json={"source": "gaydvdempire", "movie_id": movie_id},
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('title'):
                    self.log_test(
                        "GayDVDEmpire Scrape",
                        True,
                        f"Title: {data.get('title')}, Year: {data.get('year')}, Studio: {data.get('studio')}"
                    )
                    return True
                else:
                    self.log_test(
                        "GayDVDEmpire Scrape",
                        False,
                        "No title in response"
                    )
                    return False
            else:
                self.log_test(
                    "GayDVDEmpire Scrape",
                    False,
                    f"Status code: {response.status_code}, Response: {response.text[:200]}"
                )
                return False
                
        except Exception as e:
            self.log_test("GayDVDEmpire Scrape", False, f"Exception: {str(e)}")
            return False

    def test_aebn_search(self):
        """Test AEBN search functionality"""
        print("\n" + "="*60)
        print("TEST: AEBN Search")
        print("="*60)
        
        try:
            response = requests.post(
                f"{self.base_url}/search",
                json={"source": "aebn", "query": "Falcon"},
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])
                
                if len(results) > 0:
                    self.log_test(
                        "AEBN Search",
                        True,
                        f"Found {len(results)} results. First result: {results[0].get('title', 'N/A')}"
                    )
                    return True
                else:
                    self.log_test(
                        "AEBN Search",
                        False,
                        "No results returned"
                    )
                    return False
            else:
                self.log_test(
                    "AEBN Search",
                    False,
                    f"Status code: {response.status_code}, Response: {response.text[:200]}"
                )
                return False
                
        except Exception as e:
            self.log_test("AEBN Search", False, f"Exception: {str(e)}")
            return False

    def test_aebn_scrape(self):
        """Test AEBN scraping by ID"""
        print("\n" + "="*60)
        print("TEST: AEBN Scrape by ID")
        print("="*60)
        
        # Test with a known movie ID
        movie_id = "172181"
        
        try:
            response = requests.post(
                f"{self.base_url}/scrape",
                json={"source": "aebn", "movie_id": movie_id},
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('title'):
                    self.log_test(
                        "AEBN Scrape",
                        True,
                        f"Title: {data.get('title')}, Year: {data.get('year')}, Studio: {data.get('studio')}"
                    )
                    return True
                else:
                    self.log_test(
                        "AEBN Scrape",
                        False,
                        "No title in response"
                    )
                    return False
            else:
                self.log_test(
                    "AEBN Scrape",
                    False,
                    f"Status code: {response.status_code}, Response: {response.text[:200]}"
                )
                return False
                
        except Exception as e:
            self.log_test("AEBN Scrape", False, f"Exception: {str(e)}")
            return False

    def test_gevi_search(self):
        """Test GEVI search functionality (expected to return empty)"""
        print("\n" + "="*60)
        print("TEST: GEVI Search (Expected: Empty Results)")
        print("="*60)
        
        try:
            response = requests.post(
                f"{self.base_url}/search",
                json={"source": "gevi", "query": "Falcon"},
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])
                
                # GEVI search is intentionally disabled, so empty results are expected
                if len(results) == 0:
                    self.log_test(
                        "GEVI Search",
                        True,
                        "Returns empty results as expected (search disabled)"
                    )
                    return True
                else:
                    self.log_test(
                        "GEVI Search",
                        True,
                        f"Found {len(results)} results (unexpected but not an error)"
                    )
                    return True
            else:
                self.log_test(
                    "GEVI Search",
                    False,
                    f"Status code: {response.status_code}, Response: {response.text[:200]}"
                )
                return False
                
        except Exception as e:
            self.log_test("GEVI Search", False, f"Exception: {str(e)}")
            return False

    def test_gevi_scrape(self):
        """Test GEVI scraping by ID"""
        print("\n" + "="*60)
        print("TEST: GEVI Scrape by ID")
        print("="*60)
        
        # Test with a known movie ID
        movie_id = "48797"
        
        try:
            response = requests.post(
                f"{self.base_url}/scrape",
                json={"source": "gevi", "movie_id": movie_id},
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('title'):
                    self.log_test(
                        "GEVI Scrape",
                        True,
                        f"Title: {data.get('title')}, Year: {data.get('year')}, Studio: {data.get('studio')}"
                    )
                    return True
                else:
                    self.log_test(
                        "GEVI Scrape",
                        False,
                        "No title in response"
                    )
                    return False
            else:
                self.log_test(
                    "GEVI Scrape",
                    False,
                    f"Status code: {response.status_code}, Response: {response.text[:200]}"
                )
                return False
                
        except Exception as e:
            self.log_test("GEVI Scrape", False, f"Exception: {str(e)}")
            return False

    def test_radvideo_search(self):
        """Test RadVideo search functionality"""
        print("\n" + "="*60)
        print("TEST: RadVideo Search")
        print("="*60)
        
        try:
            response = requests.post(
                f"{self.base_url}/search",
                json={"source": "radvideo", "query": "Twinks"},
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])
                
                if len(results) > 0:
                    self.log_test(
                        "RadVideo Search",
                        True,
                        f"Found {len(results)} results. First result: {results[0].get('title', 'N/A')}"
                    )
                    return True
                else:
                    self.log_test(
                        "RadVideo Search",
                        False,
                        "No results returned"
                    )
                    return False
            else:
                self.log_test(
                    "RadVideo Search",
                    False,
                    f"Status code: {response.status_code}, Response: {response.text[:200]}"
                )
                return False
                
        except Exception as e:
            self.log_test("RadVideo Search", False, f"Exception: {str(e)}")
            return False

    def test_radvideo_scrape(self):
        """Test RadVideo scraping by ID"""
        print("\n" + "="*60)
        print("TEST: RadVideo Scrape by ID")
        print("="*60)
        
        # Test with a known movie slug
        movie_id = "twinks-on-all-4-s-dvd"
        
        try:
            response = requests.post(
                f"{self.base_url}/scrape",
                json={"source": "radvideo", "movie_id": movie_id},
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('title'):
                    self.log_test(
                        "RadVideo Scrape",
                        True,
                        f"Title: {data.get('title')}, Year: {data.get('year')}, Studio: {data.get('studio')}"
                    )
                    return True
                else:
                    self.log_test(
                        "RadVideo Scrape",
                        False,
                        "No title in response"
                    )
                    return False
            else:
                self.log_test(
                    "RadVideo Scrape",
                    False,
                    f"Status code: {response.status_code}, Response: {response.text[:200]}"
                )
                return False
                
        except Exception as e:
            self.log_test("RadVideo Scrape", False, f"Exception: {str(e)}")
            return False

    def test_nfo_generation(self):
        """Test NFO file generation"""
        print("\n" + "="*60)
        print("TEST: NFO Generation")
        print("="*60)
        
        # Use sample metadata
        sample_metadata = {
            "source": "gaydvdempire",
            "source_id": "123456",
            "title": "Test Movie",
            "year": 2023,
            "plot": "Test plot",
            "studio": "Test Studio",
            "director": "Test Director",
            "genres": ["Action", "Drama"],
            "actors": [{"name": "Actor 1", "role": ""}],
            "runtime": 120
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/generate-nfo",
                json={"metadata": sample_metadata},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('nfo_content') and '<movie>' in data.get('nfo_content', ''):
                    self.log_test(
                        "NFO Generation",
                        True,
                        f"NFO generated successfully, filename: {data.get('filename', 'N/A')}"
                    )
                    return True
                else:
                    self.log_test(
                        "NFO Generation",
                        False,
                        "NFO content missing or invalid"
                    )
                    return False
            else:
                self.log_test(
                    "NFO Generation",
                    False,
                    f"Status code: {response.status_code}, Response: {response.text[:200]}"
                )
                return False
                
        except Exception as e:
            self.log_test("NFO Generation", False, f"Exception: {str(e)}")
            return False

    def test_error_handling(self):
        """Test error handling for invalid movie ID"""
        print("\n" + "="*60)
        print("TEST: Error Handling (Invalid Movie ID)")
        print("="*60)
        
        # Test with an invalid movie ID that should trigger aspxerrorpath redirect
        invalid_id = "999999999"
        
        try:
            response = requests.post(
                f"{self.base_url}/scrape",
                json={"source": "gaydvdempire", "movie_id": invalid_id},
                timeout=60
            )
            
            # Should return 404 or 500 with proper error message
            if response.status_code in [404, 500]:
                error_detail = response.json().get('detail', '')
                if 'not found' in error_detail.lower() or 'error' in error_detail.lower():
                    self.log_test(
                        "Error Handling",
                        True,
                        f"Properly handled invalid ID with status {response.status_code}: {error_detail}"
                    )
                    return True
                else:
                    self.log_test(
                        "Error Handling",
                        False,
                        f"Error message unclear: {error_detail}"
                    )
                    return False
            else:
                self.log_test(
                    "Error Handling",
                    False,
                    f"Unexpected status code: {response.status_code}"
                )
                return False
                
        except Exception as e:
            self.log_test("Error Handling", False, f"Exception: {str(e)}")
            return False

    def run_all_tests(self):
        """Run all tests"""
        print("\n" + "#"*60)
        print("# EMBY METADATA SCRAPER - BACKEND API TEST SUITE")
        print("#"*60)
        print(f"Backend URL: {self.base_url}")
        print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Run all tests
        self.test_gaydvdempire_search()
        self.test_gaydvdempire_scrape()
        self.test_aebn_search()
        self.test_aebn_scrape()
        self.test_gevi_search()
        self.test_gevi_scrape()
        self.test_radvideo_search()
        self.test_radvideo_scrape()
        self.test_nfo_generation()
        self.test_error_handling()
        
        # Print summary
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        
        for result in self.test_results:
            status = "✅ PASS" if result['passed'] else "❌ FAIL"
            print(f"{status} - {result['name']}")
        
        print(f"\nTotal: {self.tests_passed}/{self.tests_run} tests passed")
        print(f"Success rate: {(self.tests_passed/self.tests_run*100):.1f}%")
        
        return self.tests_passed == self.tests_run

def main():
    """Main test runner"""
    tester = ScraperAPITester()
    success = tester.run_all_tests()
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
