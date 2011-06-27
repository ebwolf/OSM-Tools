#! /usr/bin/python
#
#  USGS Preliminary Computer Program: OSMreader.py
#  Written by: Eric B. Wolf
#  Written in: Python 2.7.1
#  Program ran on: Windows XP SP3
#
#  DISCLAIMER: Although this program has been used by the USGS, no warranty, 
#  expressed or implied, is made by the USGS or the United States Government 
#  as to the accuracy and functioning of the program and related program 
#  material nor shall the fact of distribution constitute any such warranty, 
#  and no responsibility is assumed by the USGS in connection therewith.
#
import bz2, gzip
import os
import string

from datetime import date

class objTypes:
    (nul, node, way, relation, changeset, eof) = range(0, 6)
    
# OSMReader
#
# Automatically handles straight text osm, as well as bz2, gz compressed files
#
# Does not decompress the file if its compressed
# Does not care about end of line markers.
# Does not quite handle Unicode properly. But that may be an artifact of
#  the .OSM files I got from CloudMade
#
# Currently using int for IDs. Need to change to long real soon now. For performance,
# I'm letting it be...
#
# As of Python 2.7.1, it cannot read multi-stream BZ2 files made by pbzip2
# Except for that... it works with full-planet.osm
#
# Probably need to make this a separate module - it may be the best part
# of the whole thing.
#
class OSMReader:
    def __init__(self, filename):
        self.name = filename

        self.root = ""
        self.ext = ""
        (self.root, self.ext) = os.path.splitext(string.lower(filename))
        
        try:
            # Automatically handle bz2/gz and plain osm/xml as input files
            if self.ext == '.bz2':
                self.fp = bz2.BZ2File(filename,'r')
            elif self.ext == '.gz':
                self.fp = gzip.open(filename,'r')
            else: # self.ext == '.osm':
                self.fp = open(filename,mode='rt')
        except:
            print "Error opening " + filename + "."
            exit(-1)
            
        self.buffer_size = 16384*512 # How many bytes to keep around in the buffer
        self.buffer_pos = 0
        self.buffer = self.fp.read(self.buffer_size)
        self.bytes_read = len(self.buffer)
        self.buffer_count = 0
        
        self.line_count = 0
        
        self.tag = ""

        # I should probably encapsulate the "OSM Object" but I'm leaving it as part of OSMReader for now
        #
        # OSM Object is a parsed chunk out of the OSM file: a node, way, relation, or changeset
        #     With any associated tags, way nodes, etc.
        # 
        self.objType = objTypes.nul
        self.objID = -1
        self.objUser = ''
        self.objUser_id = -1
        self.objVersion = -1
        self.objTimestamp = ''
        self.objChangeset = -1
        self.objLat = -1
        self.objLong = -1
        
        self.objTags_k = []
        self.objTags_v = []
        
        self.objWay_nodes = set()
        
        self.objRel_members = set()
        self.objRel_memtypes = []
        
        
    def getTag(self):
        return self.tag
        
    def getBytesRead(self):
        return self.bytes_read

    def findTagPunc(self, punc):
        # Return the position of the next 'punc'
        # Ignores punc in quotes.
        # Assumes buffer_pos does not point into a quoted string.
        in_quote = False
        
        pos = self.buffer_pos
        max_pos = len(self.buffer)
        
        while pos < max_pos:
            if self.buffer[pos] == '"':
                if in_quote:
                    in_quote = False
                else:
                    in_quote = True
                
            if not in_quote:
                if self.buffer[pos] == punc:
                    return pos
       
            pos += 1
            
        return -1
    
    def getNextTag(self):
        # find the close bracket
        cb = self.findTagPunc('>')
        
        # Hit the end of the buffer, need to reload
        if cb < 0:

            # Read in anohter chunk of the file
            # NOTE: It's possible that an XML tag will be greater than buffsize
            #       This will break in that situation.
            newb = self.fp.read(self.buffer_size)
            
            # Hit the end of the file, need to return zero-length
            if len(newb) == 0:
                return ''

            self.buffer_count += 1
            
            self.bytes_read = self.bytes_read + len(newb)
            
            # Copy the end of the buffer to head, tack on the new stuff
            self.buffer = self.buffer[self.buffer_pos:]+newb
            
            self.buffer_pos = 0
            
            # Check again for the close bracket
            cb = self.findTagPunc('>')
            
            if cb < 0:
                return ''

        # Pick out the tag and clean it up                
        self.tag = self.buffer[self.buffer_pos:cb+1]
        self.tag = self.tag.strip()
        if not isinstance(self.tag, unicode):
            self.tag = unicode(self.tag, "UTF-8","ignore")

        #self.tag = self.tag.decode("UTF-8","ignore")

        # shift our buffer pointer up        
        self.buffer_pos = cb + 1

        # Very rare - happens if '>' is last character in buffer
        if self.buffer_pos >= len(self.buffer):
            newb = self.fp.read(self.buffer_size)
            self.buffer = newb
            self.buffer_count += 1
            self.bytes_read += len(newb)
            self.buffer_pos = 0

        self.line_count += 1
            
        return self.tag

       
    #---------------------------------------------------------------------------
    # Gets the XML element name from the string passed in
    # an end of element tag is /element
    #---------------------------------------------------------------------------
    def getElement(self):
        s = self.tag.find('<')
        e = self.tag.find(' ',s)
        el = self.tag[s+1:e]
        
        if el[0:1]=='/':
            el=el[0:len(el)]  # was len(el) - 1 
            
        return el

    #---------------------------------------------------------------------------
    #Gets the value of the named attribute from the string
    #---------------------------------------------------------------------------
    def getAttributeValue(self, name):
        s = self.tag.find(' '+name+'="')+len(name)+3
        e = self.tag.find('"',s)
        attr = self.tag[s:e]
        return attr

    #---------------------------------------------------------------------------
    # Extract Node attribute details from a line of xml text
    #---------------------------------------------------------------------------
    def returnNode(self):
        #<node id="38708798" version="1" timestamp="2007-09-02T03:45:45Z" uid="12818" user="Andreas Kloeckner" changeset="293802" lat="41.8124909" lon="-71.3598665"/>
        nid = self.getAttributeValue('id')
        nver = self.getAttributeValue('version')
        t = self.getAttributeValue('timestamp')
        s='/'
        #                               01234567890123456789
        # Timestamp comes in like this: 2011-01-25T19:13:46Z
        # Needs to go out like this: 01/25/2011 07:13:46 PM
        m = ' AM'
        h = int(t[11:13])
        if h > 12:
            m = ' PM'
            h = h - 12
        
        nts = t[5:7]+s+t[8:10]+s+t[0:4]+' '+"%02d"%h+t[13:19]+m
               
        nuid = self.getAttributeValue('uid')
        nuser = self.getAttributeValue('user')
        ncs = self.getAttributeValue('changeset')
        nx = self.getAttributeValue('lon')
        ny = self.getAttributeValue('lat')

        return(nid, nx, ny, nver, nts, nuid, nuser, ncs)

    #---------------------------------------------------------------------------
    # Extract Way attribute details from a line of xml text
    #---------------------------------------------------------------------------
    def returnWay(self):
        #<way id="12204008" version="1" timestamp="2007-11-12T23:07:54Z" uid="7168" user="DaveHansenTiger" changeset="486129">
        id = self.getAttributeValue('id')
        ver = self.getAttributeValue('version')
        
        t = self.getAttributeValue('timestamp')
        s='/'
        #                               01234567890123456789
        # Timestamp comes in like this: 2011-01-25T19:13:46Z
        # Needs to go out like this: 01/25/2011 07:13:46 PM
        m = ' AM'
        h = int(t[11:13])
        if h > 12:
            m = ' PM'
            h = h - 12
        
        ts = t[5:7]+s+t[8:10]+s+t[0:4]+' '+"%02d"%h+t[13:19]+m
               
        uid = self.getAttributeValue('uid')
        user = self.getAttributeValue('user')
        cs = self.getAttributeValue('changeset')

        return(id, ver, ts, uid, user, cs)

    #---------------------------------------------------------------------------
    # Extract Segment (relation?!?) attributes from a line of xml text
    #---------------------------------------------------------------------------
    def returnSegment(self):
        sid = self.getAttributeValue('id')
        sn = self.getAttributeValue('from')
        en = self.getAttributeValue('to')

        return(sid, sn, en)
        
    #---------------------------------------------------------------------------
    # Get the ID attribute 
    #---------------------------------------------------------------------------
    def returnID(self):
        return self.getAttributeValue('id')

    #---------------------------------------------------------------------------
    # Get the key:value for a tag
    #---------------------------------------------------------------------------
    def returnTag(self):
        tmp = self.getAttributeValue('k').lstrip()[:29]
        
        # Standard fields can't have certain characters in the key name (like gnis:id)
        k = tmp.replace(':','_')
        
        v = self.getAttributeValue('v')[:254]
        return(k,v)

    #---------------------------------------------------------------------------
    # Parses the entire next object for high-level work
    #---------------------------------------------------------------------------
    def getNextObject(self):
        while True:
            line = self.getNextTag()
            
            if line == '':
                self.objType = objTypes.eof
                break

            if line[1] == '/':
                element = line[1:line.find('>',1)] # FIXME!
            else:
                element = line[1:line.find(' ',1)]
                
            if element == 'bound' or element == '?xml' or element == 'osm':
                continue

            if element == 'node':
                self.objType = objTypes.node
            elif element == 'way':
                self.objType = objTypes.way
            elif element == 'changeset':
                self.objType = objTypes.changeset
            elif element == 'relation':
                self.objType = objTypes.relation
                

            if element == 'node' or element == 'way' or element == 'relation':
                s = line.find('id="',4) + 4
                e = line.find('"',s)
                
                self.objID = int(line[s:e])

                s = line.find('timestamp="',4) + 11
                e = line.find('T',s)
                (year, month, day) = line[s:e].split('-')
                self.objTimestamp = date(int(year), int(month), int(day))

                s = line.find('changeset="',4) + 11
                e = line.find('"',s)
                self.objChangeset = int(line[s:e])

                s = line.find('version="',4) + 9
                e = line.find('"',s)
                self.objVersion = int(line[s:e])
                
            elif element == 'changeset':
                s = line.find('id="',4) + 4
                e = line.find('"',s)
                
                self.objID = int(line[s:e])

                # For Changeset, use "Created At" for Timestamp
                s = line.find('created_at="',4) + 12
                e = line.find('T',s)
                (year, month, day) = line[s:e].split('-')
                self.objTimestamp = date(int(year), int(month), int(day))

                #
                # RESOLVE: Probably should parse the rest of the changeset tags, but not needed now
                #
                
            # 
            # Node
            #
            if element == 'node':
                s = line.find('lat="',4) + 5
                e = line.find('"',s)
                self.objLat = float(line[s:e])
                
                s = line.find('lon="',4) + 5
                e = line.find('"',s)
                self.objLong = float(line[s:e])
    

            elif element == 'tag':
                s = line.find('k="',4) + 3
                e = line.find('"',s)
                key = line[s:e]

                s = line.find('v="',4) + 3
                e = line.find('"',s)
                value = line[s:e]
                
                self.objTags_k.append(key)
                self.objTags_v.append(value)
                
            # Way nodes
            elif element == 'nd':
                s = line.find('ref="',2) + 5
                e = line.find('"',s)
                node_id = int(line[s:e])
                
                self.objWay_nodes.add(node_id)

            elif element == 'member':
                s = line.find('ref="',6) + 5
                e = line.find('"',s)
                member = int(line[s:e])
                
                self.objRel_members.add(member)

                s = line.find('type="',6) + 6
                e = line.find('"',s)
                memtype = line[s:e]
                                
                if memtype == 'node':
                    self.objRel_memtypes.append(objTypes.node)
                elif memtype == 'way':
                    self.objRel_memtypes.append(objTypes.way)
                elif memtype == 'relation':
                    self.objRel_memtypes.append(objTypes.relation)

            # if element==...

            # End of object - break out of loop
            if element in {'/node', '/way', '/relation'}:
                break
            
            if element in {'node', 'way', 'relation'} and line[-2] == '/':
                break
        
# class OSMReader
