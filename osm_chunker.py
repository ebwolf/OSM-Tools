#---------------------------------------------------------------------------
# osm_chunker.py
#
# Takes an OSM Full Planet file and chops it up by object type.
#
# e.g., osm_chunker.py full-planet.osm
#
#       Generates four new file sets:
#          full-planet-nodes.osm.xxxx
#          full-planet-ways.osm.xxxx
#          full-planet-relations.osm.xxxx
#          full-planet-changesets.osm.xxxx
#
# The resulting OSM files aren't correct XML. But that doesn't really matter. 
# Each file contains only one object type. It also contains a maximum of 500,000
# of those objects. This limits each file to under 300,000MB.
#
# One "enhancement" that might be handy would be to add a bounding box tag to the start
# of each file. But it might make more sense to do that later on.
#
# This allows for faster processing based on the separate files when
# extracting footprints, especially when resolving ways and relations.
#
# It also keeps the changesets for exploring user contributions.
#
# Uses the OSMReader module so that it can real a compressed file if necessary
#
# Warning: I am a crusty old C programmer. I like C. I want to rewrite this in C but
#          Python's more portable and I want to use parts of the code in another
#          script that has to be Python. So this is not going to be very Pythonic.
#
#---------------------------------------------------------------------------
#   Name:       osm_chunker.py
#   Version:    1.1
#   Authored    By: Eric Wolf
#   Copyright:  Public Domain.
#---------------------------------------------------------------------------

# Command line parameters - these help be do test runs in PythonWin.
#
# E:\GNIS_OSM\rhode_island.osm.bz2
# E:\GNIS_OSM\djibouti.osm.bz2
# E:\GNIS_OSM\full-planet-110115-1800.osm.bz2
# E:\GNIS_OSM\hawaii.osm.bz2

# Import modules
import sys
import os
import math
import time
import string

from OSMReader import OSMReader

inFile = str(sys.argv[1])

start = time.clock()

#
# Step 1: Scan input file, build lists
#
try:
    # Input is maybe a very big file
    inputfile = OSMReader(inFile)

except:
    print "Failed to initialize OSMReader with file " + inFile
    exit(-1)

# These are consts. Don't change them ;)
cUnknown = -1
cNodes = 1
cWays = 2
cRelations = 3
cChangesets = 4

(root, ext) = os.path.splitext(string.lower(inFile))

outFilename = root+"-junk.osm"
outFile = open(outFilename, "a")
working_on = cUnknown
line_count = 0

nfcount = 0
wfcount = 0
rfcount = 0
cfcount = 0

nodes = 0
ways = 0
rels = 0
csets = 0


while True:

    # Read one XML tag without depending on line breaks 
    # (so this works with history files)
    line = inputfile.getNextTag()

    line_count += 1

    if line == '':
        break

    if line[1] == '/':
        element = line[1:line.find('>',1)]
    else:
        element = line[1:line.find(' ',1)]

    # 
    # Node
    # 
    if element == 'node':
        nodes += 1
         
        #
        # 500,000 Nodes should be < 100MB (typically)
        #
        if (nodes % 10000) == 0:
            nfcount += 1
            outFile.close()
    
            print "Node Files: {:05d}   Nodes: {:d}".format(nfcount, nodes)
            outFilename = root + "-nodes.osm.{:05d}".format(nfcount)
            outFile.close()
            outFile = open(outFilename, "w")
       
        if working_on != cNodes:
            outFile.close()
            outFilename = root + "-nodes.osm.{:05d}".format(nfcount)
            outFile = open(outFilename, "a")

        working_on = cNodes
           
    elif element == 'way':
        ways += 1
         
        #
        # 500,000 Ways should be < ???MB (typically)
        #
        if (ways % 10000) == 0:
            wfcount += 1
            outFile.close()
    
            print "Way Files: {:05d}   Way: {:d}".format(wfcount, ways)
            outFilename = root + "-ways.osm.{:05d}".format(wfcount)
            outFile.close()
            outFile = open(outFilename, "w")
       
        if working_on != cWays:
            outFile.close()
            outFilename = root + "-ways.osm.{:05d}".format(wfcount)
            outFile = open(outFilename, "a")

        working_on = cWays

    elif element == 'relation':
        rels += 1
    
        #
        # 500,000 Relations should be < ???MB (typically)
        #
        if (rels % 1000000) == 0:
            rfcount += 1
            outFile.close()
    
            print "Relations Files: {:05d}   Relations: {:d}".format(wfcount, ways)
            outFilename = root + "-relations.osm.{:05d}".format(wfcount)
            outFile.close()
            outFile = open(outFilename, "w")
            
        if working_on != cRelations:
            outFile.close()
            outFilename = root + "-relations.osm.{:05d}".format(rfcount)
            outFile = open(outFilename, "a")

        working_on = cRelations

    elif element == 'changeset':
        csets += 1
         
        #
        # 500,000 Changesets should be < ???MB (typically)
        #
        if (csets % 1000000) == 0:
            cfcount += 1
            outFile.close()
    
            print "Changeset Files: {:05d}   Changesets: {:d}".format(cfcount, csets)
            outFilename = root + "-changesets.osm.{:05d}".format(cfcount)
            outFile.close()
            outFile = open(outFilename, "w")
            
        if working_on != cChangesets:
            outFile.close()
            outFilename = root + "-changesets.osm.{:05d}".format(cfcount)
            outFile = open(outFilename, "a")
            
        working_on = cChangesets
        
    print >> outFile, line.encode("utf-8","ignore")
    
outFile.close()

elapsed = time.clock() - start

print "Nodes: {:d}".format(nodes)
print "Ways: {:d}".format(ways)
print "Relations: {:d}".format(rels)
print "Changesets: {:d}".format(csets)
print str(line_count) + " lines read in " + str(elapsed) + " seconds"