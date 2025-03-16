import argparse
import json
import sys

from rdflib import Graph
from pyld import jsonld

def _main():

    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="Input TTL file")
    parser.add_argument("uri", nargs='?', help="URI for root RDF resource")
    parser.add_argument("-c", "--keep-context", action='store_true',
                        help="Do not remove JSON-LD context from output")
    args = parser.parse_args()

    g = Graph().parse(args.input)
    doc = json.loads(g.serialize(format='json-ld'))

    with open('prov-context.jsonld') as f:
        context = json.load(f)

    if args.uri:
        context['@id'] = args.uri
    else:
        context['@type'] = 'http://www.w3.org/ns/prov#Entity'

    output = jsonld.frame(doc, context)
    if not args.keep_context:
        output.pop('@context', None)
        if '@graph' in output:
            output = output['@graph']
    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    _main()