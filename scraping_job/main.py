from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time
import re
import datetime

RESULTS_URL = "https://www.premierleague.com/results"
BASE_STRENGTH = 1000
K = 10  # scaling factor for strength change

def extract_html_from_page(url):
    # Setup Chrome options
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920x1080")

    # Initialize WebDriver
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    driver.get(url)
    # Wait for the results container to appear
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "fixtures__matches-list"))
        )
        print("Initial results loaded!")
    except Exception as e:
        print("Error: Page took too long to load.")

    # Scroll to load all results
    last_height = driver.execute_script("return document.body.scrollHeight")
    while True:
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.END)  # Scroll to the bottom
        time.sleep(2)  # Wait for new results to load

        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:  # If no new content is loaded, stop scrolling
            break
        last_height = new_height

    print("All results loaded!")

    # Get the page source after JavaScript execution
    html = driver.page_source
    driver.quit()  # Close the browser

    soup = BeautifulSoup(html, "html.parser")
    # print(soup.prettify())  # Todo: remove later

    return soup

def extract_results_from_html(soup):
    results = []
    matches = soup.find_all("li", class_="match-fixture")
    for match in matches:
        home_team = match.get("data-home")
        away_team = match.get("data-away")
        status = match.get("data-comp-match-item-status")
        match_id = match.get("data-comp-match-item")
        venue = match.get("data-venue")
        ko_timestamp = match.get("data-comp-match-item-ko")
        kickoff_datetime = None
        if ko_timestamp:
            kickoff_datetime = datetime.datetime.fromtimestamp(int(ko_timestamp) // 1000)

        # Extract scores
        score_span = match.find("span", class_="match-fixture__score")
        if score_span:
            score_text = re.sub(r"\s+", "", score_span.get_text())
            home_goals, away_goals = map(int, score_text.split("-"))
        else:
            home_goals = away_goals = None

        results.append({
            "home_team": home_team,
            "away_team": away_team,
            "home_goals": home_goals,
            "away_goals": away_goals,
            "venue": venue,
            "status": status,
            "match_id": match_id,
            "kickoff_datetime": kickoff_datetime
        })

    print(results[0])  # Print the first result for verification
    print(f"Total matches found: {len(results)}")
    return results

def calculate_team_strengths(results):
    team_strengths = {}
    strength_history = []

    for match in sorted(results, key=lambda x: x['kickoff_datetime']):
        home = match['home_team']
        away = match['away_team']
        home_goals = match['home_goals']
        away_goals = match['away_goals']
        date = match['kickoff_datetime']

        # Initialize strengths if not present
        if home not in team_strengths:
            team_strengths[home] = BASE_STRENGTH
        if away not in team_strengths:
            team_strengths[away] = BASE_STRENGTH

        # Calculate strength change
        home_gain = K * home_goals * (team_strengths[away] / BASE_STRENGTH)
        away_gain = K * away_goals * (team_strengths[home] / BASE_STRENGTH)

        team_strengths[home] += home_gain
        team_strengths[away] += away_gain

        # Record strengths after this match
        strength_history.append({
            'date': date,
            'team': home,
            'strength': team_strengths[home]
        })
        strength_history.append({
            'date': date,
            'team': away,
            'strength': team_strengths[away]
        })

    return strength_history

results_html = extract_html_from_page(RESULTS_URL)
results = extract_results_from_html(results_html)
strength_history = calculate_team_strengths(results)
print(strength_history[:5])  # See first few records

