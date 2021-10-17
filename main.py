import csv
import getopt
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from io import StringIO
from time import sleep, time
from typing import Optional, List, Union

from bs4 import BeautifulSoup
from retry import retry
from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    ElementNotInteractableException, WebDriverException,
)
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.keys import Keys


@dataclass
class PageButton:
    """
    Dataclass to represent buttons on a webpage.
    """
    id_to_click: str
    id_to_wait: Optional[str] = None
    delay: Union[int, float] = 0


@dataclass
class PageUrl:
    url: str


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


def wait_for(condition_function, max_wait=10):
    """
    utility to wait for condition function to return truthty value
    :param max_wait: max wait time before giving up
    :param condition_function:
    :return:
    """

    start_time = time()
    while time() < start_time + max_wait:
        try:
            if retval := condition_function():
                return retval
            else:
                pass
        except NoSuchElementException:
            pass
        finally:
            sleep(0.2)

    raise Exception('Timeout waiting for {}'.format(condition_function.__name__))


def click_through_to_new_page(chromedriver: WebDriver, link_id, id_to_refresh=None):
    # click link and detect when page changes
    link = wait_for(lambda: chromedriver.find_element_by_id(link_id))
    if id_to_refresh:
        wait_to_refresh = chromedriver.find_element_by_id(id_to_refresh)
    else:
        wait_to_refresh = link

    link.click()

    def link_has_gone_stale():
        try:
            # poll the link with an arbitrary call
            wait_to_refresh.find_elements_by_id('doesnt-matter')
            return False
        except StaleElementReferenceException:
            return True

    wait_for(link_has_gone_stale)


def webdriver_init_page(chromedriver: WebDriver, settings: List[Union[PageButton, PageUrl]]):
    """
    Load page and click trough initial button configurations
    :param chromedriver:
    :param settings:
    :return:
    """

    #
    page_url = [page_url for page_url in settings if isinstance(page_url, PageUrl)][0]

    with wait_for_page_load(chromedriver):
        chromedriver.get(page_url.url)

    @retry((StaleElementReferenceException, ElementNotInteractableException), delay=1, tries=5)
    def handle_button_press():
        print(f'trying to find button: {page_button.id_to_click}')
        elem = wait_for(lambda: chromedriver.find_element_by_css_selector(page_button.id_to_click))
        print(f'pushing the button button: {page_button.id_to_click}')
        elem.click()
        if page_button.id_to_wait:
            print(f'waiting resulting id to appear id: {page_button.id_to_wait}')
            wait_for(lambda: chromedriver.find_element_by_css_selector(page_button.id_to_wait))
        print('---')

    for page_button in settings:
        if not isinstance(page_button, PageButton):  # skip the PageUrl
            continue
        handle_button_press()
        if page_button.delay:
            sleep(page_button.delay)

    return chromedriver


@retry((StaleElementReferenceException,), delay=1, tries=5)
def navigate_to_next_results(chromedriver: WebDriver, next_button='PageLinkNext'):
    """
    Find next button and click it.
    :param chromedriver:
    :param next_button:
    :return:
    """
    next = wait_for(lambda: chromedriver.find_element_by_id(next_button))
    if next:
        next.send_keys(Keys.END)
        next.click()
        return True
    return False


def webdriver_scrape_talks(chromedriver: WebDriver):
    """
    find all talks in page and extract data from those
    :param chromedriver:
    :return: list of dicts with data scraped
    """

    results = chromedriver.find_element_by_class_name('ms-srch-group')
    soup = BeautifulSoup(results.get_attribute('innerHTML'), 'html.parser')
    search_results = soup.find_all('div', {'name': 'Item'})
    result_data = []
    for result in search_results:
        result_data.append(
            {
                'title': re.sub(' +', ' ', result.find('div', {'class': 'ms-srch-item-title'}).find('a').text),
                'date': re.sub(' +', ' ', result.find('div', {'class': 'ms-srch-item-summary'}).text),
                'link': result.find('div', {'class': 'ms-srch-item-title'}).find('a')['href'],
                'speaker': re.sub(' +', ' ', result.find('div', {'class': 'edk-srch-tmpl-puhuja'}).text),
                'intro': re.sub(' +', ' ', result.find('div', {'class': 'edk-srch-tmpl-puheenvuoro'}).text),
            }
        )
    return result_data


def results_to_csv(results: List[dict], filename):
    """
    Save results to cvs format to filename. first element is used for fieldnames.
    :param results: scraped results
    :param filename: file to write csv
    :return: None
    """
    with open(filename, 'w', newline='') as csvfile:
        _results_to_stream(results, csvfile)


def results_to_stdout(results: List[dict]):
    """
    Save results to cvs format to filename. first element is used for fieldnames.
    :param results: scraped results
    :return: None
    """
    _results_to_stream(results, sys.stdout)


def _results_to_stream(results: List[dict], stream: StringIO):
    fieldnames = results[0].keys()
    writer = csv.DictWriter(stream, fieldnames=fieldnames)
    writer.writeheader()
    for row in results:
        writer.writerow(row)


def dedup_results(talks):
    import pandas as pd
    return pd.DataFrame(talks).drop_duplicates('title').to_dict('records')


# settings for eduskunta page initialization
setting_groups = {
    'puheet-2021': [
        PageUrl('https://www.eduskunta.fi/FI/search/Sivut/Vaskiresults.aspx'),
        PageButton('.btn-consent-reject', delay=1),
        PageButton('#Asiakirjatyyppinimi_Link_Puheenvuoro', '#Asiakirjatyyppinimi_ChkGroup_Puheenvuoro_ContentLink',
                   2),
        PageButton('#button-ValtiopaivavuosiTeksti2', '#ValtiopaivavuosiTeksti2_Link_2021', 0),
        PageButton('#ValtiopaivavuosiTeksti2_Link_2021', '#ValtiopaivavuosiTeksti2_ChkGroup_2021_ContentLink', 0.5),
        PageButton('#button-Puheenvuorotyyppi', '#Puheenvuorotyyppi_Link_Varsinainen_puheenvuoro', 0),
        PageButton('#Puheenvuorotyyppi_Link_Varsinainen_puheenvuoro', '#PageLinkNext', 0),
    ],
    'puheet-2020': [
        PageUrl('https://www.eduskunta.fi/FI/search/Sivut/Vaskiresults.aspx'),
        PageButton('.btn-consent-reject', delay=1),
        PageButton('#Asiakirjatyyppinimi_Link_Puheenvuoro', '#Asiakirjatyyppinimi_ChkGroup_Puheenvuoro_ContentLink',
                   2),
        PageButton('#button-ValtiopaivavuosiTeksti2', '#ValtiopaivavuosiTeksti2_Link_2020', 0),
        PageButton('#ValtiopaivavuosiTeksti2_Link_2020', '#ValtiopaivavuosiTeksti2_ChkGroup_2020_ContentLink', 0.5),
        PageButton('#button-Puheenvuorotyyppi', '#Puheenvuorotyyppi_Link_Varsinainen_puheenvuoro', 0),
        PageButton('#Puheenvuorotyyppi_Link_Varsinainen_puheenvuoro', '#PageLinkNext', 0),
    ]

}


def main(argv):
    try:
        opts, args = getopt.getopt(argv, "hs:d:r:o:e:", ["--driver-path", "--driver-remote"])
    except getopt.GetoptError:
        print('test.py -s <talk-setting> -c <chromedriver_path>')
        sys.exit(2)

    # set default setting
    talk_setting_name = list(setting_groups.keys())[0]
    chromedriver_path = os.environ.get('CHROMEDRIVER_PATH')
    chromedriver_remote = os.environ.get('CHROMEDRIVER_REMOTE')
    output_path = None
    stop_after = 0

    for opt, arg in opts:
        if opt == '-h':
            print('test.py -s <talk-setting>')
            print(f"where <talk-settings>, use one of these:{list(setting_groups.keys())}")
            sys.exit()
        elif opt in ("-s",):
            if arg in setting_groups.keys():
                talk_setting_name = arg
            else:
                print(f"unrecognized <talk-setting>, use one of these:{list(setting_groups.keys())}")
                sys.exit(1)
        elif opt in ("-c", "--driver-path"):
            chromedriver_path = arg
        elif opt in ("-r", "--driver-remote"):
            chromedriver_remote = arg
        elif opt in ("-e",):
            stop_after = int(arg)
        elif opt in ("-o"):
            if (output_path := arg) == '-':
                std_output = True

    # start fetching data

    if not chromedriver_path and not chromedriver_remote:
        chromedriver_path = './chromedriver'
        # sys.stderr.write('error: chromedriver path or remote must be defined')
        # sys.exit(1)

    chrome_options = webdriver.ChromeOptions()
    if chromedriver_path:

        print("Using local Chrome executor")
        _chrome_args = (
            '--window-size=1920x1080',
        )
        for argument in _chrome_args:
            chrome_options.add_argument(argument)
        driver = webdriver.Chrome(executable_path=chromedriver_path, options=chrome_options)
    else:
        print("Using remote Chrome executor")
        _chrome_args = (
            '--headless', '--disable-gpu',
            #            '--incognito',
            '--disable-dev-shm-usage',
            '--window-size=1920x1080',
            'user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.81 Safari/537.36'
        )
        for argument in _chrome_args:
            chrome_options.add_argument(argument)

        @retry(delay=1, tries=3)
        def _get_driver():
            return  webdriver.Remote(command_executor=chromedriver_remote, options=chrome_options)

        driver = _get_driver()


    talks = []
    webdriver_init_page(chromedriver=driver, settings=setting_groups[talk_setting_name])

    more_results = True
    try:
        while more_results:
            talks = talks + webdriver_scrape_talks(chromedriver=driver)
            more_results = navigate_to_next_results(driver)
            if stop_after and stop_after < len(talks):
                break
            sleep(0.5)
            print(f'Gathered talks:{len(talks)}')
    except WebDriverException as e:
        print(f'Failen with error:{e}')
        with open(os.path.join('test_runs', 'error.png')) as f:
            f.write(driver.get_screenshot_as_png())
    except Exception as e:
        print(e)

    print('---' * 10)
    print(f'Gathered talks:{len(talks)}')
    talks = dedup_results(talks)
    print(f'Gathered talks after dedup:{len(talks)}')

    timestamp = datetime.now().astimezone().isoformat(timespec='seconds')
    if output_path == '-':
        results_to_stdout(talks)
    else:
        results_to_csv(talks, os.path.join(output_path or 'test_runs', f'{talk_setting_name}_{timestamp}.csv'))


if __name__ == '__main__':
    try:
        main(sys.argv[1:])
    except WebDriverException as e:
        print(e)
