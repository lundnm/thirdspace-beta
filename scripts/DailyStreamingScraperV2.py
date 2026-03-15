import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime

async def scrape_league_schedules():
    # 1. Define your target leagues and URLs
    leagues = {
        "NBA": "https://www.livesportsontv.com/league/nba",
        "MCBB": "https://www.livesportsontv.com/league/ncaa-basketball",
        "WCBB": "https://www.livesportsontv.com/league/ncaa-basketball-women"
    }
    
    all_games = []
    
    # 2. Get today's date formatted to match the website (e.g., "12" and "Mar")
    today = datetime.now()
    target_day = str(today.day)
    target_month = today.strftime("%b") 
    
    async with async_playwright() as p:
        print("Launching browser...")
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # 3. Loop through each league page
        for league_name, url in leagues.items():
            print(f"\n--- Scraping {league_name}: {url} ---")
            await page.goto(url)
            
            # Scroll a few times to ensure all of today's games are loaded in the DOM
            # (especially helpful for massive MCBB Saturday slates)
            for _ in range(3):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(1000)
            
            # Grab the fully loaded HTML
            html_content = await page.content()
            soup = BeautifulSoup(html_content, 'html.parser')
            
            game_rows = soup.find_all('div', class_='event--wrapp')
            print(f"Found {len(game_rows)} total scheduled games. Filtering for today ({target_day} {target_month})...")
            
            games_added = 0
            
            # 4. Parse the data row by row
            for row in game_rows:
                try:
                    # Check the date inside the game row
                    date_div = row.find('div', class_='event__info--date')
                    if not date_div:
                        continue
                        
                    game_day = date_div.find('b').get_text(strip=True) if date_div.find('b') else ""
                    game_month = date_div.find('span').get_text(strip=True) if date_div.find('span') else ""
                    
                    # Only proceed if the game is happening today
                    if game_day == target_day and game_month.lower() == target_month.lower():
                        
                        # Extract Time
                        time_div = row.find('time')
                        event_time = time_div.get_text(strip=True) if time_div else "Time Not Found"
                        
                        # Extract Teams (Using lambda to safely find classes that contain the target string)
                        home_elem = row.find('div', class_=lambda c: c and 'event__participant--home' in c)
                        away_elem = row.find('div', class_=lambda c: c and 'event__participant--away' in c)
                        
                        home_team = home_elem.get_text(strip=True) if home_elem else "Unknown Home"
                        away_team = away_elem.get_text(strip=True) if away_elem else "Unknown Away"
                        matchup = f"{away_team} @ {home_team}"
                        
                        # Extract Channels
                        channels = []
                        channel_list = row.find('ul', class_='event__tags')
                        if channel_list:
                            for channel_link in channel_list.find_all('a'):
                                channel_name = channel_link.get('aria-label')
                                if channel_name:
                                    channels.append(channel_name)
                                    
                        all_games.append({
                            "Date": today.strftime("%Y-%m-%d"),
                            "Time": event_time,
                            "League": league_name,
                            "Matchup": matchup,
                            "Services": str(channels) # Storing as a string representation of the list
                        })
                        games_added += 1
                        
                except Exception as e:
                    print(f"Error parsing a game row in {league_name}: {e}")
                    continue
                    
            print(f"Added {games_added} {league_name} games for today.")
            
        await browser.close()
        print("\nFinished scraping all leagues. Parsing data...")

    # 5. Export Data
    df = pd.DataFrame(all_games)
    
    if not df.empty:
        filename = f"../data/livesports_schedule_{today.strftime('%Y-%m-%d')}.csv"
        df.to_csv(filename, index=False)
        print(f"Successfully pulled {len(all_games)} total games for today!")
        print(f"Data saved to {filename}")
    else:
        print("No games found for today across any of the specified leagues.")

if __name__ == "__main__":
    asyncio.run(scrape_league_schedules())