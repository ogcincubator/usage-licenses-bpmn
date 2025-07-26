import csv
import json
import re
from pathlib import Path

import requests
from rdflib import Graph, RDF, PROV
from pyld import jsonld

CONTEXT_URL = 'https://ogcincubator.github.io/usage-licensing/build/annotated/usage-project/licensing/prov/context.jsonld'

if __name__ == "__main__":

    r = requests.get(CONTEXT_URL)
    r.raise_for_status()
    frame_base = r.json()

    chains = {}

    for fn in Path('bpmn/ttl').glob('*.ttl'):
        g = Graph().parse(fn)
        jsong = json.loads(g.serialize(format='json-ld'))
        for s in g.subjects(predicate=RDF.type, object=PROV.Entity):
            if 'usage.geocat.live' not in str(s):
                continue

            uuid = re.sub(r'.*[#/]', '', str(s))
            frame = {
                **frame_base,
                '@id': str(s),
            }
            framed = jsonld.frame(jsong, frame)
            framed['@context'] = CONTEXT_URL
            chains[uuid] = framed

    with open('bpmn/provenance.json', 'w') as f:
        json.dump({uuid: json.dumps(frame) for uuid, frame in chains.items()}, f, indent=2)
