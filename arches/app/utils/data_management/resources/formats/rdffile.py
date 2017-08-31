import os
import datetime
from format import Writer
from arches.app.models import models
from arches.app.models.system_settings import settings
from rdflib import Namespace
from rdflib import URIRef, Literal
from rdflib import Dataset
from rdflib.namespace import RDF, RDFS

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO


class RdfWriter(Writer):

    def __init__(self, **kwargs):
        self.format = kwargs.pop('format', 'xml')
        super(RdfWriter, self).__init__(**kwargs)

    def write_resources(self, graph_id=None, resourceinstanceids=None):
        super(RdfWriter, self).write_resources(graph_id=graph_id, resourceinstanceids=resourceinstanceids)
        
        rdf_for_export = []
        ds = Dataset()

        archesproject = Namespace(settings.ARCHES_NAMESPACE_FOR_DATA_EXPORT)
        ds.bind('archesproject', archesproject, False)

        def get_nodegroup_edges_by_collector_node(node):
            edges = []
            nodegroup = node.nodegroup
            def getchildedges(node):
                for edge in models.Edge.objects.filter(domainnode=node):
                    if nodegroup == edge.rangenode.nodegroup:
                        edges.append(edge)
                        getchildedges(edge.rangenode)

            getchildedges(node)
            return edges

        graph_cache = {}
        def get_graph_parts(graphid):
            if graphid not in graph_cache:
                graph_cache[graphid] = {
                    'rootedges': [],
                    'subgraphs': {}
                }
                graph = models.GraphModel.objects.get(pk=graphid)
                nodegroups = set()
                for node in graph.node_set.all():
                    if node.nodegroup:
                        nodegroups.add(node.nodegroup)
                    if node.istopnode:
                        for edge in get_nodegroup_edges_by_collector_node(node):
                            if edge.rangenode.nodegroup is None:
                                graph_cache[graphid]['rootedges'].append(edge)
                for nodegroup in nodegroups:
                    graph_cache[graphid]['subgraphs'][nodegroup] = {
                        'edges': [],
                        'inedge': None,
                        'parentnode_nodegroup': None
                    }
                    graph_cache[graphid]['subgraphs'][nodegroup]['inedge'] = models.Edge.objects.get(rangenode_id=nodegroup.pk)
                    graph_cache[graphid]['subgraphs'][nodegroup]['parentnode_nodegroup'] = graph_cache[graphid]['subgraphs'][nodegroup]['inedge'].domainnode.nodegroup
                    graph_cache[graphid]['subgraphs'][nodegroup]['edges'] = get_nodegroup_edges_by_collector_node(models.Node.objects.get(pk=nodegroup.pk))

            return graph_cache[graphid]


        def add_edge_to_graph(graph, domainnode, rangenode, edge):
            graph.add((domainnode, RDF.type, URIRef(edge.domainnode.ontologyclass)))
            graph.add((rangenode, RDF.type, URIRef(edge.rangenode.ontologyclass)))
            graph.add((domainnode, URIRef(edge.ontologyproperty), rangenode))


        dest = StringIO()
        for resourceinstanceid, tiles in self.resourceinstances.iteritems():
            g = ds.graph(archesproject['resource/%s' % resourceinstanceid])
            graphid = tiles[0].resourceinstance.graph_id
            graph_info = get_graph_parts(graphid)

            for edge in graph_cache[graphid]['rootedges']:
                domainnode = archesproject[str(edge.domainnode.pk)]
                rangenode = archesproject[str(edge.rangenode.pk)]
                add_edge_to_graph(g, domainnode, rangenode, edge)

            for tile in tiles:
                for edge in graph_info['subgraphs'][tile.nodegroup]['edges']:
                    domainnode = archesproject["%s--%s" % (str(edge.domainnode.pk), str(tile.pk))]
                    rangenode = archesproject["%s--%s" % (str(edge.rangenode.pk), str(tile.pk))]
                    add_edge_to_graph(g, domainnode, rangenode, edge)

                    try:
                        g.add((domainnode, RDF.value, Literal(tile.data[str(edge.domainnode_id)]))) 
                    except:
                        pass    
                    try:
                        g.add((rangenode, RDF.value, Literal(tile.data[str(edge.rangenode_id)]))) 
                    except:
                        pass    

                if graph_info['subgraphs'][tile.nodegroup]['parentnode_nodegroup'] == None:
                    edge = graph_info['subgraphs'][tile.nodegroup]['inedge']
                    domainnode = archesproject[str(edge.domainnode.pk)]
                    rangenode = archesproject["%s--%s" % (str(edge.rangenode.pk), str(tile.pk))]
                    add_edge_to_graph(g, domainnode, rangenode, edge)

                if graph_info['subgraphs'][tile.nodegroup]['parentnode_nodegroup'] != None:
                    edge = graph_info['subgraphs'][tile.nodegroup]['inedge']
                    domainnode = archesproject["%s--%s" % (str(edge.domainnode.pk), str(tile.parenttile.pk))]
                    rangenode = archesproject["%s--%s" % (str(edge.rangenode.pk), str(tile.pk))]
                    add_edge_to_graph(g, domainnode, rangenode, edge)

            dest.write(g.serialize(format=self.format))

        iso_date = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        file_name = os.path.join('{0}_{1}.{2}'.format(self.file_prefix, iso_date, 'rdf'))

        rdf_for_export.append({'name':file_name, 'outputfile': dest})
        return rdf_for_export

# to override thess formats, do this
# class PrettyRdfWriter(RdfWriter):

#     def __init__(self, **kwargs):
#         super(PrettyRdfWriter, self).__init__(**kwargs)
#         self.format = 'pretty-xml'

# class JsonLdWriter(RdfWriter):

#     def __init__(self, **kwargs):
#         super(JsonLdWriter, self).__init__(**kwargs)
#         self.format = 'json-ld'