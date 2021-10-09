# This is a sample Python script.

# Press Shift+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.
import os
import re
from dataclasses import dataclass
from pprint import pprint
from time import sleep, time
from typing import Optional, List

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException, \
    ElementNotInteractableException
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from retry import retry


@dataclass
class PageButton:
    id_to_click: str
    id_to_wait: Optional[str] = None
    delay: int = 0


class wait_for_page_load(object):
    def __init__(self, browser):
        self.browser = browser

    def __enter__(self):
        self.old_page = self.browser.find_element_by_tag_name('html')

    def page_has_loaded(self):
        new_page = self.browser.find_element_by_tag_name('html')
        return new_page.id != self.old_page.id

    def __exit__(self, *_):
        wait_for(self.page_has_loaded)


def wait_for(condition_function):
    start_time = time()
    while time() < start_time + 10:
        try:
            if retval := condition_function():
                return retval
            else:
                print(f"rrr {retval}")
        except NoSuchElementException:
            pass
        finally:
            sleep(0.1)

    raise Exception(
        'Timeout waiting for {}'.format(condition_function.__name__)
    )


def click_through_to_new_page(chromedriver: WebDriver, link_id):
    # click link and detect when page changes
    link = chromedriver.find_element_by_id(link_id)
    link.click()

    def link_has_gone_stale():
        try:
            # poll the link with an arbitrary call
            link.find_elements_by_id('doesnt-matter')
            return False
        except StaleElementReferenceException:
            return True

    wait_for(link_has_gone_stale)


def webdriver_init_page(chromedriver: WebDriver, url, settings: List[PageButton]):
    driver.get(url)

    if not "Haku:" in driver.title:
        raise Exception("Unable to load google page!")

    @retry((StaleElementReferenceException,ElementNotInteractableException), delay=0.2, tries=5)
    def handle_button_press():
        print(f"trying to find button id:{page_button.id_to_click}")
        elem = wait_for(lambda: chromedriver.find_element_by_id(page_button.id_to_click))
        print(f"pushing the button button id:{page_button.id_to_click}")
        elem.click()
        print(f"waiting resulting id to appear id:{page_button.id_to_wait}")
        wait_for(lambda: chromedriver.find_element_by_id(page_button.id_to_wait))
        print("---")

    for page_button in settings:
        handle_button_press()
        if page_button.delay:
            sleep(page_button.delay)

    return driver


@retry((StaleElementReferenceException,), delay=1, tries=3)
def navigate_to_next_results(chromedriver: WebDriver, next_button='PageLinkNext'):
    next = wait_for(lambda: chromedriver.find_element_by_id(next_button))

    if next:
        next.send_keys(Keys.END)
        next.click()
        return True
    return False


def webdriver_scrape_talks(chromedriver: WebDriver):
    results = chromedriver.find_element_by_class_name('ms-srch-group')
    soup = BeautifulSoup(results.get_attribute('innerHTML'), 'html.parser')

    search_results = soup.find_all('div', {'name': 'Item'})
    result_data = []
    for result in search_results:
        result_data.append({
            'title': re.sub(' +', ' ', result.find('div', {'class': 'ms-srch-item-title'}).find('a').text),
            'link': result.find('div', {'class': 'ms-srch-item-title'}).find('a')['href'],
            'speaker': re.sub(' +', ' ', result.find('div', {'class': 'edk-srch-tmpl-puhuja'}).text),
            'intro': re.sub(' +', ' ', result.find('div', {'class': 'edk-srch-tmpl-puheenvuoro'}).text),
        })
    return result_data


def results_to_csv(results, filename):
    import csv

    fieldnames = results[0].keys()

    with open(filename, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in results:
            writer.writerow(row)


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    driver = webdriver.Chrome('./chromedriver')  # Optional argument, if not specified will

    url = "https://www.eduskunta.fi/FI/search/Sivut/Vaskiresults.aspx"
    page_button_settings = [
        PageButton('Asiakirjatyyppinimi_Link_Puheenvuoro', 'Asiakirjatyyppinimi_ChkGroup_Puheenvuoro_ContentLink', 0.2),
        PageButton('button-ValtiopaivavuosiTeksti2', 'ValtiopaivavuosiTeksti2_Link_2021', 0),
        PageButton('ValtiopaivavuosiTeksti2_Link_2021', 'ValtiopaivavuosiTeksti2_ChkGroup_2021_ContentLink', 0.5),
        PageButton('button-Puheenvuorotyyppi', 'Puheenvuorotyyppi_Link_Varsinainen_puheenvuoro', 0),
        PageButton('Puheenvuorotyyppi_Link_Varsinainen_puheenvuoro', 'PageLinkNext', 0),
    ]

    webdriver_init_page(chromedriver=driver, url=url, settings=page_button_settings)
    talks = []

    more_results = True
    try:
        while more_results:
            talks = talks + webdriver_scrape_talks(chromedriver=driver)
            more_results = navigate_to_next_results(driver)
            sleep(0.5)
            print(f'Gathered talks:{len(talks)}')
    except Exception as e:
        print(e)

    results_to_csv(talks, os.path.join('test_runs', 'puheet.csv'))
