import html
import sys
import textwrap

from rdflib import Graph, PROV, RDF, RDFS, Literal

PROV_TYPES = [PROV.Entity, PROV.Activity, PROV.Agent]

NODE_TPL = '''{nodeid} [ shape=none, color=black label=< <table color='#666666' cellborder='0' cellspacing='0' border='1'><tr><td colspan='2' bgcolor='grey'><B>{title}</B></td></tr><tr><td bgcolor='#eeeeee' colspan='2'><font point-size='10' color='#6666ff'>{type}</font></td></tr><tr><td href='{url}' bgcolor='#eeeeee' colspan='2'><font point-size='10' color='#6666ff'>{url}</font></td></tr></table> > ]'''
NODE_NO_URL_TPL = '''{nodeid} [ shape=none, color=black label=< <table color='#666666' cellborder='0' cellspacing='0' border='1'><tr><td colspan='2' bgcolor='grey'><B>{title}</B></td></tr><tr><td bgcolor='#eeeeee' colspan='2'><font point-size='10' color='#6666ff'>{type}</font></td></tr></table> > ]'''
EDGE_TPL = '''{a} -> {b} [ color=BLACK, label=< <font point-size='10' color='#336633'>{prop}</font> > ] ;'''


def _main():
    g = Graph().parse(sys.argv[1])
    node_count = 0
    nodes = {}
    edges = []
    dot = []
    for t in PROV_TYPES:
        for s in g.subjects(predicate=RDF.type, object=t, unique=True):
            node_count += 1
            nid = f"node{node_count}"
            nodes[s] = nid
            label = html.escape(str(g.value(subject=s, predicate=RDFS.label, default=Literal(str(s)))))
            if len(label) > 70:
                label = '<BR/>'.join(textwrap.wrap(label, 70))
            node_type = str(t).replace(str(PROV), '')
            dot.append(NODE_NO_URL_TPL.format(nodeid=nid, title=label, type=node_type, url=str(s)))
            for prop, object in g.predicate_objects(s):
                if str(prop) in PROV:
                    edges.append((s, object, str(prop).replace(str(PROV), '')))

    for edge in edges:
        a, b = nodes.get(edge[0]), nodes.get(edge[1])
        if a and b:
            dot.append(EDGE_TPL.format(a=a, b=b, prop=edge[2]))


    output = f"""
    digraph {{
        rankdir="BT"
        node [fontname="Open Sans"];
        {'\n'.join(dot)}
    }}
    """
    print(output)

if __name__ == "__main__":
    _main()
