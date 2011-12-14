################################################################################
#
#    Randal C. Burns
#    Department of Computer Science
#    Johns Hopkins University
#
################################################################################

import numpy as np
import cStringIO
import zlib
import MySQLdb
import zindex

################################################################################
#
#  class: AnnDB
#
#  Manipulate/create/read from the Morton-order cube store
#
################################################################################

class AnnDB: 

  def __init__ (self, dbconf):
    """Connect with the brain databases"""

    self.dbcfg = dbconf

    # Connection info in dbconfig
    self.conn = MySQLdb.connect (host = self.dbcfg.dbhost,
                            user = self.dbcfg.dbuser,
                            passwd = self.dbcfg.dbpasswd,
                            db = self.dbcfg.anndbname)
    cursor = self.conn.cursor ()
    cursor.execute ("SELECT VERSION()")
    row = cursor.fetchone ()
    print "server version:", row[0]
    cursor.close ()

    [ self.startslice, endslice ] = self.dbcfg.slicerange
    self.slices = endslice - self.startslice + 1 

  def __del ( self ):
    """Close the connection"""
    conn.close()



  #
  #  nextIdentifier
  #
  def nextIdentifier ( self ):
    
    # Query the current max identifier
    
    # increment and update query

    return id


  #
  # addItem
  #
  #  Load the cube from the DB.
  #  Uncompress it.
  #  Select and item identifier
  #  Call add item on the cube.
  #  Store the cube on the DB
  #
  #
  def addEntity ( self, locations ):

#  RBTODO need to deal with voxel conflicts.  later.

  #  An item may exist across several cubes
  #  Convert the locations into Morton order

  # dictionary of mortonkeys
  cubelocs = {}

  #  list of locations inside each morton key
  for loc in locations:
    key = XYZMorton(loc)
    cubelocs[key].append(loc)

  # Now we have a 
  for key, loclist in cubelocs.iteritems():
    # get the block from the database

    # decompress the anncube
    anncube.fromNPZ ( )

    # add the items
    anncube.addEntity ( self.nextIdentity(), loclist )

    # compress the anncube
    anncube.toNPX ()

    # perform an update query

  

    

  #
  #  ingestCube
  #
  def ingestCube ( self, mortonidx, resolution, tilestack ):

    print "Ingest for resolution %s morton index %s, xyz " % (resolution , mortonidx) , zindex.MortonXYZ ( mortonidx )

    [ x, y, z ] = zindex.MortonXYZ ( mortonidx )
    [xcubedim, ycubedim, zcubedim] = self.dbcfg.cubedim [resolution ]
    bc = braincube.BrainCube ( self.dbcfg.cubedim[resolution] )
    corner = [ x*xcubedim, y*ycubedim, z*zcubedim ]
    bc.cubeFromFiles (corner, tilestack)
    return bc
#    self.inmemcubes[mortonidx] = bc


  #
  #  generateDB
  #
  def generateEmpytDB ( self, resolution ):
    """Generate an empty annontqtion databases """

    [ximagesz, yimagesz] = self.dbcfg.imagesz [ resolution ]
    [xcubedim, ycubedim, zcubedim] = self.dbcfg.cubedim [resolution ]
    [ self.startslice, endslice ] = self.dbcfg.slicerange
    self.slices = endslice - self.startslice + 1 

    # round up to the next largest slice
    if self.slices % zcubedim != 0 : 
      self.slices = ( self.slices / zcubedim + 1 ) * zcubedim

    # You've made this assumption.  It's reasonable.  Make it explicit
    # process more slices than you need.  Round up.  Missing data is 0s.
    assert self.slices % zcubedim == 0
    assert yimagesz % ycubedim == 0
    assert ximagesz % xcubedim == 0

    tilestack = tiles.Tiles ( self.dbcfg.tilesz, self.dbcfg.inputprefix + '/' + str(resolution), self.startslice) 

    # Set the limits on the number of cubes in each dimension
    xlimit = ximagesz / xcubedim
    ylimit = yimagesz / ycubedim
    zlimit = self.slices / zcubedim

    # list of batched indexes
    idxbatch = []

    # This parameter needs to match to the max number of slices to be taken.  
    # The maximum z slices that prefetching will take in this prefetch
    #  This is useful for higher resolutions where we run out of tiles in 
    #  the x and y dimensions
    zmaxpf = 256
    zstride = 256

    # This batch size is chosen for braingraph1.  
    #  It loads 32x32x16cubes equivalent to 16 x 16 x 256 tiles @ 128x128x16 per tile and 512x512x1 per cube
    #  this is 2^34 bytes of memory 
    batchsize = 16384

    # Ingest the slices in morton order
    for mortonidx in zindex.generator ( [xlimit, ylimit, zlimit] ):

      xyz = zindex.MortonXYZ ( mortonidx )
      
      # if this exceeds the limit on the z dimension, do the ingest
      if len ( idxbatch ) == batchsize or xyz[2] == zmaxpf:

        # preload the batch
        tilestack.prefetch ( idxbatch, [xcubedim, ycubedim, zcubedim] )
        
        # ingest the batch
        for idx in idxbatch:
          bc = self.ingestCube ( idx, resolution, tilestack )
          self.saveCube ( bc, idx, resolution )

        # commit the batch
        self.conn.commit()
        
        # if we've hit our area bounds set the new limit
        if xyz [2] == zmaxpf:
           zmaxpf += zstride

        # Finished this batch.  Start anew.
        idxbatch = []

      #build a batch of indexes
      idxbatch.append ( mortonidx )

    # preload the remaining
    tilestack.prefetch ( idxbatch, [xcubedim, ycubedim, zcubedim] )

    # Ingest the remaining once the loop is over
    for idx in idxbatch:
      bc = self.ingestCube ( idx, resolution, tilestack )
      self.saveCube ( bc, idx, resolution )

    # commit the batch
    self.conn.commit()


  #
  # Output the cube to the database
  #   use NumPy formatting I/O routines
  #
  def saveCube ( self, cube, mortonidx, resolution ):
    """Output the cube to the database"""

    dbname = self.dbcfg.tablebase + str(resolution)

    # create the DB BLOB
    fileobj = cStringIO.StringIO ()
    np.save ( fileobj, cube.data )
    cdz = zlib.compress (fileobj.getvalue()) 

    # insert the blob into the database
    cursor = self.conn.cursor()
    sql = "INSERT INTO " + dbname + " (zindex, cube) VALUES (%s, %s)"
    cursor.execute(sql, (mortonidx, cdz))
    cursor.close()


  #
  #  getCube  
  #
  def getCube ( self, corner, dim, resolution ):
    """Extract a cube of arbitrary size.  Need not be aligned."""

    [xcubedim, ycubedim, zcubedim] = self.dbcfg.cubedim [resolution ]

    # Round to the nearest larger cube in all dimensions
    start = [ corner[0]/xcubedim,\
                    corner[1]/ycubedim,\
                    corner[2]/zcubedim ] 

    numcubes = [ (corner[0]+dim[0]+xcubedim-1)/xcubedim - start[0],\
                (corner[1]+dim[1]+ycubedim-1)/ycubedim - start[1],\
                (corner[2]+dim[2]+zcubedim-1)/zcubedim - start[2] ] 

    inbuf = braincube.BrainCube ( self.dbcfg.cubedim [resolution] )
    outbuf = braincube.BrainCube ( [numcubes[0]*xcubedim, numcubes[1]*ycubedim, numcubes[2]*zcubedim] )

    # Build a list of indexes to access
    listofidxs = []
    for z in range ( numcubes[2] ):
      for y in range ( numcubes[1] ):
        for x in range ( numcubes[0] ):
          mortonidx = zindex.XYZMorton ( [x+start[0], y+start[1], z+start[2]] )
          listofidxs.append ( mortonidx )

    # Sort the indexes in Morton order
    listofidxs.sort()

    # Batch query for all cubes
    dbname = self.dbcfg.tablebase + str(resolution)
    cursor = self.conn.cursor()
    sql = "SELECT zindex, cube from " + dbname + " where zindex in (%s)" 
    # creats a %s for each list element
    in_p=', '.join(map(lambda x: '%s', listofidxs))
    # replace the single %s with the in_p string
    sql = sql % in_p
    cursor.execute(sql, listofidxs)

    # xyz offset stored for later use
    lowxyz = zindex.MortonXYZ ( listofidxs[0] )

    # Get the objects and add to the cube
    for i in range ( len(listofidxs) ): 
      idx, datastring = cursor.fetchone()

      # get the data out of the compressed blob
      newstr = zlib.decompress ( datastring[:] )
      newfobj = cStringIO.StringIO ( newstr )
      inbuf.data = np.load ( newfobj )

      #add the query result cube to the bigger cube
      curxyz = zindex.MortonXYZ(int(idx))
      offsetxyz = [ curxyz[0]-lowxyz[0], curxyz[1]-lowxyz[1], curxyz[2]-lowxyz[2] ]
      outbuf.addData ( inbuf, offsetxyz )

    # need to trim down the array to size
    #  only if the dimensions are not the same
    if dim[0] % xcubedim  == 0 and\
       dim[1] % ycubedim  == 0 and\
       dim[2] % zcubedim  == 0 and\
       corner[0] % xcubedim  == 0 and\
       corner[1] % ycubedim  == 0 and\
       corner[2] % zcubedim  == 0:
      pass
    else:
      outbuf.cutout ( corner[0]%xcubedim,dim[0],\
                      corner[1]%ycubedim,dim[1],\
                      corner[2]%zcubedim,dim[2] )
    return outbuf
