#! /usr/bin/python
#
#  USGS Preliminary Computer Program: osm2fgdb.py
#  Written by: Eric B. Wolf
#  Written in: Python 2.5
#  Program ran on: Windows XP SP3, with ArcGIS 9.3.1
#
#  DISCLAIMER: Although this program has been used by the USGS, no warranty, 
#  expressed or implied, is made by the USGS or the United States Government 
#  as to the accuracy and functioning of the program and related program 
#  material nor shall the fact of distribution constitute any such warranty, 
#  and no responsibility is assumed by the USGS in connection therewith.
#

#Import modules
import sys, os
import fileinput, bz2
import math, time
import gzip

from OSMReader import OSMReader

from optparse import OptionParser, OptionGroup

#---------------------------------------------------------------------------
# This Python script will load osm xml into a file geodatabase
# It works against the compressed *.bz2 file to save space
# resulting fgdb will contain Nodes where they have useful tags.
# No segments will be loaded
# All ways will be loaded, tagged or not
# during the conversion process temporary files are used to reduce memory footprint
# you should be able to load the complete planet without memory issues
# you will need aprox 2x the bz2 files space for temporary space
# also space for output data. 

# Command line parameters
# D:\GNIS_OSM\rhode_island.osm.bz2 D:\GNIS_OSM\RI OSM.gdb 4 D:\GNIS_OSM\Work
# D:\GNIS_OSM\full-planet-110115-1800.osm.bz2 D:\GNIS_OSM OSM.gdb 4 D:\GNIS_OSM\Work

# -i d:\gnis_osm\rhode_island.osm.bz2 -o osm.gdb
# -i d:\gnis_osm\djibouti.osm.bz2 -o djibouti.gdb
#
# Kansas
# -i d:\gnis_osm\dasc-original.osm.gz -o dasc-original.gdb


sep = ';'
sep2 = '#'

parser = OptionParser()

parser.add_option('-i', '--input', dest='filename', 
                  help="OSM XML file to read extract from")

parser.add_option('-o', '--output', dest='fgdb_name', 
                  help="File geodatabase to create from the input file")
                  
parser.add_option('-w', '--workdir', dest='workdir', 
                  help="Work directory", default='work')

parser.add_option('-k', '--blocksize', dest='blocksize', 
                  help="Block size for handling large files.", default=16)

bbox_group = OptionGroup(parser, "Bounding Box (Decimal Degrees)")
bbox_group.add_option('-l', '--left', dest='left', type='float', default='-180.0')
bbox_group.add_option('-r', '--right', dest='right', type='float', default='180.0')
bbox_group.add_option('-t', '--top', dest='top', type='float', default='90.0')
bbox_group.add_option('-b', '--bottom', dest='bottom', type='float', default='-90.0')

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

sourcefile = options.filename
(inPath, inFile) = os.path.split(sourcefile)
outFGDB = inPath + "\\" + options.fgdb_name
workDir = inPath + "\\" +  options.workdir
blockSize = options.blocksize

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

from datetime import date

(year, month, day) = start_date.split('-')
start_date = date(int(year), int(month), int(day))

(year, month, day) = end_date.split('-')
end_date = date(int(year), int(month), int(day))

if start_date > end_date:
    print "End date must be greater than start date\n\n"
    sys.exit(-1)

# Show stats just does the first pass and gives stats on the data
show_stats = options.showstats

# Import the arc module as late as possible
import arcgisscripting

# Create the geoprocessor object - use 9.3 version
gp = arcgisscripting.create(9.3)

# Prints message to stdout and adds to the geoprocessor (in case this is run as a tool)
# 
def AddMsgAndPrint(msg, severity=0):
    print msg

    # Split the message on \n first, so that if it's multiple lines, 
    #  a GPMessage will be added for each line
    try:
        for string in msg.split('\n'):
            # Add appropriate geoprocessing message 
            #
            if severity == 0:
                gp.AddMessage(string)
            elif severity == 1:
                gp.AddWarning(string)
            elif severity == 2:
                gp.AddError(string)
    except:
        pass



# Enable/disable the use of bz2 compression for temp files
compress_temp_files = False

# Enable/disable deleting temp files (for debugging)
delete_temp_files = False


#
# Tags to convert to fields - I really want to make this an input file
#
#standard fields to poulate in Tags
standardFields = set((
                     'source', 'attribution','created_by','converted_by',
                     'highway'
                     
                     # GNIS-related tags
                     #'gnis_id', 'gnis_import_uuid','gnis_edited','gnis_reviewed',
                     #'gnis_created','gnis_feature_id','gnis_feature_type',
                     #'gnis_Class',
                     #'gnis_county_id','gnis_County','gnis_county_name','gnis_County_num',
                     #'gnis_state_id','gnis_ST_alpha','gnis_ST_num'

                     #'highway','junction','cycleway','tracktype','waterway','railway',
                     #'aeroway','aerialway','power','man_made','leisure',
                     #'amenity','shop','tourism','historic','landuse',
                     #'military','natural','route','boundary','sport',
                     #'abutters','fenced','lit','width','lanes',
                     #'bridge','tunnel','cutting','embankment','layer',
                     #'surface','name','int_name','nat_name','reg_name',
                     #'loc_name','old_name','ref','int_ref','nat_ref',
                     #'reg_ref','loc_ref','old_ref','ncn_ref','place',
                     #'place_name','place_numbers','postal_code','is_in','note','class'
                     ))

                     
#Tags with these keys will not be loaded, features with *only* these keys will not be loaded
#ignoreFields = set(('created_by','source','converted_by'))
ignoreFields = set(('fred','barney'))

class fieldType:
    unknown = -1
    node = 1
    way = 2
    segment = 3
    relation = 4

#this flag controls whether features with only non standard tags are loaded.
loadNonstandardTags=True

output = outFGDB
nodefc = output + "\\nodes"
#nodetagtab=output+"\osm_node_tags"
nodeothertag = output + "\other_node_tags"
wayothertag = output + "\other_way_tags"
wayfc = output + "\osm_ways"
finalwayfc = output + "\ways"
areawayfc = output + "\osm_area_ways"
finalareawayfc = output + "\\area_ways"
waytagtab = output + "\osm_way_tags"
coordsys = 'Coordinate Systems\Geographic Coordinate Systems\World\WGS 1984.prj'
scratchSpace = workDir

blocksize = blockSize * 500000

nodecount=0
taggednodecount=0
segmentcount=0
waycount=0
nodetagcount=0
waytagcount=0
ftype = fieldType.unknown
hasvalidtags=False

#
# Step 1 of 5: Prepare FGDB
#
try:
    #prepare target featureclasses
    AddMsgAndPrint("Step 1/5: Preparing target feature Classes")
    
    gp.toolbox = "management"
    if not gp.Exists(output):
        gp.CreateFileGDB(os.path.split(output)[0], os.path.split(output)[1])
        
    if not gp.Exists(nodefc):
        gp.CreateFeatureclass(output, "nodes", "point", "#", "DISABLED", "DISABLED", coordsys)
        gp.addfield(nodefc, "Node_ID", "LONG")
        gp.addfield(nodefc, "Version", "LONG")
        gp.addfield(nodefc, "Timestamp", "DATE")
        gp.addfield(nodefc, "User_ID", "LONG")
        gp.addfield(nodefc, "User", "TEXT","#","#","255")
        gp.addfield(nodefc, "Changeset", "LONG")
        for fieldname in standardFields:
            gp.addfield(nodefc,fieldname,"TEXT","#","#","255")
        
    if not gp.Exists(nodeothertag):
        gp.CreateTable(output, "other_node_tags")
        gp.addfield(nodeothertag,"Node_ID","LONG")
        gp.addfield(nodeothertag,"Tag_Name","TEXT","30","#","30")
        gp.addfield(nodeothertag,"Tag_Value","TEXT","255","#","255")
        
    if not gp.Exists(wayfc):
        gp.CreateFeatureclass(output, "osm_ways", "polyline", "#", "DISABLED", "DISABLED",coordsys)
        gp.addfield(wayfc, "Way_ID", "LONG")
        gp.addfield(wayfc, "Version", "LONG")
        gp.addfield(wayfc, "Timestamp", "DATE")
        gp.addfield(wayfc, "User_ID", "LONG")
        gp.addfield(wayfc, "User", "TEXT","#","#","255")
        gp.addfield(wayfc, "Changeset", "LONG")
        for fieldname in standardFields:
            gp.addfield(wayfc,fieldname,"TEXT","#","#","255")

    if not gp.Exists(areawayfc):
        gp.CreateFeatureclass(output, "osm_area_ways", "polygon", "#", "DISABLED", "DISABLED",coordsys)
        gp.addfield(areawayfc, "Way_ID", "LONG")
        gp.addfield(areawayfc, "Version", "LONG")
        gp.addfield(areawayfc, "Timestamp", "DATE")
        gp.addfield(areawayfc, "User_ID", "LONG")
        gp.addfield(areawayfc, "User", "TEXT","#","#","255")
        gp.addfield(areawayfc, "Changeset", "LONG")
        for fieldname in standardFields:
            gp.addfield(areawayfc,fieldname,"TEXT","#","#","255")

    if not gp.Exists(wayothertag):
        gp.CreateTable(output, "other_way_tags")
        gp.addfield(wayothertag,"Way_ID","LONG")
        gp.addfield(wayothertag,"Tag_Name","TEXT","#","#","30")
        gp.addfield(wayothertag,"Tag_Value","TEXT","#","#","255")
        
    if not gp.Exists(waytagtab):
        gp.CreateTable(output, "osm_way_tags")
        gp.addfield(waytagtab,"Way_ID","LONG")
        for fieldname in standardFields:
            gp.addfield(waytagtab,fieldname,"TEXT","#","#","255")
            
    ##if not gp.Exists(nodetagtab):
    ##    gp.CreateTable(output, "osm_node_tags")
    ##    gp.addfield(nodetagtab,"Node_ID","LONG")
    ##    for fieldname in standardFields:
    ##        gp.addfield(nodetagtab,fieldname,"TEXT","#","#","255")
            
except Exception, ErrorDesc:
    AddMsgAndPrint("Step 1 Failed" + str(ErrorDesc), 1)
    print gp.GetMessages()
    del gp
    sys.exit(-1)

#
# Step 2: Load nodes and tags
#
try:
    AddMsgAndPrint("Step 2/5: Load the nodes and tags")

    # Input can be an uncompressed OSM XML file or bzip2 or gzip compressed
    osmFile = OSMReader(inFile)

    if compress_temp_files:
        unbuiltsegments=bz2.BZ2File(scratchSpace+'/unbuiltsegments.dat','w')
        unbuiltways=bz2.BZ2File(scratchSpace+'/unbuiltways.dat','w')
    else:
        unbuiltsegments= open(scratchSpace+'/unbuiltsegments.dat','w')
        unbuiltways= open(scratchSpace+'/unbuiltways.dat','w')

    node = ('ID','x','y','ver','ts','uid','user','changeset')
    way = ('ID','ver','ts','uid','user','changeset')
    segment = ('id','start','end')
    tag = ('key','value')


    ##------------------------------------------------------------------------------
    ##First pass through source file
    ##sort nodes into blocks
    ##seperate ways
    ##load tagged nodes into fgdb
    ##load node and way tags into fgdb
    ##--------------------------------------------------------------------------------

    nodecursor = gp.insertcursor(nodefc)
    waytagcursor = gp.insertcursor(waytagtab)
    othernodetagcursor = gp.insertcursor(nodeothertag)
    otherwaytagcursor = gp.insertcursor(wayothertag)
    nodepnt = gp.createobject("point")
    ftags=[]

    linecount = 0
    blocknum = 1
    
    if compress_temp_files:
        nodefile=bz2.BZ2File(scratchSpace+'/nodeblock'+str(blocknum)+'.dat','w')
    else:
        nodefile=open(scratchSpace+'/nodeblock'+str(blocknum)+'.dat','w')
        
    while True:
        # Read the next line from the OSM file
        uline = osmFile.getNextTag()

        if uline == '':
            break
        
        element = osmFile.getElement()
        linecount += 1

        if linecount % 2000000 == 0:
            AddMsgAndPrint(str(nodecount) +' Vertices   '+str(waycount)+' Ways     ' + str(taggednodecount) +' Tagged Nodes     '+str(nodetagcount)+ ' Node Tags')

        if element=='node':
            ftype = fieldType.unknown
            ftags = []
            node = osmFile.returnNode()
              
            # Make sure lat/long make sense before continuing
            if (math.fabs(float(node[1])) > 180) or (math.fabs(float(node[2])) > 90):
                continue
                
            ftype = fieldType.node
            
            if nodecount > blocknum * blocksize:
                nodefile.close()
                blocknum += 1
                if compress_temp_files:
                    nodefile=bz2.BZ2File(scratchSpace+'/nodeblock'+str(blocknum)+'.dat','w')
                else:
                    nodefile=open(scratchSpace+'/nodeblock'+str(blocknum)+'.dat','w')

            sline = str(node[0]) + sep                              # Node ID
            sline = sline + str(node[1]) + sep                      # Latitude
            sline = sline + str(node[2]) + sep                      # Longitude
            sline = sline + str(node[3]) + sep                      # Version
            sline = sline + str(node[4]) + sep                      # Timestamp
            sline = sline + str(node[5]) + sep                      # User ID
            sline = sline + str(node[6]) + sep    # User Name
            sline = sline + str(node[7]) + '\n'                     # Changeset
            #print sline

            nodefile.write(sline)
            nodecount+=1

        elif element=='way':
            ftags = []
            ftype = fieldType.way
            waycount+=1
            way = osmFile.returnWay()

            sline = str(way[0]) + sep                              # Node ID
            sline = sline + str(way[1]) + sep                      # Version
            sline = sline + str(way[2]) + sep                      # Timestamp
            sline = sline + str(way[3]) + sep                      # User ID
            sline = sline + str(way[4]) + sep                      # User Name
            sline = sline + str(way[5])                            # Changeset

            unbuiltways.write('\n' + sline + sep2)
            
        elif element=='nd':
            # <nd ref="110552334"/>
            unbuiltways.write(str(osmFile.getAttributeValue('ref')) + sep)

        elif element=='tag':
            (key, value) = osmFile.returnTag()
            
            if key in ignoreFields:
                continue
            
            if value == '':
                continue

            if ftype == fieldType.node:
                #tagged node
                #ignore less useful tags, and if not a standard tag
                #remove tags with blank values too. lots of wierd keys have blank values
                
                if key in standardFields:
                    ftags.append((key,value))
                    hasvalidtags=True
                    nodetagcount+=1
                elif loadNonstandardTags:
                    hasvalidtags=True
                    row = othernodetagcursor.newrow()
                    row.Node_ID = long(node[0])
                    row.Tag_Name = str(key)
                    row.Tag_Value = str(value.encode('utf-8'))
                    othernodetagcursor.insertrow(row)
                    nodetagcount += 1
                    
            elif ftype == fieldType.way:

                if key in standardFields:
                    key = key.replace(sep,'_')

                    ftags.append((key,value))
                    hasvalidtags=True
                    waytagcount+=1
                elif loadNonstandardTags:
                    row=otherwaytagcursor.newrow()
                    row.Way_ID = long(way[0])
                    row.Tag_Name=str(key)
                    row.Tag_Value=str(value.encode('utf-8'))
                    otherwaytagcursor.insertrow(row)
                    waytagcount+=1
                
        elif element=='/node' and hasvalidtags and ftype == fieldType.node:
            #done with node lets load its shape
            frow = nodecursor.newrow()
            frow.setValue("Node_ID", long(node[0]))
            frow.setValue("Version", node[3])
            frow.setValue("Timestamp", node[4])
            frow.setValue("User_ID", long(node[5]))
            frow.setValue("User", node[6].encode('utf-8'))
            frow.setValue("Changeset", long(node[7]))
            
            # Initialize standard fields to empty
            for f in standardFields:
                frow.setValue(f, '')
                
            # Fill in standard fields
            for sTag in ftags:
                frow.setValue(sTag[0], str(sTag[1]))
                
            # Create the geometry
            nodepnt.x = float(node[1])
            nodepnt.y = float(node[2])
            frow.SetValue('shape', nodepnt)
            
            nodecursor.insertrow(frow)
            
            taggednodecount += 1
            hasvalidtags = False
            
        elif element=='/way' and hasvalidtags:
            #done with way lets load tags in waytags
            if len(ftags) > 0:
                                
                trow=waytagcursor.newrow()
                trow.SetValue("Way_ID",long(way[0]))
                
                for f in standardFields:
                    trow.setValue(f, '')
                    
                for sTag in ftags:
                    trow.setValue(sTag[0], str(sTag[1].encode('utf-8')))
                    
                waytagcursor.insertrow(trow)
            hasvalidtags=False
        
        # if element==...
               
    AddMsgAndPrint( str(nodecount) +' Vertices   ' +str(taggednodecount)+'  Nodes    '+str(waycount)+' Ways')

    AddMsgAndPrint( 'Bytes read from OSM file: ' + str(osmFile.getBytesRead()))

    #Close files that were written to.
    nodefile.close() 
    #unbuiltsegments.close()
    unbuiltways.close()   

    del osmFile

    # Clean up GP objects
    del nodepnt
    del waytagcursor
    del othernodetagcursor
    del otherwaytagcursor
    del nodecursor

except Exception, ErrorDesc:
    AddMsgAndPrint("dd : " + str(ErrorDesc), 2)
    print gp.GetMessages()
    nodefile.close()
    unbuiltways.close()
    del osmFile
    
    del nodepnt
    del waytagcursor
    del othernodetagcursor
    del otherwaytagcursor
    del nodecursor

    del gp
    sys.exit(-2)


#
# Step 3: Process Ways
#
try:
    AddMsgAndPrint("Step 3/5: Assembling Ways from nodes")
    nodes={}
    waycursor=gp.insertcursor(wayfc)
    areawaycursor=gp.insertcursor(areawayfc)
    completedways = 0
    wayshape = gp.createobject("Array")
    waypartpnts = gp.createobject("Array")
    waypart = gp.createobject("Array")
    apnt = gp.createobject("point")
    counter=0

    for fs in range(1,blocknum+1):
        if compress_temp_files:
            nodefile=bz2.BZ2File(scratchSpace+'/nodeblock'+str(fs)+'.dat','r')
        else:
            nodefile=open(scratchSpace+'/nodeblock'+str(fs)+'.dat','r')
            
        AddMsgAndPrint('Loading Block ' +str(fs))

        #add nodes to a dictionary
        for node in nodefile:
            snode = node.rstrip('\n').split(sep)
            # 0 - Node_ID, 1 = long, 2 = lat
            nodes[snode[0]] = (snode[1], snode[2])
            
        nodefile.close()
        
        AddMsgAndPrint('Searching Block ' +str(fs))
        if compress_temp_files:
            unbuiltways=bz2.BZ2File(scratchSpace+'/unbuiltways.dat','r')
            stillunbuiltways=bz2.BZ2File(scratchSpace+'/stillunbuiltways.dat','w')
        else:
            unbuiltways=open(scratchSpace+'/unbuiltways.dat','r')
            stillunbuiltways=open(scratchSpace+'/stillunbuiltways.dat','w')
            
        for way in unbuiltways:
            wayitems = way.rstrip('\n').rstrip(sep).split(sep2)
            
            if len(wayitems) != 2:
                continue

            subway = wayitems[0] + sep2
            wayfields = wayitems[0].split(sep)
            waynodes = wayitems[1].split(sep)
            wayid = wayfields[0]
            
            isAllComplete=True
            
            for nd in waynodes:
                # Is this node already turned into lat/long pair?
                if nd.count(' ') > 0:
                    subway = subway + nd + sep
                    
                # Is this node in our node list? Get the lat/long for the node
                elif nodes.has_key(nd):
                    subway = subway + (nodes[nd])[0] + ' ' + (nodes[nd])[1] + sep
                    
                # Node is not in the list, need to save it for "stillunbuiltways"
                else:
                    isAllComplete=False
                    subway = subway + nd + sep

            # We've tracked down all the nodes, now we can build the way/polyline
            if isAllComplete:
                row=waycursor.newrow()
                row.SetValue("way_id",wayfields[0])
                row.setValue("Version", wayfields[1])
                row.setValue("Timestamp", wayfields[2])
                row.setValue("User_ID", long(wayfields[3]))
                row.setValue("User", wayfields[4].encode('utf-8'))
                row.setValue("Changeset", long(wayfields[5]))

                waypartpnts.RemoveAll()

                finalnodes = subway.split(sep2)[1].split(sep)
                
                # Build the way geometry
                for waypoints in finalnodes:
                    partcoords=waypoints.split(' ')
                    
                    if len(partcoords) == 2:
                        apnt.x = partcoords[0]
                        apnt.y = partcoords[1]
                        waypartpnts.add(apnt)           
                        
                wayshape.add(waypartpnts)
                row.setValue("shape",wayshape)
                
                waycursor.insertrow(row)
                
                if wayshape.count == 1: #Is it an Area as well?
                    waypart=wayshape.GetObject(0)
                    sp = waypart.getobject(0)
                    ep = waypart.getobject(waypart.count-1)
                    if sp.x==ep.x and sp.y==ep.y:
                        arow=areawaycursor.newrow()
                        arow.SetValue("way_id",wayfields[0])
                        arow.setValue("Version", wayfields[1])
                        arow.setValue("Timestamp", wayfields[2])
                        arow.setValue("User_ID", long(wayfields[3]))
                        arow.setValue("User", wayfields[4])
                        arow.setValue("Changeset", long(wayfields[5]))
                        arow.SetValue("shape",waypart)
                        areawaycursor.insertrow(arow)
                        waypart.RemoveAll()
                        
                wayshape.RemoveAll()
                waypartpnts.RemoveAll()
                completedways +=1
            else:
                stillunbuiltways.write(subway + '\n')
            
        # for way in unbuiltways:
 
        AddMsgAndPrint("Loaded Ways=" + str(completedways))
        nodes.clear()
    
        unbuiltways.close()
        stillunbuiltways.close()
        os.remove(scratchSpace+'/unbuiltways.dat')
        os.rename(scratchSpace+'/stillunbuiltways.dat',scratchSpace+'/unbuiltways.dat')

    # for fs in range(1,blocknum+1):

    del apnt
    del waypart
    del waypartpnts
    del wayshape
    del areawaycursor
    del waycursor

    
except Exception, ErrorDesc:
    AddMsgAndPrint("Step 3 Failed", 2)
    print gp.GetMessages()
    
    # Cleanup on Error
    del apnt
    del waypart
    del waypartpnts
    del wayshape
    del areawaycursor
    del waycursor
    
    nodefile.close
    unbuiltways.close
    
    
    del gp
    sys.exit(-3)

#
# Step 4: Build indeces and import into FGDB
#
try:
    AddMsgAndPrint("Step 4/5: Building Indexes")

    gp.addspatialindex(nodefc,0.5)
    gp.AddIndex(waytagtab,"Way_ID","Way_Idx","UNIQUE","#")
    gp.AddIndex(nodeothertag,"Node_ID","Node_Idx","NON_UNIQUE","#")
    gp.AddIndex(wayothertag,"Way_ID","Way_Idx","NON_UNIQUE","#")

except Exception, ErrorDesc:
    AddMsgAndPrint("Step 4 Failed : " + str(ErrorDesc), 2)
    print gp.GetMessages()
    del gp
    sys.exit(-4)

#
# Step 5: Join attributes
#
try:
    AddMsgAndPrint("Step 5/5: Joining attributes to way features")
    gp.MakeFeatureLayer_management(wayfc, "tempway", "", "", "Shape_Length Shape_Length VISIBLE;Way_ID Way_ID VISIBLE")
    gp.AddJoin_management("tempway", "Way_ID", waytagtab, "Way_ID", "KEEP_ALL")
    gp.CopyFeatures_management("tempway", finalwayfc, "", "0.05", "0.5", "5.0")
    gp.delete_management("tempway")
    gp.delete_management(wayfc)

    AddMsgAndPrint("Joining attributes to area features")
    gp.MakeFeatureLayer_management(areawayfc, "temparea", "", "", "Shape_Length Shape_Length VISIBLE;Way_ID Way_ID VISIBLE")
    gp.AddJoin_management("temparea", "Way_ID", waytagtab, "Way_ID", "KEEP_ALL")
    gp.CopyFeatures_management("temparea", finalareawayfc, "", "0.05", "0.5", "5.0")
    gp.delete_management("temparea")
    gp.delete_management(areawayfc)
    gp.delete_management(waytagtab)

except Exception, ErrorDesc:
    AddMsgAndPrint("Step 5 Failed : " + str(ErrorDesc), 2)
    print gp.GetMessages()
    del gp
    sys.exit(-5)

AddMsgAndPrint("Conversion Completed")    
AddMsgAndPrint(str(nodecount) +' Nodes    '+str(waycount)+' Ways')
del gp
