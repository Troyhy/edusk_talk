# This is a sample Python script.

# Press Shift+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.
import re
from pprint import pprint
from time import sleep, time

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from retry import retry


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


def print_hi(name):
    # Use a breakpoint in the code line below to debug your script.
    print(f'Hi, {name}')  # Press Ctrl+F8 to toggle the breakpoint.

    desired_cap = {
        'browserName': 'android',
        'device': 'Samsung Galaxy Note 9',
        'realMobile': 'true',
        'os_version': '8.1',
        'name': 'Bstack-[Python] Sample Test'
    }

    driver = webdriver.Chrome('./chromedriver')  # Optional argument, if not specified will

    driver.get("https://www.eduskunta.fi/FI/search/Sivut/Vaskiresults.aspx")
    if not "Haku:" in driver.title:
        raise Exception("Unable to load google page!")

    page_settings = ['Asiakirjatyyppinimi_Link_Puheenvuoro', 'button-ValtiopaivavuosiTeksti2',
                     'ValtiopaivavuosiTeksti2_Link_2021', 'button-Puheenvuorotyyppi',
                     'Puheenvuorotyyppi_Link_Varsinainen_puheenvuoro']

    for button_name in page_settings:
        elem = wait_for(lambda: driver.find_element_by_id(button_name))
        elem.click()
        sleep(1)


def click_through_to_new_page(chromedriver, link_id):
    link = browser.find_element_by_link_text('my link')
    link.click()

    def link_has_gone_stale():
        try:
            # poll the link with an arbitrary call
            link.find_elements_by_id('doesnt-matter')
            return False
        except StaleElementReferenceException:
            return True

    wait_for(link_has_gone_stale)


def webdriver_init_page(chromedriver: WebDriver, url, settings):
    driver.get("https://www.eduskunta.fi/FI/search/Sivut/Vaskiresults.aspx")
    if not "Haku:" in driver.title:
        raise Exception("Unable to load google page!")

    for button_name in settings:
        print(f"trying to find button id:{button_name}")
        # with wait_for_page_load(chromedriver):
        elem = wait_for(lambda: chromedriver.find_element_by_id(button_name))
        print(f"pushing the button button id:{button_name}")
        elem.click()
        sleep(2)

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
        result_data.append( {
            'title': re.sub(' +', ' ', result.find('div', {'class': 'ms-srch-item-title'}).find('a').text),
            'link': result.find('div', {'class': 'ms-srch-item-title'}).find('a')['href'],
            'speaker': re.sub(' +', ' ', result.find('div', {'class': 'edk-srch-tmpl-puhuja'}).text),
            'intro': re.sub(' +', ' ', result.find('div', {'class': 'edk-srch-tmpl-puheenvuoro'}).text),
        })
    return result_data



# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    driver = webdriver.Chrome('./chromedriver')  # Optional argument, if not specified will

    url = "https://www.eduskunta.fi/FI/search/Sivut/Vaskiresults.aspx"
    page_settings = ['Asiakirjatyyppinimi_Link_Puheenvuoro', 'button-ValtiopaivavuosiTeksti2',
                     'ValtiopaivavuosiTeksti2_Link_2021', 'button-Puheenvuorotyyppi',
                     'Puheenvuorotyyppi_Link_Varsinainen_puheenvuoro']

    webdriver_init_page(chromedriver=driver, url=url, settings=page_settings)
    talks = []

    results = True
    try:
        while results:
            talks = talks + webdriver_scrape_talks(chromedriver=driver)
            results = navigate_to_next_results(driver)
            sleep(0.5)
            print(f'Gathered talks:{len(talks)}')
    except Exception as e:
        print(e)

    pprint(talks)