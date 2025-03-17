import sys
from pathlib import Path

from rdflib import Graph, URIRef, BNode, RDFS, Literal, Namespace
from rdflib.namespace import RDF, PROV
from lxml import etree
from bs4 import BeautifulSoup, NavigableString

ENTITY_SHAPE = 'mxgraph.bpmn.data'
MERGE_SHAPE = 'mxgraph.bpmn.gateway2'
ACTIVITY_SHAPE = 'mxgraph.bpmn.task'
USED_SHAPES = {ENTITY_SHAPE, MERGE_SHAPE, ACTIVITY_SHAPE}

EX = Namespace('http://example.org/usage/prov/')

html_parser = etree.HTMLParser()


def extract_label(label: str):
    if not label:
        return None, []

    soup = BeautifulSoup(label, 'html.parser')

    for tag in soup.find_all(True):

        if ''.join(str(c) for c in tag.children if isinstance(c, NavigableString)).strip().startswith('%3CmxGraphModel'):
            tag.decompose()
    for tag in soup.find_all(True):
        if tag.name != 'a' or not tag.attrs.get('href'):
            tag.unwrap()

    first_link = soup.find_next('a')
    links = []
    if first_link:
        if '/srv/' in first_link['href']:
            links.append({'href': first_link['href'], 'text': first_link.get_text(strip=True)})
            for sibling in first_link.next_siblings:
                if sibling.name == 'a':
                    links.append({'href': sibling['href'], 'text': sibling.get_text(strip=True)})
                sibling.extract()
            first_link.extract()

    if not links:
        for a in soup.find_all('a'):
            a.replace_with(soup.new_string(f"{a.get_text()} ({a['href']})"))

    return soup.get_text().strip(), links


def to_uri(s: str):
    if '#/metadata/' in s:
        root, dataset_id = s.split('#/metadata/', 1)
        base, _ = root.split('/srv/', 1)
        s = f"{base}/srv/api/records/{dataset_id}"
    return URIRef(s)

def create_graphs(fn: Path):
    doc = etree.parse(fn)
    root = doc.getroot()

    graphs = []
    skipped_nodes = set()
    diagrams = root.findall("./diagram")
    for diagram in diagrams:
        nodes = {}
        g = Graph()
        for e in diagram.findall('.//*[@vertex="1"]'):
            node_id = e.get('id') or e.getparent().get('id')
            style = dict(x.split('=') for x in e.get('style').split(';') if '=' in x)
            shape = style.get('shape')
            if not shape or shape not in USED_SHAPES:
                skipped_nodes.add(node_id)
                continue

            label = e.get('value') or e.getparent().get('label')
            parsed_label, links = extract_label(label)

            node = {
                'shape': shape,
                'label': parsed_label,
                'type': PROV.Activity,
                'otherTypes': [],
                'uri': None,
            }

            if shape == ENTITY_SHAPE:
                node['type'] = PROV.Entity
                if links:
                    node['uri'] = links[0]['href']

            elif shape == MERGE_SHAPE:
                node['label'] = 'Merge entities'
                node['otherTypes'].append(EX.MergeActivity)

            elif shape == ACTIVITY_SHAPE:
                node['agents'] = [{'uri': l['href'], 'label': l['text']} for l in links]

            node['resource'] = to_uri(node['uri']) if node['uri'] else BNode()

            g.add((node['resource'], RDFS.label, Literal(node['label'])))
            g.add((node['resource'], RDF.type, node['type']))

            for agent in node.get('agents', []):
                agent_uri = to_uri(agent['uri'])
                g.add((agent_uri, RDF.type, PROV.SoftwareAgent))
                g.add((agent_uri, RDF.type, PROV.Agent))
                g.add((agent_uri, RDFS.label, Literal(agent['label'])))
                g.add((node['resource'], PROV.wasAssociatedWith, agent_uri))

            for other_type in node.get('otherTypes', []):
                g.add((node['resource'], RDF.type, other_type))

            nodes[node_id] = node

        for e in diagram.findall('.//*[@edge="1"]'):
            source, target = e.get('source'), e.get('target')
            if not source or not target:
                print(f"WARNING: Edge {e.get('id')} has source={source}, target={target}", file=sys.stderr)
                continue
            if source in skipped_nodes or target in skipped_nodes:
                # Skipping events
                continue

            source_node, target_node = nodes.get(source), nodes.get(target)
            if not source_node or not target_node:
                print(f"WARNING: Edge {e.get('id')} has source_node={source_node}, target_node={target_node}", file=sys.stderr)
                continue

            if source_node['type'] == PROV.Entity and target_node['type'] == PROV.Activity:
                g.add((target_node['resource'], PROV.used, source_node['resource']))
            elif source_node['type'] == PROV.Activity and target_node['type'] == PROV.Entity:
                g.add((target_node['resource'], PROV.wasGeneratedBy, source_node['resource']))
            elif source_node['type'] == PROV.Activity and target_node['type'] == PROV.Activity:
                g.add((target_node['resource'], PROV.wasInformedBy, source_node['resource']))
            else:
                print(f"WARNING: Unexpected source and target type combination"
                      f" for {e.get('id')}: source={source_node['type']}, target={target_node['type']}",
                      file=sys.stderr)

        if g:
            graphs.append(g)

    return graphs


def _main():
    filenames = sys.argv[1:] or Path('bpmn').glob('*.drawio')
    for fn in filenames:
        fn = Path(fn)
        for i, graph in enumerate(create_graphs(fn)):
            graph.serialize(fn.with_stem(fn.stem + f"_{i}").with_suffix('.ttl'), format='ttl')

if __name__ == "__main__":
    _main()