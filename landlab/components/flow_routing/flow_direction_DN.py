#! /usr/env/python

"""
flow_direction_DN.py: calculates single-direction flow directions on a regular
or irregular grid.

GT Nov 2013
Modified Feb 2014
"""


import numpy
import numpy as np

from landlab import RasterModelGrid, BAD_INDEX_VALUE
from landlab.grid.raster_funcs import calculate_steepest_descent_across_cell_faces

UNDEFINED_INDEX = BAD_INDEX_VALUE


def grid_flow_directions(grid, elevations):
    """Flow directions on raster grid.

    Calculate flow directions for node elevations on a raster grid. 
    Each node is assigned a single direction, toward one of its neighboring
    nodes (or itself, if none of its neighbors are lower). There is only
    flow from one node to another if there is a negative gradient. If a
    node's steepest gradient is >= 0., then its slope is set to zero and
    its receiver node is listed as itself.

    Parameters
    ----------
    grid : RasterModelGrid
        a raster grid.
    elevations: ndarray
        Node elevations.

    Returns
    -------
    receiver : (ncells, ) ndarray
        For each cell, the node in the direction of steepest descent, or
        itself if no downstream nodes.
    steepest_slope : (ncells, ) ndarray
        The slope value in the steepest direction of flow.

    Notes
    -----
    This function considers only nodes that have four neighbors. Thus, only
    calculate flow directions and slopes for nodes that have associated
    cells.

    Examples
    --------
    This example calculates flow routing on a (4,5) raster grid with the
    following node elevations::

        5 - 5 - 5 - 5 - 5
        |   |   |   |   |
        5 - 3 - 4 - 3 - 5
        |   |   |   |   |
        5 - 1 - 2 - 2 - 5
        |   |   |   |   |
        5 - 0 - 5 - 5 - 5
        
    >>> from landlab import RasterModelGrid
    >>> mg = RasterModelGrid(4,5)
    >>> z = numpy.array([5., 0., 5., 5., 5.,
    ...                  5., 1., 2., 2., 5.,
    ...                  5., 3., 4., 3., 5.,
    ...                  5., 5., 5., 5., 5.])
    >>> recv_nodes, slope = grid_flow_directions(mg, z)

    Each node with a cell has a receiving node (although that node may be
    itself).

    >>> recv_nodes
    array([1, 6, 8, 6, 7, 8])

    All positive gradients are clipped to zero.

    >>> slope
    array([-1., -1.,  0., -2., -2., -1.])

    If a cell has no surrounding neighbors lower than itself, it is a sink.
    Use :attr:`~landlab.grid.base.ModelGrid.node_index_at_cells` to get the
    nodes associated with the cells.

    >>> sink_cells = np.where(slope >= 0)[0]
    >>> sink_cells
    array([2])
    >>> mg.node_index_at_cells[sink_cells] # Sink nodes
    array([8])

    The source/destination node pairs for the flow.

    >>> zip(mg.node_index_at_cells, recv_nodes)
    [(6, 1), (7, 6), (8, 8), (11, 6), (12, 7), (13, 8)]
    """
    slope, receiver = calculate_steepest_descent_across_cell_faces(
        grid, elevations, return_node=True)

    (sink_cell, ) = numpy.where(slope >= 0.)
    receiver[sink_cell] = grid.node_index_at_cells[sink_cell]
    slope[sink_cell] = 0.

    return receiver, slope


def flow_directions(elev, active_links, fromnode, tonode, link_slope,
                    grid=None, baselevel_nodes=None):
    """Find flow directions on a grid.

    Finds and returns flow directions for a given elevation grid. Each node is
    assigned a single direction, toward one of its N neighboring nodes (or
    itself, if none of its neighbors are lower).
    
    Parameters
    ----------
    elev : array_like
        Elevations at nodes.
    active_links : array_like
        IDs of active links.
    fromnode : array_like
        IDs of the "from" node for each link.
    tonode : array_like
        IDs of the "to" node for each link.
    link_slope : array_like
        slope of each link, defined POSITIVE DOWNHILL (i.e., a negative value
        means the link runs uphill from the fromnode to the tonode).
    baselevel_nodes : array_like, optional
        IDs of open boundary (baselevel) nodes.
    
    Returns
    -------
    receiver : ndarray
        For each node, the ID of the node that receives its flow. Defaults to
        the node itself if no other receiver is assigned.
    steepest_slope : ndarray
        The slope value (positive downhill) in the direction of flow
    sink : ndarray
        IDs of nodes that are flow sinks (they are their own receivers)
    receiver_link : ndarray
        ID of link that leads from each node to its receiver, or
        UNDEFINED_INDEX if none.
    
    Examples
    --------
    The example below assigns elevations to the 10-node example network in
    Braun and Willett (2012), so that their original flow pattern should be
    re-created.
    
    >>> z = numpy.array([2.4, 1.0, 2.2, 3.0, 0.0, 1.1, 2.0, 2.3, 3.1, 3.2])
    >>> fn = numpy.array([1,4,4,0,1,2,5,1,5,6,7,7,8,6,3,3,2,0])
    >>> tn = numpy.array([4,5,7,1,2,5,6,5,7,7,8,9,9,8,8,6,3,3])
    >>> s = z[fn] - z[tn]  # slope with unit link length, positive downhill
    >>> active_links = numpy.arange(len(fn))
    >>> r, ss, snk, rl = flow_directions(z, active_links, fn, tn, s)
    >>> r
    array([1, 4, 1, 6, 4, 4, 5, 4, 6, 7])
    >>> ss
    array([ 1.4,  1. ,  1.2,  1. ,  0. ,  1.1,  0.9,  2.3,  1.1,  0.9])
    >>> snk
    array([4])
    >>> rl[3:8]
    array([        15, 2147483647,          1,          6,          2])

    Example 2
    ---------
    This example implements a simple routing on a (4,5) raster grid with the
    following node elevations::

        5 - 5 - 5 - 5 - 5
        |   |   |   |   |
        5 - 3 - 4 - 3 - 5
        |   |   |   |   |
        5 - 1 - 2 - 2 - 5
        |   |   |   |   |
        5 - 0 - 5 - 5 - 5
        
    >>> from landlab import RasterModelGrid
    >>> mg = RasterModelGrid(4,5)
    >>> z = numpy.array([5., 0., 5., 5., 5.,
    ...                  5., 1., 2., 2., 5.,
    ...                  5., 3., 4., 3., 5.,
    ...                  5., 5., 5., 5., 5.])
    >>> fn = tn = s = None
    >>> active_links = None #these can all be dummy variables

    #>>> r, ss, snk, rl = flow_directions(z, active_links, fn, tn, s, grid=mg)
    #>>> r
    #array([ 1,  1,  1,  8,  4,  6,  1,  6,  8,  8, 11,  6,  7,  8,  13, 15, 11, 12, 13, 19])
    #>>> ss
    #array([ 5.0, 0.0, 5.0, 3.0, 0.0, 4.0, 1.0, 1.0, 0.0, 3.0, 2.0, 2.0, 2.0, 1.0, 0.0, 0.0, 2.0, 1.0, 2.0, 0.0])
    #>>> snk
    #array([ 1,  4,  8,  14, 15, 19])
    #>>> rl
    #array([         0, 2147483647,  1,         19, 2147483647,
    #                4,         17,  5, 2147483647,          7,
    #                8,         22, 23,         24,         11,
    #       2147483647,         27, 18,         29, 2147483647])

    OK, the following are rough notes on design: we want to work with just the
    active links. Ways to do this:
        - Pass active_links in as argument
        - In calling code, only refer to receiver_links for active nodes
    
    """
    
    # Setup
    num_nodes = len(elev)
    steepest_slope = numpy.zeros(num_nodes)
    receiver = numpy.arange(num_nodes)
    receiver_link = UNDEFINED_INDEX + numpy.zeros(num_nodes, dtype=int)
    
    # For each link, find the higher of the two nodes. The higher is the
    # potential donor, and the lower is the potential receiver. If the slope
    # from donor to receiver is steeper than the steepest one found so far for
    # the donor, then assign the receiver to the donor and record the new slope.
    # (Note the minus sign when looking at slope from "t" to "f").
    #
    # NOTE: MAKE SURE WE ARE ONLY LOOKING AT ACTIVE LINKS
    #THIS REMAINS A PROBLEM AS OF DEJH'S EFFORTS, MID MARCH 14.
    #overridden as part of fastscape_stream_power

    #DEJH attempting to replace the node-by-node loop, 5/28/14:
    #This is actually about the same speed on a 100*100 grid!
    try:
        raise AttributeError #hardcoded for now, until raster method works
        links_at_each_node = grid.node_activelinks()
        if not isinstance(grid, RasterModelGrid):
            raise AttributeError
    except AttributeError:
        #print "looped method"
        #do the loops, shifted from ln 96
        for i in xrange(len(fromnode)):
            f = fromnode[i]
            t = tonode[i]
            #print 'link from',f,'to',t,'with slope',link_slope[i]
            if elev[f]>elev[t] and link_slope[i]>steepest_slope[f]:
                receiver[f] = t
                steepest_slope[f] = link_slope[i]
                receiver_link[f] = active_links[i]
                #print ' flows from',f,'to',t
            elif elev[t]>elev[f] and -link_slope[i]>steepest_slope[t]:
                receiver[t] = f
                steepest_slope[t] = -link_slope[i]
                receiver_link[t] = active_links[i]
                #print ' flows from',t,'to',f
            #else:
                #print ' is flat'
    else:    
        #alternative, assuming grid structure doesn't change between steps
        #*********** not yet working! ***********
        global neighbor_nodes
        global links_list
        global one_over_sqrt_two
        try:
            elevs_array = numpy.where(neighbor_nodes!=-1, elev[neighbor_nodes], numpy.finfo(float).max)
        except NameError:
            print 'creating global neighbor list...'
            one_over_sqrt_two = 1./numpy.sqrt(2.)
            neighbor_nodes = numpy.empty((grid.number_of_active_nodes, 8), dtype=int)
            neighbor_nodes[:,:4] = grid.get_neighbor_list()[grid.active_nodes,:] #(nnodes, 4), and E,N,W,S
            neighbor_nodes[:,4:] = grid.get_diagonal_list()[grid.active_nodes,:] #NE,NW,SW,SE
            neighbor_nodes = numpy.where(neighbor_nodes!=UNDEFINED_INDEX, neighbor_nodes, -1)
            links_list = numpy.empty_like(neighbor_nodes)
            links_list[:,:4] = grid.node_activelinks().T[grid.active_nodes,:]
            links_list[:,4:].fill(UNDEFINED_INDEX)
            elevs_array = numpy.where(neighbor_nodes!=-1, elev[neighbor_nodes], numpy.finfo(float).max/1000.)
        slope_array = (elev[grid.active_nodes].reshape((grid.active_nodes.size,1)) - elevs_array)/grid.max_active_link_length()
        slope_array[:,4:] *= one_over_sqrt_two
        axis_indices = numpy.argmax(slope_array, axis=1)
        steepest_slope[grid.active_nodes] = slope_array[numpy.indices(axis_indices.shape),axis_indices]
        downslope = numpy.greater(steepest_slope, 0.)
        downslope_active = downslope[grid.active_nodes]
        receiver[downslope] = neighbor_nodes[numpy.indices(axis_indices.shape),axis_indices][0,downslope_active]
        receiver_link[downslope] = links_list[numpy.indices(axis_indices.shape),(7-axis_indices)][0,downslope_active]

            
    node_id = numpy.arange(num_nodes)

    # Optionally, handle baselevel nodes: they are their own receivers
    if baselevel_nodes is not None:
        receiver[baselevel_nodes] = node_id[baselevel_nodes]
    
    # The sink nodes are those that are their own receivers (this will normally
    # include boundary nodes as well as interior ones; "pits" would be sink
    # nodes that are also interior nodes).
    (sink, ) = numpy.where(node_id==receiver)
    
    return receiver, steepest_slope, sink, receiver_link
    
    
if __name__ == '__main__':
    import doctest
    doctest.testmod()
