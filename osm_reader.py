#! /usr/bin/python

# Disable some Pylint warnings
# pylint: disable=C0103, C0114, C0115, C0116 # Missing docstrings
# pylint: disable=C0209 # Consider using F-string
# pylint: disable=W0511 # Fixme
# pylint: disable=W0702 # No exception type
# pylint: disable=R0902
# pylint: disable=R0903
# pylint: disable=R0912 # Too many branches
# pylint: disable=R0915 # Too many statements
# pylint: disable=R1732 # Consider using with

#
#  Library Name: OSMreader.py
#  Written by: Erica Wolf
#  Written in: Python 3.7.1
#  Program ran on: Ubuntu 22.04 LTS
#
import bz2
import gzip
import os
import sys


from datetime import date


class ObjTypes:
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


class OsmReader:
    def __init__(self, filename):
        self.name = filename

        self.root = ""
        self.ext = ""
        (self.root, self.ext) = os.path.splitext(filename.lower())

        try:
            # Automatically handle bz2/gz and plain osm/xml as input files
            if self.ext == '.bz2':
                print("Opening BZ2 file" + filename)
                self.fptr = bz2.BZ2File(filename, 'r')
            elif self.ext == '.gz':
                print("Opening gz file" + filename)
                self.fptr = gzip.open(filename, 'r')
            else:  # self.ext == '.osm':
                print("Opening other file" + filename)
                self.fptr = open(filename, mode='rt', encoding="utf-8")
        except:
            print("Error opening " + filename + ".")
            sys.exit(-1)

        self.buffer_size = 16384 * 512  # How many bytes to keep around in the buffer
        self.buffer_pos = 0
        self.buffer = self.fptr.read(self.buffer_size)
        self.bytes_read = len(self.buffer)
        self.buffer_count = 0

        self.line_count = 0

        self.tag = ""

        # I should probably encapsulate the "OSM Object"
        # but I'm leaving it as part of OSMReader for now
        #
        # OSM Object is a parsed chunk out of the OSM file: a node, way, relation, or changeset
        #     With any associated tags, way nodes, etc.
        #
        self.obj_type = ObjTypes.nul
        self.obj_id = -1
        self.obj_users = ''
        self.obj_user_id = -1
        self.obj_version = -1
        self.obj_timestamp = ''
        self.obj_changeset = -1
        self.obj_lat = -1
        self.obj_long = -1

        self.obj_tags_k = []
        self.obj_tags_v = []

        self.obj_way_nodes = set()

        self.obj_rel_members = set()
        self.obj_rel_memtypes = []

    def getTag(self):
        return self.tag

    def get_bytes_read(self):
        return self.bytes_read

    def find_tag_punc(self, punc):
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

    def get_next_tag(self):
        # find the close bracket
        cb = self.find_tag_punc('>')

        # Hit the end of the buffer, need to reload
        if cb < 0:

            # Read in anohter chunk of the file
            # NOTE: It's possible that an XML tag will be greater than buffsize
            #       This will break in that situation.
            newb = self.fptr.read(self.buffer_size)

            # Hit the end of the file, need to return zero-length
            if len(newb) == 0:
                return ''

            self.buffer_count += 1

            self.bytes_read = self.bytes_read + len(newb)
            print ("Bytes read:" + str(self.bytes_read))

            # Copy the end of the buffer to head, tack on the new stuff
            self.buffer = self.buffer[self.buffer_pos:] + newb

            self.buffer_pos = 0

            # Check again for the close bracket
            cb = self.find_tag_punc('>')

            if cb < 0:
                return ''

        # Pick out the tag and clean it up
        self.tag = self.buffer[self.buffer_pos:cb + 1]
        self.tag = self.tag.strip()
        # Not needed in Python3 - all strings are now unicode!
        # if not isinstance(self.tag, unicode):
        #    self.tag = unicode(self.tag, "UTF-8", "ignore")

        # self.tag = self.tag.decode("UTF-8","ignore")

        # shift our buffer pointer up
        self.buffer_pos = cb + 1

        # Very rare - happens if '>' is last character in buffer
        if self.buffer_pos >= len(self.buffer):
            newb = self.fptr.read(self.buffer_size)
            self.buffer = newb
            self.buffer_count += 1
            self.bytes_read += len(newb)
            self.buffer_pos = 0

        self.line_count += 1

        return self.tag

    # ---------------------------------------------------------------------------
    # Gets the XML element name from the string passed in
    # an end of element tag is /element
    # ---------------------------------------------------------------------------

    def get_element(self):
        s = self.tag.find('<')
        e = self.tag.find(' ', s)
        el = self.tag[s + 1:e]

        if el[0:1] == '/':
            el = el[0:len(el)]  # was len(el) - 1

        return el

    # ---------------------------------------------------------------------------
    # Gets the value of the named attribute from the string
    # ---------------------------------------------------------------------------
    def get_attribute_value(self, name):
        s = self.tag.find(' ' + name + '="') + len(name) + 3
        e = self.tag.find('"', s)
        attr = self.tag[s:e]
        return attr

    # ---------------------------------------------------------------------------
    # Extract Node attribute details from a line of xml text
    # ---------------------------------------------------------------------------
    def return_node(self):
        # <node id="38708798" version="1" timestamp="2007-09-02T03:45:45Z" uid="12818"
        # user="Andreas Kloeckner" changeset="293802" lat="41.8124909" lon="-71.3598665"/>
        nid = self.get_attribute_value('id')
        nver = self.get_attribute_value('version')
        tstamp = self.get_attribute_value('timestamp')

        #                               01234567890123456789
        # Timestamp comes in like this: 2011-01-25T19:13:46Z
        # Needs to go out like this: 01/25/2011 07:13:46 PM
        am_pm = ' AM'
        hournum = int(tstamp[11:13])
        if hournum > 12:
            am_pm = ' PM'
            hournum = hournum - 12

        nts = "%02s/%02s/%02s %02d%04s %02s" % \
              (tstamp[5:7], tstamp[8:10], tstamp[0:4],
               hournum, tstamp[13:19], am_pm)
        nuid = self.get_attribute_value('uid')
        nuser = self.get_attribute_value('user')
        ncs = self.get_attribute_value('changeset')
        nx = self.get_attribute_value('lon')
        ny = self.get_attribute_value('lat')

        return (nid, nx, ny, nver, nts, nuid, nuser, ncs)

    # ---------------------------------------------------------------------------
    # Extract Way attribute details from a line of xml text
    # ---------------------------------------------------------------------------
    def return_way(self):
        # <way id="12204008" version="1" timestamp="2007-11-12T23:07:54Z"
        # uid="7168" user="DaveHansenTiger" changeset="486129">
        wid = self.get_attribute_value('id')
        ver = self.get_attribute_value('version')

        tstamp = self.get_attribute_value('timestamp')

        #                               01234567890123456789
        # Timestamp comes in like this: 2011-01-25T19:13:46Z
        # Needs to go out like this: 01/25/2011 07:13:46 PM
        am_pm = ' AM'
        hournum = int(tstamp[11:13])
        if hournum > 12:
            am_pm = ' PM'
            hournum = hournum - 12

        nts = "%02s/%02s/%02s %02d%04s %02s" % \
              (tstamp[5:7], tstamp[8:10], tstamp[0:4],
               hournum, tstamp[13:19], am_pm)

        uid = self.get_attribute_value('uid')
        user = self.get_attribute_value('user')
        cs = self.get_attribute_value('changeset')

        return (wid, ver, nts, uid, user, cs)

    # ---------------------------------------------------------------------------
    # Extract Segment (relation?!?) attributes from a line of xml text
    # ---------------------------------------------------------------------------
    def return_segment(self):
        sid = self.get_attribute_value('id')
        sn = self.get_attribute_value('from')
        en = self.get_attribute_value('to')

        return (sid, sn, en)

    # ---------------------------------------------------------------------------
    # Get the ID attribute
    # ---------------------------------------------------------------------------
    def return_id(self):
        return self.get_attribute_value('id')

    # ---------------------------------------------------------------------------
    # Get the key:value for a tag
    # ---------------------------------------------------------------------------
    def return_tag(self):
        tmp = self.get_attribute_value('k').lstrip()[:29]

        # Standard fields can't have certain characters in the key name (like gnis:id)
        k = tmp.replace(':', '_')

        v = self.get_attribute_value('v')[:254]
        return (k, v)

    # ---------------------------------------------------------------------------
    # Parses the entire next object for high-level work
    # ---------------------------------------------------------------------------
    def get_next_object(self):
        while True:
            line = self.get_next_tag()

            if line == '':
                self.obj_type = ObjTypes.eof
                break

            if line[1] == '/':
                element = line[1:line.find('>', 1)]  # FIXME!
            else:
                element = line[1:line.find(' ', 1)]

            if element in ['bound', '?xml', 'osm']:
                continue

            if element == 'node':
                self.obj_type = ObjTypes.node
            elif element == 'way':
                self.obj_type = ObjTypes.way
            elif element == 'changeset':
                self.obj_type = ObjTypes.changeset
            elif element == 'relation':
                self.obj_type = ObjTypes.relation

            if element in ['node', 'way', 'relation']:
                s = line.find('id="', 4) + 4
                e = line.find('"', s)

                self.obj_id = int(line[s:e])

                s = line.find('timestamp="', 4) + 11
                e = line.find('T', s)
                (year, month, day) = line[s:e].split('-')
                self.obj_timestamp = date(int(year), int(month), int(day))

                s = line.find('changeset="', 4) + 11
                e = line.find('"', s)
                self.obj_changeset = int(line[s:e])

                s = line.find('version="', 4) + 9
                e = line.find('"', s)
                self.obj_version = int(line[s:e])

            elif element == 'changeset':
                s = line.find('id="', 4) + 4
                e = line.find('"', s)

                self.obj_id = int(line[s:e])

                # For Changeset, use "Created At" for Timestamp
                s = line.find('created_at="', 4) + 12
                e = line.find('T', s)
                (year, month, day) = line[s:e].split('-')
                self.obj_timestamp = date(int(year), int(month), int(day))

                #
                # RESOLVE: Probably should parse the rest of the changeset tags, but not needed now
                #

            #
            # Node
            #
            if element == 'node':
                s = line.find('lat="', 4) + 5
                e = line.find('"', s)
                self.obj_lat = float(line[s:e])

                s = line.find('lon="', 4) + 5
                e = line.find('"', s)
                self.obj_long = float(line[s:e])

            elif element == 'tag':
                s = line.find('k="', 4) + 3
                e = line.find('"', s)
                key = line[s:e]

                s = line.find('v="', 4) + 3
                e = line.find('"', s)
                value = line[s:e]

                self.obj_tags_k.append(key)
                self.obj_tags_v.append(value)

            # Way nodes
            elif element == 'nd':
                s = line.find('ref="', 2) + 5
                e = line.find('"', s)
                node_id = int(line[s:e])

                self.obj_way_nodes.add(node_id)

            elif element == 'member':
                s = line.find('ref="', 6) + 5
                e = line.find('"', s)
                member = int(line[s:e])

                self.obj_rel_members.add(member)

                s = line.find('type="', 6) + 6
                e = line.find('"', s)
                memtype = line[s:e]

                if memtype == 'node':
                    self.obj_rel_memtypes.append(ObjTypes.node)
                elif memtype == 'way':
                    self.obj_rel_memtypes.append(ObjTypes.way)
                elif memtype == 'relation':
                    self.obj_rel_memtypes.append(ObjTypes.relation)

            # if element==...

            # End of object - break out of loop
            if element in {'/node', '/way', '/relation'}:
                break

            if element in {'node', 'way', 'relation'} and line[-2] == '/':
                break

# class OsmReader
