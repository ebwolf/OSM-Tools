#
# Splitter - takes a node file from osm_chunker and splits it into lots of little files
#            probably should build this into osm_chunker
#

import sys, time

start = time.clock()

try:
    infile = open(sys.argv[1], "r")
    
except:
    print("Unable to open " + sys.argv[1])
    sys.exit(-1)
    
fcount = 0
lcount = 1
ofname = sys.argv[1] + '.{:04d}'.format(fcount)
outfile = open(ofname, "w")

line = ''

for line in infile:
    outfile.write(line)

    if (line[2] == 'n'):
        lcount += 1

    if (line[1] == 'n' and line[-3] == '/'):
        lcount += 1
     
    #
    # 500,000 Nodes should be < 100MB (typically)
    #
    if (lcount % 1000000) == 0:
        lcount += 1
        fcount += 1
        outfile.close()

        print("Files: {:05d}   Nodes: {:d}".format(fcount, lcount))
        
        ofname = sys.argv[1] + '.{:05d}'.format(fcount)
        outfile = open(ofname, "w")
        

        
outfile.close()

infile.close()

print("Split " + str(lcount) + " lines from " + sys.argv[1] + " into " + str(fcount+1) + " files.")

finish = time.clock()
print("Took " + str(finish - start) + " seconds.")

    