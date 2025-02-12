from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time

RESULTS_URL = "https://www.premierleague.com/results"


def extract_html_from_page(url):
    # Setup Chrome options
    options = Options()
    options.add_argument("--headless")  # Run Chrome in headless mode (no UI)
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

    # time.sleep(5)

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

    # Parse with BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    print(soup.prettify())  # Todo: remove later

    return

extract_html_from_page(RESULTS_URL)