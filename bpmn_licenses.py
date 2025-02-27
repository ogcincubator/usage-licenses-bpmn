import csv
import re
import sys
from pathlib import Path
from time import sleep
from typing import Generator

import requests
from bs4 import BeautifulSoup
from lxml import etree
from rdflib import Graph, DCTERMS

html_parser = etree.HTMLParser()

def extract_licenses(fn: Path) -> Generator[dict, None, None]:
    links = set()
    doc = etree.parse(fn)
    root = doc.getroot()
    objects = root.cssselect('UserObject[label]')
    throttle = False

    result = []

    for object in objects:
        label = etree.fromstring(object.get('label'), parser=html_parser)
        for a in label.cssselect('a[href]'):
            links.add(a.get('href'))

    for link in links:
        if not '/srv/' in link:
            print('Skipping {}'.format(link), file=sys.stderr)
            continue

        if throttle:
            sleep(0.3)
        else:
            throttle = True

        srv_url = re.sub(r'/srv/.*$', '/srv', link)
        dataset_id = re.search(r'([a-z0-9]+-)+[a-z0-9]+', link, flags=re.IGNORECASE).group(0)
        url = f"{srv_url}/eng/csw"
        params = {
            'REQUEST': 'GetRecordById',
            'SERVICE': 'CSW',
            'version': '2.0.2',
            'outputSchema': 'http://www.w3.org/ns/dcat#',
            'Id': dataset_id,
        }

        row = {
            'id': dataset_id,
            'url': f"{srv_url}/eng/catalog.search#/metadata/{dataset_id}",
        }
        try:
            r = requests.get(url, params=params)
            error = None
            if not r.ok:
                print(f'Error fetching dataset {dataset_id} from {srv_url}: {r.status_code} {r.reason}', file=sys.stderr)
                error = f'HTTP Error: {r.status_code} {r.reason}'

            if not error:
                resp = etree.fromstring(r.content)
                if etree.QName(resp).localname == 'ExceptionReport':
                    error = ''.join(resp.itertext()).strip()
                elif not len(resp.getchildren()):
                    error = 'No description could be retrieved'

                if error:
                    print(f"Error fetching dataset {dataset_id} from {srv_url}: {error}", file=sys.stderr)
                    result.append({
                        'id': dataset_id,
                        'error': ''.join(resp.itertext()).strip()
                    })
                else:
                    rdf_elem = resp.getchildren()[0]
                    g = Graph().parse(data=etree.tostring(rdf_elem).decode('utf-8'), format='xml')
                    licenses = [str(l) for l in g.objects(predicate=DCTERMS.license) if str(l) and str(l) not in ('license',)]
                    title = next(g.objects(predicate=DCTERMS.title), None)
                    if title:
                        title = str(title).strip()
                    row['title'] = title
                    row['licenses'] = '\n'.join(licenses)
            row['error'] = error
            yield row
        except Exception as e:
            print(f'Error processing dataset {dataset_id} from {fn}: {e}', file=sys.stderr)
            raise e

def _main():
    if len(sys.argv) < 2:
        print('Usage: bpmn_extract.py <bpmn1.drawio> [ <bpmn2.drawio> ...]', file=sys.stderr)
        sys.exit(1)

    writer = csv.DictWriter(sys.stdout, fieldnames=['bpmn', 'id', 'url', 'title', 'licenses', 'error'])
    writer.writeheader()

    for fn in sys.argv[1:]:
        fn = Path(fn)
        for row in extract_licenses(fn):
            row['bpmn'] = fn.name
            writer.writerow(row)


if __name__ == '__main__':
    _main()