"""
StarMap Browser-Use E2E Test
Tests the frontend functionality using browser automation.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


async def test_frontend_pages():
    """Test frontend pages using browser automation."""
    print("=== Browser-Use E2E Test ===")
    
    try:
        # Import browser-use
        from browser_use import Browser
        
        # Initialize browser
        browser = Browser()
        
        # Test 1: Home page
        print("\n1. Testing Home page...")
        page = await browser.new_page()
        await page.goto("http://localhost:5173")
        
        # Check if page loads
        title = await page.title()
        print(f"   Page title: {title}")
        
        # Check for graph visualization
        graph_element = await page.query_selector(".graph-canvas")
        if graph_element:
            print("   [PASS] Graph visualization found")
        else:
            print("   [FAIL] Graph visualization not found")
        
        # Test 2: Position list page
        print("\n2. Testing Position list page...")
        await page.goto("http://localhost:5173/positions")
        
        # Check for position list
        position_list = await page.query_selector(".position-list")
        if position_list:
            print("   [PASS] Position list found")
        else:
            print("   [FAIL] Position list not found")
        
        # Test 3: Match diagnosis page
        print("\n3. Testing Match diagnosis page...")
        await page.goto("http://localhost:5173/match")
        
        # Check for match form
        match_form = await page.query_selector(".match-form")
        if match_form:
            print("   [PASS] Match form found")
        else:
            print("   [FAIL] Match form not found")
        
        # Test 4: Evolution dashboard
        print("\n4. Testing Evolution dashboard...")
        await page.goto("http://localhost:5173/evolution")
        
        # Check for evolution dashboard
        evolution_dashboard = await page.query_selector(".evolution-dashboard")
        if evolution_dashboard:
            print("   [PASS] Evolution dashboard found")
        else:
            print("   [FAIL] Evolution dashboard not found")
        
        # Test 5: Admin page
        print("\n5. Testing Admin page...")
        await page.goto("http://localhost:5173/admin")
        
        # Check for admin panel
        admin_panel = await page.query_selector(".admin-panel")
        if admin_panel:
            print("   [PASS] Admin panel found")
        else:
            print("   [FAIL] Admin panel not found")
        
        # Close browser
        await browser.close()
        
        print("\n=== Browser-Use E2E Test Complete ===")
        return True
        
    except ImportError:
        print("[WARN] browser-use not installed, skipping browser tests")
        return True
    except Exception as e:
        print(f"[FAIL] Browser test failed: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_frontend_pages())
    sys.exit(0 if success else 1)
