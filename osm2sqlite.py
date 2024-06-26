# ---------------------------------------------------------------------------
# osm2sqlite.py
#
# First pass based on osm_fpextract.py
#
# Extracts a BBOX footprint and timeframe from a full planet file. Like
# Frederick Ramm's history-extract.pl except that it works against the
# compressed .bz2, compressed .gz, or OSM XML. And It doesn't care about
# end-of-lines.
#
# Writes to an sqlite3 database
#
# Uses multiple passes to get everything. Ways and relations are resolved fully
# but, for obvious reasons if you think about it, changesets are not. That is,
# you don't get everything in every changeset.
#
# Pass 1:
#   Scan through all nodes,
#     - Make a list of nodes in BBOX, timeframe
#     - Note changesets for each node
#   Scan through all ways
#     - Make a list of ways having at least one node in list
#     - Note changesets for each way
#   Scan through all relations
#     - Make a list of relations having at least one node or way in lists
#     - Note changesets for each relation
#
# Pass 2:
#   Copy listed changesets to new file
#   Copy listed nodes to new file
#   Copy listed ways to new file
#   Copy listed relations to new file
#
# Of course, all tags for each object are also copied.
#
# Since this is designed to work with historical data, it tends to grab more
# than it needs. Specifically, old, deleted nodes will cause ways and relations
# to be included (etc.). It does not thoroughly resolve relations because that
# could get out of hand. And as mentioned, it doesn't even try to resolve
# changesets.
#
#
# ---------------------------------------------------------------------------
#   Name:       osm2sqlite.py
#   Version:    1.0
#   Authored    By: Erica Wolf
#   Copyright:  Public Domain.
# ---------------------------------------------------------------------------

# Command line parameters - these help be do test runs in PythonWin.
#
# D:\GNIS_OSM\rhode_island.osm.bz2 -72 -71 42 41
# D:\GNIS_OSM\djibouti.osm.bz2 42.7 42.8 11.6 11.5
# D:\GNIS_OSM\full-planet-110115-1800.osm.bz2 -72 -71 42 41
#
# Hawaii - just Oahu
# -i hawaii.osm.bz2 -l -158.29 -r -157.661 -t 21.73 -b 21.2 -e 2009-01-01
# -i test.osm -l -158.29 -r -157.661 -t 21.73 -b 21.2 -e 2009-01-01

# Import modules
from optparse import OptionParser, OptionGroup
from osm_reader import OsmReaderReader
from datetime import date
import sys
import time


class objTypes:
    (nul, node, way, relation, changeset, eof) = range(0, 6)


parser = OptionParser()

parser.add_option('-i', '--input', dest='filename',
                  help="OSM XML file to read extract from", metavar="FILE")

bbox_group = OptionGroup(parser, "Bounding Box (Decimal Degrees)")
bbox_group.add_option('-l', '--left', dest='left',
                      type='float', default='-180.0')
bbox_group.add_option('-r', '--right', dest='right',
                      type='float', default='180.0')
bbox_group.add_option('-t', '--top', dest='top',
                      type='float', default='90.0')
bbox_group.add_option('-b', '--bottom', dest='bottom',
                      type='float', default='-90.0')

parser.add_option_group(bbox_group)

tframe_group = OptionGroup(parser, "Time Frame (YYYY-MM-DD)")
tframe_group.add_option('-s', '--start', dest='start', default='2000-01-01')
tframe_group.add_option('-e', '--end', dest='end', default='2100-01-01')
parser.add_option_group(tframe_group)

parser.add_option('-H', '--history', dest='history', action="store_true", default=False,
                  help="Output all versions, not just current version.")

parser.add_option('-c', '--changesets', dest='changesets', action="store_true", default=False,
                  help="Output changesets.")

parser.add_option('-R', '--resolve', dest='resolve', action="store_false", default=True,
                  help="DO NOT resolve ways and relations that extend past bbox (default is to resolve).")

parser.add_option('-x', '--stats', dest='showstats', action="store_true", default=False,
                  help="Show processing/debugging statistics.")


(options, args) = parser.parse_args(args=None, values=None)

inFile = options.filename
bbox_left = options.left
bbox_right = options.right
bbox_top = options.top
bbox_bottom = options.bottom
start_date = options.start
end_date = options.end

output_history = options.history
output_changesets = options.changesets
resolve = options.resolve

start = time.clock()


(year, month, day) = start_date.split('-')
start_date = date(int(year), int(month), int(day))

(year, month, day) = end_date.split('-')
end_date = date(int(year), int(month), int(day))

if start_date > end_date:
    print("End date must be greater than start date\n\n")
    sys.exit(-1)

# Show stats just does the first pass and gives stats on the data
show_stats = options.showstats

node_list = set()
way_list = set()
relation_list = set()
changeset_list = set()

node_ver_dict = {}
way_ver_list = []
rel_ver_list = []

relation_ways = set()
relation_nodes = set()

#
# Processing flags
#

# Enable/disable the use of bz2 compression for temp files
useBZ2_temp_files = False

# Enable/disable deleting temp files (for debugging)
delete_temp_files = False

min_node_id = 100000000
max_node_id = 0
min_way_node_id = 100000000
max_way_node_id = 0

obj_count = 0


#
# Step 1: Scan input file, build lists
#
try:
    # Input is maybe a very big file
    inputfile = OsmReader(inFile)

except:
    print("Failed to initialize OsmReader")
    exit(-1)

if show_stats:
    print("Step 1: List nodes in BBOX")

try:
    # for uline in inputfile:
    while True:

        # Read one OSM XML object without depending on line breaks
        # (so this works with history files)
        inputfile.get_nextobject()

        if inputfile.obj_type == ObjTypes.eof:
            break

        obj_count += 1

        if (show_stats):
            if (obj_count % 250000) == 0:
                print("Processed " + str(obj_count) + " objects.")

        # Is the node within the timestamp?
        if (inputfile.objTimestamp < start_date or inputfile.objTimestamp > end_date):
            continue

        #
        # Node
        #
        if inputfile.obj_type == ObjTypes.node:
            if inputfile.obj_id > max_node_id:
                max_node_id = inputfile.obj_id

            if inputfile.obj_id < min_node_id:
                min_node_id = inputfile.obj_id

            # Is the node in the BBOX?
            if inputfile.obj_lat < bbox_bottom or inputfile.obj_lat > bbox_top:
                continue

                # Is the node in the BBOX?
            if inputfile.obj_long < bbox_left or inputfile.obj_long > bbox_right:
                continue

            node_list.add(inputfile.obj_id)

            changeset_list.add(inputfile.obj_changeset)

            # Save the highest version number
            if not output_history:
                node_ver_dict[inputfile.objID] = inputfile.objVersion

        # Way
        elif inputfile.obj_type == ObjTypes.way:

            # Does the way contain a node we are keeping?
            for node_id in inputfile.obj_way_nodes:
                if node_id in node_list:
                    way_list.add(inputfile.obj_id)

                    changeset_list.add(inputfile.obj_changeset)

                    # This adds nodes not in BBOX but part of way that intersects it
                    # This really slows things down!
                    # if resolve:
                    #    node_list.update(inputfile.objWay_nodes)

                    break

        # Relation
        elif inputfile.objType == objTypes.relation:
            if not resolve:
                continue

            relation_list.add(inputfile.objID)
            changeset_list.add(inputfile.objChangeset)
            node_list.update(relation_nodes)
            way_list.update(relation_ways)

    # while True:

    if show_stats:
        print('Bytes read from OSM file: ' + str(inputfile.getBytesRead()))
        print('Objects processed: ' + str(obj_count))

        print("Changeset list count: " + str(len(changeset_list)))
        print("Node list count: " + str(len(node_list)))
        print("Way list count: " + str(len(way_list)))
        print("Relation list count: " + str(len(relation_list)))

    del inputfile

except Exception, ErrorDesc:
    print("Step 1 Failed : " + str(ErrorDesc)))
    print("Line " + str(inputfile.line_count) + ":" + inputfile.getTag())
    print("Bytes read: " + str(inputfile.getBytesRead()))
    finish= time.clock()
    print("Extract incomplete in " + str(finish - start) + " seconds.")
    sys.exit(-2)

line_count= 0

try:
    # Input is maybe a very big file
    inputfile= OSMReader(inFile)

    # OSM XML Header stuff - made up as usual
    print('<?xml version="1.0" encoding="UTF-8"?>')
    # "2011-02-16T01:11:04Z"  "%Y-%m-%dT%H:%M:%SZ"
    timestamp= time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    print('<osm version="0.6" generator="OSM_Extract.py" timestamp="' + timestamp + '">')
    print('<!-- copyright="OpenStreetMap and contributors" attribution="http://www.openstreetmap.org/copyright/" license="http://creativecommons.org/licenses/by/2.0/" -->')
    print('  <bound box="' + str(bbox_left) + ',' + str(bbox_bottom) + ',' + str(bbox_right) + \
          ',' + str(bbox_top) + '> origin="http://www.openstreetmap.org/api/0.6" />')

    keep= False

    line_count= 0

    while True:
        # Read one XML tag without depending on line breaks
        # (so this works with history files)
        line= inputfile.getNextTag()

        line_count += 1

        if line == '':
            break

        if line[1] == '/':
            element = line[1:line.find('>', 1)] # FIXME!
        else:
            element = line[1:line.find(' ', 1)]

        #
        # Node
        #
        if element == 'node':
            keep= False

            s = line.find('id="', 5) + 4
            e = line.find('"', s)
            node_id= int(line[s:e])

            if node_id in node_list:
                # Save the highest version number
                if not output_history:
                    s = line.find('version="', 4) + 9
                    e = line.find('"', s)
                    ver= int(line[s:e])
                    if node_ver_dict[node_id] == ver:
                        print("  " + line.encode("utf-8", "ignore"))
                        if not line[-2] == '/':
                            keep= True
                else:
                    print("  " + line.encode("utf-8", "ignore"))
                    if not line[-2] == '/':
                        keep= True


        #
        # Way
        #
        elif element == 'way':
            keep= False

            s = line.find('id="', 5) + 4
            e = line.find('"', s)
            way_id= int(line[s:e])

            if way_id in way_list:
                print("  " + line.encode("utf-8", "ignore"))
                keep= True

        #
        # Relation
        #
        elif element == 'relation':
            keep= False
            s = line.find('id="', 5) + 4
            e = line.find('"', s)
            rel_id= int(line[s:e])

            if rel_id in relation_list:
                print("  " + line.encode("utf-8", "ignore"))
                keep= True

        #
        # Changeset
        #
        elif element == 'changeset':
            keep= False

            s= line.find('id="', 5) + 4
            e= line.find('"', s)
            cs_id= int(line[s:e])

            if output_changesets and cs_id in changeset_list:
                print("    " + line.encode("utf-8", "ignore"))
                keep= True


        elif element == 'tag' or element == 'nd' or element == 'member':
            if keep:
                print("    " + line.encode("utf-8", "ignore"))

        elif element == '/node' or element == '/way' or element == '/relation' or element == '/changeset':
            if keep:
                print("  " + line.encode("utf-8", "ignore"))

            keep= False

        else:
            if keep:
                print("  " + line.encode("utf-8", "ignore"))

    # While True:

    print('</osm>\n')

except Exception, ErrorDesc:
    print("Step 2 Failed : " + str(ErrorDesc))
    print("Line " + str(inputfile.line_count) + ":" + \
          inputfile.getTag().encode("utf-8", "ignore"))
    print("Bytes read: " + str(inputfile.getBytesRead()))
    finish= time.clock()
    print("Extract incomplete in " + str(finish - start) + " seconds.")
    sys.exit(-2)

finish= time.clock()
if show_stats:
    print("Extract complete in " + str(finish - start) + " seconds.")

