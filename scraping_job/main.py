import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import time
import random

try:
    from scraping_job.csv_extractor import extract_results_from_csv
except ImportError:
    from csv_extractor import extract_results_from_csv

def get_soup(url):
    """Get the BeautifulSoup object for a URL with headers to mimic a browser"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return BeautifulSoup(response.text, 'html.parser')

def extract_match_data(match):
    """Extract match data from a match element"""
    try:
        # Extract team names
        teams = [team.get_text(strip=True) for team in match.select('.matches__item-col--side')]
        if len(teams) != 2:
            return None
            
        home_team, away_team = teams[0], teams[1]
        
        # Extract score
        score_element = match.select_one('.matches__teamscores')
        if not score_element:
            return None
            
        score_parts = [p.get_text(strip=True) for p in score_element.select('span')]
        if len(score_parts) < 2:
            return None
            
        home_goals, away_goals = score_parts[0], score_parts[1]
        
        # Extract match date
        date_element = match.select_one('.matches__date')
        match_date = date_element.get('data-time') if date_element else None
        if match_date:
            try:
                match_date = datetime.fromisoformat(match_date.replace('Z', '+00:00'))
            except:
                match_date = datetime.now()
        else:
            match_date = datetime.now()
            
        return {
            'date': match_date,
            'home_team': home_team,
            'away_team': away_team,
            'home_goals': int(home_goals) if home_goals.isdigit() else None,
            'away_goals': int(away_goals) if away_goals.isdigit() else None
        }
    except Exception as e:
        print(f"Error extracting match data: {e}")
        return None

def scrape_premier_league_results():
    """Scrape Premier League results from Sky Sports"""
    url = "https://www.skysports.com/premier-league-results/2024-25"
    print(f"Scraping results from: {url}")
    
    try:
        soup = get_soup(url)
        matches = soup.select('.matches__item')
        
        if not matches:
            print("No matches found on the page")
            return []
            
        results = []
        for match in matches:
            match_data = extract_match_data(match)
            if match_data:
                results.append(match_data)
                
        print(f"Successfully extracted {len(results)} matches")
        return results
        
    except Exception as e:
        print(f"Error scraping results: {e}")
        return []

def main():
    print("Loading Premier League results from dataset...")
    start_time = time.time()
    
    try:
        # Web scraping code is kept as dead code for now:
        # results = scrape_premier_league_results()
        results = extract_results_from_csv()
        
        if results:
            # Convert to DataFrame for better display and analysis
            df = pd.DataFrame(results)
            df = df.sort_values('date')
            
            print(f"Successfully loaded {len(results)} matches.")
            print("\n=== Match Results (First 10) ===")
            print(df[['date', 'home_team', 'home_goals', 'away_goals', 'away_team']].head(10).to_string(index=False))
            
            # Save to CSV
            csv_filename = 'premier_league_results.csv'
            df.to_csv(csv_filename, index=False)
            print(f"\nResults saved to {csv_filename}")
        else:
            print("No results were found.")
            
    except Exception as e:
        print(f"\nAn error occurred: {e}")
        
    finally:
        print(f"\nScript completed in {time.time() - start_time:.2f} seconds")

if __name__ == "__main__":
    main()