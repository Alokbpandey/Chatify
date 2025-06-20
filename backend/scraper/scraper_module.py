import json
import logging
import re
import os
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

class WebScraper:
    def __init__(self,
                 json_file='chatpy/backend/data/crawled_links.json',
                 output_file='chatpy/backend/data/extracted_text_data.json',
                 raw_output='chatpy/backend/data/raw_html_css_data.json'):
        self.json_file = json_file
        self.text_output = output_file
        self.raw_output = raw_output
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
        }
        self.skip_ext = ('.pdf', '.jpg', '.jpeg', '.png', '.gif',
                         '.zip', '.mp4', '.avi', '.mp3')

    def load_links(self):
        try:
            with open(self.json_file, encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            logging.error(f"Couldn’t load {self.json_file}: {e}")
            return []

        if isinstance(data, dict):
            for key in ('all_discovered_links', 'crawled_pages', 'all_links'):
                if key in data and isinstance(data[key], list):
                    return list({u for u in data[key] if isinstance(u, str)})
            if 'page_details' in data and isinstance(data['page_details'], dict):
                return list(data['page_details'].keys())
        elif isinstance(data, list):
            return [u for u in data if isinstance(u, str)]
        return []

    def clean_text(self, html):
        text = BeautifulSoup(html, 'html.parser') \
                       .get_text(separator=' ', strip=True)
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'(Skip to content|Cookie policy|Privacy policy)', '', text, flags=re.I)
        sents = [s.strip() for s in re.split(r'[.!?]+', text)]
        sents = [s for s in sents if 20 <= len(s) <= 300]
        return '. '.join(dict.fromkeys(sents)) + ('.' if sents else '')

    def extract_clean(self, url):
        try:
            r = requests.get(url, headers=self.headers, timeout=15)
            r.raise_for_status()
            html = r.text
            soup = BeautifulSoup(html, 'html.parser')
            title = soup.title.string.strip() if soup.title and soup.title.string else ''
            cleaned = self.clean_text(html)
            return {
                'url': url,
                'domain': urlparse(url).netloc,
                'title': title,
                'text': cleaned,
                'length': len(cleaned),
                'status': 'success'
            }
        except Exception as e:
            logging.warning(f"Clean extract failed ({url}): {e}")
            return {'url': url, 'domain': urlparse(url).netloc, 'text': '', 'status': 'error'}

    def extract_raw(self, url):
        try:
            r = requests.get(url, headers=self.headers, timeout=15)
            r.raise_for_status()
            html = r.text
            soup = BeautifulSoup(html, 'html.parser')

            css = []
            for tag in soup.find_all(('style', 'link')):
                if tag.name == 'style':
                    css.append(tag.get_text())
                elif tag.name == 'link' and tag.get('rel') == ['stylesheet']:
                    href = tag.get('href')
                    if href and not href.startswith('data:'):
                        try:
                            css.append(requests.get(
                                requests.compat.urljoin(url, href),
                                timeout=10).text)
                        except: pass

            js = []
            for tag in soup.find_all('script'):
                if tag.get('src'):
                    try:
                        js.append(requests.get(
                            requests.compat.urljoin(url, tag['src']),
                            timeout=10).text)
                    except: pass
                elif tag.string:
                    js.append(tag.string)

            return {
                'url': url,
                'domain': urlparse(url).netloc,
                'html': html,
                'css': '\n'.join(css),
                'js': '\n'.join(js),
                'status': 'success'
            }
        except Exception as e:
            logging.warning(f"Raw extract failed ({url}): {e}")
            return {'url': url, 'domain': urlparse(url).netloc, 'html': '', 'css': '', 'js': '', 'status': 'error'}

    def save(self, data, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logging.info(f"Saved {len(data)} records to {path}")

    def run(self):
        links = self.load_links()
        if not links:
            logging.error("No links to process.")
            return

        logging.info(f"Processing {len(links)} links...")

        text_data = [self.extract_clean(u) for u in links]
        self.save(text_data, self.text_output)

        raw_data = [self.extract_raw(u) for u in links]
        self.save(raw_data, self.raw_output)


if __name__ == '__main__':
    print("Running scraper module...")
    WebScraper().run()
