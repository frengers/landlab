#! /usr/bin/env python

import numpy as np
try:
    import matplotlib.pyplot as plt
except ImportError:
    import warnings
    warnings.warn('matplotlib not found', ImportWarning)


def assert_array_size_matches(array, size, msg=None):
    if size != array.size:
        if msg is None:
            msg = '%d != %d' % (size, array.size)
        raise ValueError(msg)


def imshow_node_grid(grid, values, **kwds):
    """
    Prepares a map view of data over all nodes in the grid.
    Method can take any of the same **kwds as imshow().
    
    requires:
    grid: the grid
    values: the values on the nodes (length nnodes)
    """
    assert_array_size_matches(values, grid.number_of_nodes,
            'number of values does not match number of nodes')

    data = values.view()
    data.shape = grid.shape

    _imshow_grid_values(grid, data, **kwds)


def imshow_active_node_grid(grid, values, other_node_val='min', **kwds):
    """
    Prepares a map view of data over only the active (i.e., not closed) nodes
    in the grid.
    Method can take any of the same **kwds as imshow().
    
    requires:
    grid: the grid
    values: the values on the open, active nodes OR the values on all nodes in
    the grid. If the latter is provided, this method will only plot the active
    subset.
    
    If *other_node_val* is set, this is the value that will be displayed for
    all nodes that are not active. It defaults to 'min', which is the minimum
    value found on any active node in the grid.
    """
    active_nodes = grid.active_nodes
    try:
        assert_array_size_matches(values, active_nodes.size,
            'number of values does not match number of active nodes')
    except ValueError:
        assert_array_size_matches(values[active_nodes], active_nodes.size,
            'number of values does not match number of active nodes')
        values_to_use = values[active_nodes]
    else:
        values_to_use = values
    
    data = np.zeros(grid.number_of_nodes)
    if other_node_val!='min':
        data.fill(other_node_val)
    else:
        data.fill(np.min(values_to_use))
    data[active_nodes] = values_to_use.flat
    data.shape = grid.shape

    _imshow_grid_values(grid, data, **kwds)

def imshow_core_node_grid(grid, values, other_node_val='min', **kwds):
    """
    Prepares a map view of data over only the core nodes
    in the grid.
    Method can take any of the same **kwds as imshow().
    
    requires:
    grid: the grid
    values: the values on the core nodes OR the values on all nodes in
    the grid. If the latter is provided, this method will only plot the core
    subset.
    
    If *other_node_val* is set, this is the value that will be displayed for
    all nodes that are not core. It defaults to 'min', which is the minimum
    value found on any core node in the grid.
    """
    active_nodes = grid.core_nodes
    try:
        assert_array_size_matches(values, active_nodes.size,
            'number of values does not match number of active nodes')
    except ValueError:
        assert_array_size_matches(values[active_nodes], active_nodes.size,
            'number of values does not match number of active nodes')
        values_to_use = values[active_nodes]
    else:
        values_to_use = values
    
    data = np.zeros(grid.number_of_nodes)
    if other_node_val!='min':
        data.fill(other_node_val)
    else:
        data.fill(np.min(values_to_use))
    data[active_nodes] = values_to_use.flat
    data.shape = grid.shape

    _imshow_grid_values(grid, data, **kwds)


def imshow_cell_grid(grid, values, **kwds):
    """
    Prepares a map view of data over all cells in the grid.
    Method can take any of the same **kwds as imshow().
    
    requires:
    grid: the grid
    values: the values on the cells OR the values on all nodes in the grid, from
    which the cell values will be extracted.
    """
    cells = grid.node_index_at_cells
    try:
        assert_array_size_matches(values, cells.size,
            'number of values does not match number of cells')
    except ValueError:
        assert_array_size_matches(values[cells], cells.size,
            'number of values does not match number of cells')
        values_to_use = values[cells]
    else:
        values_to_use = values
        
    data = values_to_use.view()
    data.shape = (grid.shape[0] - 2, grid.shape[1] - 2)

    _imshow_grid_values(grid, data, **kwds)


def imshow_active_cell_grid(grid, values, other_node_val='min', **kwds):
    """
    Prepares a map view of data over all active (i.e., core and open boundary)
    cells in the grid.
    Method can take any of the same **kwds as imshow().
    
    requires:
    grid: the grid
    values: the values on the active cells OR the values on all nodes in the 
    grid, from which the active cell values will be extracted.
    
    If *other_node_val* is set, this is the value that will be displayed for
    all cells that are not active. It defaults to 'min', which is the minimum
    value found on any active cell in the grid.
    """

    active_cells = grid.node_index_at_active_cells
    try:
        assert_array_size_matches(values, active_cells.size,
            'number of values does not match number of active cells')
    except ValueError:
        assert_array_size_matches(values[active_cells], active_cells.size,
            'number of values does not match number of active cells')
        values_to_use = values[active_cells]
    else:
        values_to_use = values

    data = np.zeros(grid.number_of_nodes)
    if other_node_val!='min':
        data.fill(other_node_val)
    else:
        data.fill(np.min(values_to_use))
    data[active_cells] = values_to_use
    data = data[grid.node_index_at_cells]
    data.shape = (grid.shape[0] - 2, grid.shape[1] - 2)

    _imshow_grid_values(grid, data, **kwds)


def _imshow_grid_values(grid, values, var_name=None, var_units=None,
                        grid_units=(None, None), symmetric_cbar=False,
                        cmap='jet', limits=None):
    if len(values.shape) != 2:
        raise ValueError('dimension of values must be 2 (%s)' % values.shape)

    y = np.arange(values.shape[0] + 1) - grid.dx * .5
    x = np.arange(values.shape[1] + 1) - grid.dx * .5

    kwds = dict(cmap=cmap)
    if limits is None:
        if symmetric_cbar:
            (var_min, var_max) = (values.min(), values.max())
            limit = max(abs(var_min), abs(var_max))
            (kwds['vmin'], kwds['vmax']) = (- limit, limit)
    else:
        (kwds['vmin'], kwds['vmax']) = (limits[0], limits[1])


    plt.pcolormesh(x, y, values, **kwds)

    plt.gca().set_aspect(1.)
    plt.autoscale(tight=True)

    plt.colorbar()

    plt.xlabel('X (%s)' % grid_units[1])
    plt.ylabel('Y (%s)' % grid_units[0])

    if var_name is not None:
        plt.title('%s (%s)' % (var_name, var_units))

    #plt.show()


def imshow_grid(grid, values, **kwds):
    show = kwds.pop('show', False)
    values_at = kwds.pop('values_at', 'node')

    if values_at == 'node':
        imshow_node_grid(grid, values, **kwds)
    elif values_at == 'cell':
        imshow_cell_grid(grid, values, **kwds)
    elif values_at == 'active_node':
        imshow_active_node_grid(grid, values, **kwds)
    elif values_at == 'active_cell':
        imshow_active_cell_grid(grid, values, **kwds)
    else:
        raise TypeError('value location %s not understood' % values_at)

    if show:
        plt.show()


def imshow_field(field, name, **kwds):
    values_at = kwds['values_at']
    imshow_grid(field, field.field_values(values_at, name), var_name=name,
                var_units=field.field_units(values_at, name), **kwds)

###
# Added by Sai Nudurupati 29Oct2013 
# This function is exactly the same as imshow_grid but this function plots
# arrays spread over cells rather than nodes
##DEJH: Sai, this is duplicating what we already had I think. I deprecated it.
""".. deprecated:: 0.6
    Use :meth:`imshow_active_cell_grid`, above, instead.
"""

def imshow_active_cells(grid, values, var_name=None, var_units=None,
                grid_units=(None, None), symmetric_cbar=False,
                cmap='jet'):
    data = values.view()
    data.shape = (grid.shape[0]-2, grid.shape[1]-2)

    y = np.arange(data.shape[0]) - grid.dx * .5
    x = np.arange(data.shape[1]) - grid.dx * .5

    if symmetric_cbar:
        (var_min, var_max) = (data.min(), data.max())
        limit = max(abs(var_min), abs(var_max))
        limits = (-limit, limit)
    else:
        limits = (None, None)

    plt.pcolormesh(x, y, data, vmin=limits[0], vmax=limits[1], cmap=cmap)

    plt.gca().set_aspect(1.)
    plt.autoscale(tight=True)

    plt.colorbar()

    plt.xlabel('X (%s)' % grid_units[1])
    plt.ylabel('Y (%s)' % grid_units[0])

    if var_name is not None:
        plt.title('%s (%s)' % (var_name, var_units))

    plt.show()

###
