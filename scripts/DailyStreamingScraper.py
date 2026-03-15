import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime

async def scrape_livesports():
    base_url = "https://www.livesportsontv.com"
    all_games = []
    
    async with async_playwright() as p:
        print("Launching browser...")
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # 1. Go to the main page to find the calendar links
        await page.goto(base_url)
        print("Fetching calendar links...")
        
        # Grab the 'href' from just the FIRST calendar item (Today)
        hrefs = await page.evaluate('''() => {
            const links = Array.from(document.querySelectorAll('a.calendar__item'));
            return links.slice(0, 1).map(a => a.getAttribute('href'));
        }''')
        
        print(f"Found {len(hrefs)} day to scrape. Starting loop...\n")

        # 2. Loop through the single day (kept as a loop in case you expand later)
        for i, href in enumerate(hrefs):
            # Construct the full URL for the day
            day_url = f"{base_url}{href}" if href.startswith('/') else f"{base_url}/{href}"
            print(f"--- Scraping Today: {day_url} ---")
            
            # Navigate to the specific day's page
            await page.goto(day_url)

            # Scroll to load all dynamic content for THIS day
            last_height = await page.evaluate("document.body.scrollHeight")
            while True:
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(2000) 
                
                new_height = await page.evaluate("document.body.scrollHeight")
                if new_height == last_height:
                    break 
                last_height = new_height

            # Grab the fully loaded HTML for this specific day
            html_content = await page.content()
            soup = BeautifulSoup(html_content, 'html.parser')

            # Extract the Date
            active_date_element = soup.find('a', class_='calendar__item--active')
            game_date = active_date_element.get('id') if active_date_element else "Date Not Found"
            print(f"Extracting games for date: {game_date}")

            # Extract the events using BeautifulSoup
            event_containers = soup.find_all('div', class_='events')

            for container in event_containers:
                league_tag = container.find_previous_sibling('a', href=lambda href: href and '/league/' in href)
                if league_tag and league_tag.get_text(strip=True):
                    league = league_tag.get_text(strip=True)
                elif league_tag:
                    league = league_tag.get('href').split('/')[-1].upper().replace('-', ' ')
                else:
                    fallback = container.find_previous('a', href=lambda href: href and '/league/' in href)
                    league = fallback.get_text(strip=True) if fallback else "Unknown League"

                game_rows = container.find_all('div', class_='event--wrapp')

                for row in game_rows:
                    try:
                        time_div = row.find('div', class_='event__info--time')
                        event_time = time_div.find('time').get_text(strip=True) if time_div and time_div.find('time') else "Time Not Found"

                        match_info = row.find('div', class_='event__matchInfo')
                        match_link = match_info.find('a') if match_info else None
                        teams = match_link.get_text(separator=" ", strip=True) if match_link else ""
                        
                        if not teams and match_link:
                            slug = match_link.get('href', '')
                            teams = slug.split('/')[-1].rsplit('-', 1)[0].replace('-', ' ').title()

                        channels = []
                        channel_list = row.find('ul', class_='event__tags')
                        
                        if channel_list:
                            for channel_link in channel_list.find_all('a'):
                                channel_name = channel_link.get('aria-label')
                                if channel_name:
                                    channels.append(channel_name)

                        all_games.append({
                            "Date": game_date,
                            "Time": event_time,
                            "League": league,
                            "Matchup": teams or "Unknown Matchup",
                            "Services": ", ".join(channels)
                        })
                        
                    except Exception as e:
                        print(f"Error parsing game row: {e}")
                        continue
            
            print(f"Finished {game_date}.\n")

        # Close the browser once the loop finishes
        await browser.close()
        print("Finished scrolling today's schedule. Parsing data...")

    # 3. Export the Data with Today's Date in the Filename
    df = pd.DataFrame(all_games)
    
    # Format today's date as YYYY-MM-DD
    today_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"../data/livesports_schedule_{today_str}.csv"
    
    df.to_csv(filename, index=False)
    print(f"\nSuccessfully pulled {len(all_games)} games for today!")
    print(f"Data saved to {filename}")

# This tells Python to run the async function when you execute the script
if __name__ == "__main__":
    asyncio.run(scrape_livesports())