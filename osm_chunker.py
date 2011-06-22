#---------------------------------------------------------------------------
# osm_chunker.py
#
# Takes an OSM Full Planet file and chops it up by object type.
#
# e.g., osm_chunker.py full-planet.osm
#
#       Generates four new files:
#          full-planet-nodes.osm
#          full-planet-ways.osm
#          full-planet-relations.osm
#          full-planet-changesets.osm
#
# The resulting OSM files aren't correct XML. But that doesn't really matter.
#
# This allows for faster processing based on the separate files when
# extracting footprints, especially when resolving ways and relations.
#
# It also provides a separate changeset file for exploring user contributions.
#
# Uses the OSMReader module so that it can real a compressed file if necessary
#
# Warning: I am a crusty old C programmer. I like C. I want to rewrite this in C but
#          Python's more portable and I want to use parts of the code in another
#          script that has to be Python. So this is not going to be very Pythonic.
#
#---------------------------------------------------------------------------
#   Name:       osm_chunker.py
#   Version:    1.0
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
        if working_on != cNodes:
           outFile.close()
           outFilename = root + "-nodes.osm"
           outFile = open(outFilename, "a")
           working_on = cNodes
           
    elif element == 'way':
        if working_on != cWays:
           outFile.close()
           outFilename = root + "-ways.osm"
           outFile = open(outFilename, "a")
           working_on = cWays

    elif element == 'relation':
        if working_on != cRelations:
           outFile.close()
           outFilename = root + "-relations.osm"
           outFile = open(outFilename, "a")
           working_on = cRelations

    elif element == 'changeset':
        if working_on != cChangesets:
           outFile.close()
           outFilename = root + "-changesets.osm"
           outFile = open(outFilename, "a")
           working_on = cChangesets

    #else:
        #if outFile.closed == False:
        #    outFile.close()
        #outFilename = root+"-junk.osm"
        #outFile = open(outFilename, "a")
        #working_on = cUnknown
        
    print >> outFile, line.encode("utf-8","ignore")
    
outFile.close()

elapsed = time.clock() - start

print str(line_count) + " lines read in " + str(elapsed) + " seconds"