# -*- coding: utf-8 -*-
""" generate_overland_flow.py 

 This component simulates overland flow using
 the 2-D numerical model of shallow-water flow
 over topography using the Bates et al. (2010)
 algorithm for storage-cell inundation modeling.

Written by Greg Tucker, Nicole Gasparini and Jordan Adams


"""

from landlab import Component, ModelParameterDictionary
import pylab
import numpy as np
from matplotlib import pyplot as plt
from math import atan, degrees
import os


_DEFAULT_INPUT_FILE = os.path.join(os.path.dirname(__file__),
                                  'overland_flow_input.txt')



class OverlandFlow(Component):
    
        
    
    '''  Landlab component that simulates overland flow using the Bates et al., (2010) approximations
of the 1D shallow water equations to be used for 2D flood inundation modeling. 
    
This component calculates discharge, depth and shear stress after some precipitation event across
any raster grid. Default input file is named "overland_flow_input.txt' and is contained in the
landlab.components.overland_flow folder.
        
    Inputs
    ------
    grid : Requires a RasterGridModel instance
        
    input_file : Contains necessary and optional inputs. If not given, default input file is used.
        - Manning's n is REQUIRED.
        - Storm duration is needed IF rainfall_duration is not passed in the initialization
        - Rainfall intensity is needed IF rainfall_intensity is not passed in the initialization
        - Model run time can be provided in initialization. If not it is set to the storm duration
        
    Constants
    ---------
    h_init : float
        Some initial depth in the channels. Default = 0.001 m
    g : float
        Gravitational acceleration, \frac{m}{s^2}
    alpha : float
        Non-dimensional time step factor from Bates et al., (2010)
    rho : integer
        Density of water, \frac{kg}{m^3}
    ten_thirds : float
        Precalculated value of \frac{10}{3} which is used in the implicit shallow water equation.
            
            
    >>> DEM_name = 'DEM_name.asc'
    >>> (rg, z) = read_esri_ascii(DEM_name) # doctest: +SKIP
    >>> of = OverlandFlow(rg) # doctest: +SKIP
       
'''
    _name = 'OverlandFlow'

    _input_var_names = set([
        'water_depth',
        'rainfall_intensity',
        'rainfall_duration',
    ])
    _output_var_names = set([
        'water_depth',
        'water_discharge',
        'shear_stress',
    ])

    _var_units = {
        'water_depth': 'm',
        'rainfall_intensity': 'm/s',
        'rainfall_duration': 's',
        'water_discharge': 'm3/s',
        'shear_stress': 'Pa',
    }

    
    def __init__(self, grid, input_file=None, **kwds):
        self.h_init = kwds.pop('h_init', 0.001)
        self.alpha = kwds.pop('alpha', 0.2)
        self.rho = kwds.pop('rho', 1000)
        self.m_n = kwds.pop('Mannings_n', 0.04)
        self.rainfall_intensity = kwds.pop('rainfall_intensity', None)
        self.rainfall_duration = kwds.pop('rainfall_duration', None)
        self.model_duration = kwds.pop('model_duration', None)        

         

        super(OverlandFlow, self).__init__(grid, **kwds)

        for name in self._input_var_names:
            if not name in self.grid.at_node:
                self.grid.add_zeros('node', name, units=self._var_units[name])

        for name in self._output_var_names:
            if not name in self.grid.at_node:
                self.grid.add_zeros('node', name, units=self._var_units[name])

        self._nodal_values = self.grid['node']   
        self._link_values = self.grid['link']
        
               
        self._water_discharge = grid.add_zeros('link', 'water_discharge', units=self._var_units['water_discharge'])                     
        self.g = 9.8               
        self.ten_thirds = 10./3.   
        self.current_time = 0.0
        self.m_n_sq = self.m_n*self.m_n 
        self.elapsed_time = 0

            
        # Create a ModelParameterDictionary instance for the inputs if they
        # are not provided as optional keyword arguments.
        
        MPD = ModelParameterDictionary()
        if input_file is None:
            input_file = _DEFAULT_INPUT_FILE
           
        
        MPD.read_from_file(input_file)    

        if self.rainfall_duration == None:
            self.rainfall_duration = MPD.read_float('RAINFALL_DURATION')
        if self.rainfall_intensity == None:
            self.rainfall_intensity = MPD.read_float('RAINFALL_INTENSITY')
        if self.model_duration == None:
            self.total_time = self.rainfall_duration
        
        
        # Set up grid arrays for state variables
        
        # Water Depth
        self.hstart = grid.zeros(centering='node') + self.h_init 
        self.h = grid.zeros(centering='node') + self.h_init     
        self.dhdt = grid.zeros(centering='cell') 

        # Discharge
        self.q = grid.zeros(centering='active_link') # unit discharge (m2/s)
        
        # Tau
        self.tau = grid.zeros(centering='node') # shear stress (Pascals)

        
    def flow_at_one_node(self, grid, z, study_node, **kwds):
        
        '''
        Outputs water depth, discharge and shear stress values through time at
        a user-selected point, defined as the "study_node" in function arguments.

        
        Inputs
        ------
        grid : Requires a RasterGridModel instance
        
        z : elevations drawn from the grid
        
        study_node : node ID for the the node at which discharge, depth and shear stress are calculated
        
        total_t : total model run time. If not provided as an argument or in the input_file, it is set to the storm_duration
        
        rainfall_intensity : rainfall intensity in m/s. If not provided as an argument, it must come from the input file.
        
        self.rainfall_duration : storm duration in seconds. If not provided as an argument, it must come from the input file.
        
        >>> study_row = 10
        >>> study_column = 10
        >>> rg.node_coords_to_id(study_row, study_column) # doctest: +SKIP
        >>> of.flow_at_one_node(rg, z, study_node, model_duration, storm_intensity, storm_duration) # doctest: +SKIP
        
        The study_node should NOT be a boundary node.
        '''

        self.q_node = grid.zeros(centering='node')

        self.interior_nodes = grid.get_active_cell_node_ids()
        self.active_links = grid.active_links

        self._water_depth = self._nodal_values['water_depth']
        self._shear_stress = self._nodal_values['shear_stress']
        self._water_discharge = self._link_values['water_discharge']
        
        self.rainfall_duration = kwds.pop('rainfall_duration', self.rainfall_duration)
        self.rainfall_intensity = kwds.pop('rainfall_intensity',self.rainfall_intensity) #
        self.interstorm_duration = kwds.pop('interstorm_duration', 0)
        
        self.model_duration = kwds.pop('model_duration', self.rainfall_duration)      
        self.z = z
        self.elapsed_time = kwds.pop('elapsed_time', 0)
        self.model_duration += self.interstorm_duration
        
        
        self.study_node = study_node

         # Get a list of the interior cells and active links for our fields...
        self.interior_nodes = grid.get_active_cell_node_ids()
        self.active_links = grid.active_links
    
        # To track discharge at the study node through time, we create initially empty
        # lists for the node discharge, tau and depth. Time is also saved to help with
        # plotting later...

        ## Time array for x-axis        
        self.time = [0]
        
        # Discharge at study node
        self.q_study = [0]

        # Shear stress at study node
        self.tau_study = [0]
        
        # Water depth at study node
        self.depth_study = [0]
        
        # Initial value in each array is zero.

        
        # Some of the calculations (like discharge) take place at links. 
        # This next bit of code identifies the neighbor node of study_node
        # That is located in the direction of max slope.
        # Then, using that node ID and the ID of the new node, the study link
        # is identified.
        
        nbr_node = grid.find_node_in_direction_of_max_slope_d4(z, study_node)
        study_link = grid.get_active_link_connecting_node_pair(study_node, nbr_node)
        
        # New "NODE" arrays are created so that link values can be put onto
        # interior nodes in the grid.
        
        self.q_node = grid.zeros(centering='node')
        self.tau_node = grid.zeros(centering='node')
        self.dqds = grid.zeros(centering='node')
        
        # Main loop
        while self.elapsed_time < self.model_duration:
        
            # Calculate time-step size for this iteration (Bates et al., eq 14)
            dtmax = self.alpha*grid.dx/np.sqrt(self.g*np.amax(self.h))
            
            dt = min(dtmax, self.model_duration)
        
            # Calculate the effective flow depth at active links. Bates et al. 2010
            # recommend using the difference between the highest water-surface
            # and the highest bed elevation between each pair of cells.
            
            zmax = grid.max_of_link_end_node_values(z) 
            w = self.h+self.z   
            wmax = grid.max_of_link_end_node_values(w) 
            hflow = wmax - zmax 
        
            # Calculate water-surface slopes across links
            water_surface_slope = grid.calculate_gradients_at_active_links(w)
       
            # Calculate the unit discharges (Bates et al., eq 11)
            self.q = (self.q-self.g*hflow*dtmax*water_surface_slope)/ \
                (1.+self.g*hflow*dtmax*0.06*0.06*abs(self.q)/(hflow**self.ten_thirds))
                    
                    
            # Calculate water-flux divergence at nodes
            self.dqds = grid.calculate_flux_divergence_at_nodes(self.q)
        
            # Update rainfall rate
            if self.elapsed_time > self.rainfall_duration:
                self.rainfall_intensity = 0.
        
            # Calculate rate of change of water depth
            self.dhdt = self.rainfall_intensity-self.dqds
        
            # Second time-step limiter (experimental): make sure you don't allow
            # water-depth to go negative
            if np.amin(self.dhdt) < 0.:
                shallowing_locations = np.where(self.dhdt<0.)
                time_to_drain = -self.h[shallowing_locations]/self.dhdt[shallowing_locations]
                dtmax2 = self.alpha*np.amin(time_to_drain)
                dt = np.min([dtmax, dtmax2])
            else:
                dt = dtmax
        
            # Update the water-depth field
            self.h[self.interior_nodes] = self.h[self.interior_nodes] + self.dhdt[self.interior_nodes]*dt

            # Get the water surface slope at across all nodes. 
            self.slopes_at_node, garbage = grid.calculate_steepest_descent_on_nodes(w, water_surface_slope)
            
            # Calculate shear stress using the study node values
            tau_temp=self.rho*self.g*self.slopes_at_node[study_node]*self.h[study_node]
            
            # Add the shear stress value at study node to the shear stress array
            self.tau_study.append(tau_temp)
            
            # Add the water depth value at study node to the water depth array
            self.depth_study.append(self.h[study_node])
            
            # Add the discharge value at study node to the discharge array
            self.q_study.append(self.q[study_link])    

            # Append new model time to the time array.
            self.time.append(self.elapsed_time)
            
            # Update model run time and print elapsed time.
            self.elapsed_time += dt
            print "elapsed time", self.elapsed_time
            
        # Update our fields...
        self._water_depth[self.interior_nodes] = self.h[self.interior_nodes]
        self._water_discharge[self.active_links] = self.q

          
    def update_at_one_point(self, grid, rainfall_duration, model_duration, rainfall_intensity, **kwds):
        '''
        The update_at_one_point() method, for now, requires our grid (which has fields associated with it),
        a new rainfall_duration, model_durationa and rainfall_intensity until I figure out some clever way to update using
        the MPD. 
        
        This function updates the overall elapsed time and passes it as an optional argument to flow_at_one_node().
        hstart is updated to be the depths from the field (_water_depth), model duration is updated to include past calls to
        flow_at_one_node() and/or update_at_one_node() depending on the past model run.
    
        Rainfall_duration is also updated so that model time will continue sequentially.
        '''
        
        # First, lets get the elapsed time from the last model run. 
        elapsed = self.elapsed_time
        
        # Set our initial depth condition to the final depth condition using fields.
        self.hstart = self._water_depth
        
        # Update the model duration and rain duration so that it begins where the last run left off.
        model_dur = model_duration + self.elapsed_time
        rain_dur = rainfall_duration+self.elapsed_time
        
        # Getting a new rainfall_intensity from our required arguments.
        intens= rainfall_intensity
        
        # Finally, call flow_at_one_node with our updated conditions.
        self.flow_at_one_node(grid, self.z, self.study_node, rainfall_duration=rain_dur, rainfall_intensity=intens, model_duration=model_dur, elapsed_time=elapsed)
        
        print '\n','\n'

            
                
    def flow_across_grid(self, grid, z, **kwds):  
        '''
        Outputs water depth, discharge and shear stress values through time at
        every point in the input grid.

        
        Inputs
        ------
        grid : Requires a RasterGridModel instance
        
        z : elevations drawn from the grid
     
        total_t : total model run time. If not provided as an argument or in the input_file, it is set to the storm_duration
        
        rainfall_intensity : rainfall intensity in m/s. If not provided as an argument, it must come from the input file.
        
        rainduration : storm duration in seconds. If not provided as an argument, it must come from the input file.
        
        '''
        
        #self.h = self.hstart

        # Interior_nodes are the nodes on which you will be calculating depth,
        # discharge and shear stress. 
        self.q_node = grid.zeros(centering='node')

        self.interior_nodes = grid.get_active_cell_node_ids()
        self.active_links = grid.active_links

        self._water_depth = self._nodal_values['water_depth']
        self._shear_stress = self._nodal_values['shear_stress']
        self._water_discharge = self._link_values['water_discharge']
        
        self.rainfall_duration = kwds.pop('rainfall_duration', self.rainfall_duration)
        self.rainfall_intensity = kwds.pop('rainfall_intensity', self.rainfall_intensity)
        self.interstorm_duration = kwds.pop('interstorm_duration', 0)
        
        self.model_duration = kwds.pop('model_duration', self.rainfall_duration)      
        self._water_depth = self._nodal_values['water_depth']
        self.z = z
        self.elapsed_time = kwds.pop('elapsed_time', 0)
        self.model_duration += self.interstorm_duration
        
        
        # And we create an array that keeps track of discharge changes through time.
        self.dqds= grid.zeros(centering='node')
        
        # Main loop...        
        while self.elapsed_time < self.model_duration:
            
            # Calculate time-step size for this iteration (Bates et al., eq 14)
            dtmax = self.alpha*grid.dx/np.sqrt(self.g*np.amax(self.h))     
        
            # Take the smaller of delt or calculated time-step
            dt = min(dtmax, self.model_duration)
        
            # Calculate the effective flow depth at active links. Bates et al. 2010
            # recommend using the difference between the highest water-surface
            # and the highest bed elevation between each pair of cells.
            
            zmax = grid.max_of_link_end_node_values(z) 
            w = self.h+self.z   
            wmax = grid.max_of_link_end_node_values(w) 
            hflow = wmax - zmax 
        
            # Calculate water-surface slopes across links
            water_surface_slope = grid.calculate_gradients_at_active_links(w)
       
            # Calculate the unit discharges (Bates et al., eq 11)
            self.q = (self.q-self.g*hflow*dtmax*water_surface_slope)/ \
                (1.+self.g*hflow*dtmax*0.06*0.06*abs(self.q)/(hflow**self.ten_thirds))
                    
            # Calculate water-flux divergence at nodes
            self.dqds = grid.calculate_flux_divergence_at_nodes(self.q,self.dqds)
            
            # Update rainfall rate
            if self.elapsed_time > self.rainfall_duration:
                self.rainfall_intensity = 0
            
            # Calculate rate of change of water depth
            self.dhdt = self.rainfall_intensity-self.dqds
            
            # Second time-step limiter (experimental): make sure you don't allow
            # water-depth to go negative
            if np.amin(self.dhdt) < 0.:
                shallowing_locations = np.where(self.dhdt<0.)
                time_to_drain = -self.h[shallowing_locations]/self.dhdt[shallowing_locations]
                dtmax2 = self.alpha*np.amin(time_to_drain)
                dt = np.min([dtmax, dtmax2, self.model_duration])
            else:
                dt = dtmax
        
            # Update the water-depth field
            self.h[self.interior_nodes] = self.h[self.interior_nodes] + self.dhdt[self.interior_nodes]*dt

            # Now we can calculate shear stress across the grid...

            # Get water surface elevation at each interior node.
            w = self.h+z   
        
            # Using water surface elevation, calculate water surface slope at each interior node.
            self.slopes_at_node, garbage = grid.calculate_steepest_descent_on_nodes(w, water_surface_slope)

            #Below if is for limiting shear stress calculations to only times when q surpasses a threshold (in this case q should be in m^3/sec)
            if self.q.any()*grid.dx> 0.2:
                # Now calculate shear stress as tau == rho * g * S * h
                self.tau = self.rho*self.g*self.slopes_at_node*self.h

            # Resetting negative shear stress values to zero..
            self.tau[np.where(self.tau<0)] = 0       

            # Update model run time.
            self.elapsed_time += dt
            print "elapsed time", self.elapsed_time
        
        # Update our fields after the loop...
        self._water_depth[self.interior_nodes] = self.h[self.interior_nodes]
        self._shear_stress[self.interior_nodes] = self.tau[self.interior_nodes]
        self._water_discharge[self.active_links] = self.q



    def update_across_grid(self, grid, rainfall_duration, model_duration, rainfall_intensity, **kwds):
        '''
        The update_across_grid() method, for now, requires our grid (which has fields associated with it),
        a new rainfall_duration, model_durationa and rainfall_intensity until I figure out some clever way to update using
        the MPD. 
        
        This function updates the overall elapsed time and passes it as an optional argument to flow_across_grid().
        hstart is updated to be the depths from the field (_water_depth), model duration is updated to include past calls to
        flow_across_grid() and/or update_across_grid() depending on the past model run.
    
        Rainfall_duration is also updated so that model time will continue sequentially.
        '''  
        # First, lets get the elapsed time from the last model run. 
        elapsed = self.elapsed_time
        
        # Set our initial depth condition to the final depth condition using fields.
        self.hstart = self._water_depth
        
        # Update the model duration and rain duration so that it begins where the last run left off.
        model_dur = model_duration + self.elapsed_time
        rain_dur = rainfall_duration+self.elapsed_time
        
        # Getting a new rainfall_intensity from our required arguments.
        intens= rainfall_intensity

        # Finally, call flow_across_grid() using our updated conditions
        self.flow_across_grid(grid, self.z, rainfall_duration=rain_dur, rainfall_intensity=intens, model_duration=model_dur, elapsed_time=elapsed)

        
    def plot_at_one_node(self):
        
        '''This method must follow a call to the flow_at_one_node() method.
        
        It plots depth, discharge and shear stress through time at the study
        node that was called in the flow_at_one_node() method.
        
           Three windows will appear after this method is called:
               1. Discharge through time is plotted as a solid blue line.
               2. Shear stress through time is plotted as a solid red line.
               3. Water depth through time is plotted as a solid cyan line.
        '''       
        plt.figure('Discharge at Study Node')
        plt.plot(self.time, self.q_study, 'b-')
        plt.legend(loc=1)
        plt.ylabel('Discharge, m^3/s')
        plt.xlabel('Time, s')
  
        plt.figure('Shear Stress at Study Node')
        plt.plot(self.time, self.tau_study, 'r-')
        plt.ylabel('Shear Stress, Pa')
        plt.xlabel('Time, s')
        plt.legend(loc=1)
        
        plt.figure('Water Depth at Study Node')
        plt.plot(self.time, self.depth_study, 'c-')
        plt.ylabel('Water Depth, m')
        plt.xlabel('Time, s')
        plt.legend(loc=1)
        plt.show()
        
    def plot_water_depths(self, grid):
         '''
            This method must follow a call to either flow_at_one_node() or the
            flow_across_grid() methods and requires the instance of the raster
            grid which was created when the DEM is read in.
            
            Water depths are calculated at each interior node in both methods.
            This takes that node vector, converts it into a raster.
            
            Presently, all nodes with water depths less than 1 cm are considered to have
            no flow/no depth and are plotted as white in the raster, using the following call:
                
                >>>  palette.set_under('w', 0.01) # doctest: +SKIP 
              
            If this value is changed, the value in the pylab.clim()
            function MUST also be changed.
            
            Additionally, the maximum value for plotted water depths is 1 m,
            using the following call:
                
                >>> pylab.clim(0.01, 1) # doctest: +SKIP
                
            Changing the value of 1 will extend the colorbar to higher values.
            
            Depths are plotted using a continuous color map, like those
            found here: http://wiki.scipy.org/Cookbook/Matplotlib/Show_colormaps
            The winter_r is simply a reverse of the winter colormap, so small values
            are shaded green while increasing values are shaded with increasingly dark
            shades of blue.
         '''
        
         plt.figure('Water Depth Raster')
         
         # This function takes the node vector and converts to a raster.
         hr = grid.node_vector_to_raster(self._water_depth)
         
         # Setting color selections - this is a green to blue continuous colorbar
        # palette = pylab.cm.winter_r
         cmap=plt.get_cmap('winter_r')#, 10)
        
        # This sets the minimum on the color bar, anything beneath the lower clim() value is set to white.
         cmap.set_under('white')
         
         # Anything beneath the float value in this argument is colored white.
         #palette.set_under('w', 0.01) ## Hardcoded 1 mm min. depth.
         
         # Creates the grid image to show.
         im2 = pylab.imshow(hr, cmap=cmap, extent=[0, grid.number_of_node_columns *grid.dx,0, grid.number_of_node_rows * grid.dx])
         
         # Sets the minimum and maximum values for the colorbar.
         #pylab.clim(0, 2) # The left value or "min" must be equal to the value in the set_under() function call above. Currently
          
                            # hardcoded to 1 m. 
         pylab.clim(vmin=0.01, vmax=0.5)

        # Creates the colorbar
         cb = pylab.colorbar(im2)

        # Labels for the colorbar and figure.
         cb.set_label('Water depth (m)', fontsize=12)
         pylab.title('Water depth')
         plt.show()
         

    def plot_shear_stress_grid(self, grid):         
        '''
            This method must follow a call to the flow_across_grid() method
            and requires the instance of the raster grid which was created
            when the DEM is read in.
            
            Shear stress is calculated at each interior node, to correspond with
            where water depths are calculated (interior nodes).
            This takes that node vector, converts it into a raster.
            
            Presently, all nodes the colorbar is blocked at intervals of ten, using
            the following function call:
                
                >>> cmap = plt.get_cmap('Spectral', 10)
                
            To change the interval at which color blocks are set, the value of 10 can
            be changed.
            
            To specify a particular range of shear stress values, the following call
            can be added to the function. Say we want the low values on the color bar to start at 10
            and increase to 100, which is currently the default setting:
                
                >>> pylab.clim(vmin=10, vmax=100) # doctest: +SKIP
                
            The colorbar is plotted using a blocked color map like those found here:
            http://wiki.scipy.org/Cookbook/Matplotlib/Show_colormaps
            The Spectral map has small values starting at shades of pink while increasing
            values go over the color spectrum from orange, to yellow, to green, to blue and
            purple as the values increase.
            '''
        # First we create a new figure window to plot within                                  
        plt.figure('Shear Stress raster')
        
        # And then we convert the shear stress node vector to raster format
        tn = grid.node_vector_to_raster(self.tau)
        
        # This call selects the color map and interval which it will be blocked by
        cmap=plt.get_cmap('Spectral', 10)
        
        # This sets the minimum on the color bar, anything beneath the lower clim() value is set to white.
        cmap.set_under('white')
        
        # Creating the grid image to show
        im2 = pylab.imshow(tn, cmap=cmap, extent=[0, grid.number_of_node_columns *grid.dx,0, grid.number_of_node_rows * grid.dx])
        
        # Creating the colorbar for the grid image
        cb = pylab.colorbar(im2)
        
        # Sets the minimum and maximum values for the colorbar.
        pylab.clim(vmin=10, vmax=100)
        
        # Set titles for the figure and colorbar.
        cb.set_label('Shear Stress (Pa)', fontsize=12)
        pylab.title('Shear Stress')
        plt.show()    
        
    def plot_slopes(self, grid):
        '''
            This method must follow a call to the flow_across_grid() method
            and requires the instance of the raster grid which was created
            when the DEM is read in.
            
            Slopes are initially calculated at active links. Then, using these 
            active link values, slopes are calculated at each interior node.
            This takes slope values from that node vector, creates a new node vector
            containing the arctangent of each original slope value, and
            converts that node vector into a raster.
            
            Presently, all nodes the colorbar is blocked at intervals of ten, using
            the following function call:
                
                >>> cmap = plt.get_cmap('RdYlGn_r', 10) # doctest: +SKIP

            To change the interval at which color blocks are set, the value of 10 can
            be changed.
            
            Presently, all nodes with slopes less than 0.01 are plotted as white in the raster, using the following call:
                
                >>> cmap.set_under('w', 0.01) # doctest: +SKIP

            If this value is changed, the value in the pylab.clim()
            function MUST also be changed.
            
            Additionally, the maximum value for plotted slopes is 50,
            using the following call:
                
                >>> pylab.clim(0.01, 50) # doctest: +SKIP
                
            To specify a particular range of slope values, the above two lines must be
            edited. The minimum (by default 0.01) must be changed in the set_under() and
            clim() calls. The maximum must be changed in the clim() call only.
                            
            The colorbar is plotted using a blocked color map like those found here:
            http://wiki.scipy.org/Cookbook/Matplotlib/Show_colormaps
            The RdYlGn_r map has small values starting at shades of green while increasing
            values go through lighter shades of green to yellow, then yellow shades to orange,
            and finally from orange to red for the highest values.
            '''
        # This creates a new figure window
        plt.figure('Water Surface Slopes')
        
        # This call selects the color map and interval which it will be blocked by
        cmap=plt.get_cmap('RdYlGn_r', 10)
        
        # Here we are creating a new node vector, and calculating slope in degrees
        # using the math library's atan() function.
        fixed_slope = grid.zeros(centering='node')
        for each in self.interior_nodes:
            fixed_slope[each] = degrees(atan(self.slopes_at_node[each]))
            
        # This converts the new slope vector (in degrees) to a raster
        fx = grid.node_vector_to_raster(fixed_slope)
        
        # All slopes beneath the minimum are shown in white.
        cmap.set_under('w', 0.01) 
        
        # Creating the grid image to show.
        im2 = pylab.imshow(fx, cmap=cmap, extent=[0, grid.number_of_node_columns *grid.dx,0, grid.number_of_node_rows * grid.dx])
        
        # Setting minimum and maximum values for the colorbar
        pylab.clim(0.01, 50) 
        
        # Creating the colorbar instance
        cb = pylab.colorbar(im2)
        
        # Set titles for the figure and the colorbar.
        cb.set_label('Slope', fontsize=12)
        pylab.title('Slope')
        plt.show()
                    
#    def plot_discharge(self,grid):
#        '''
#            This method must follow a call to the flow_across_grid() methods and
#            requires the instance of the raster grid which was created when the DEM is read in.
#            
#            Discharge is plotted using a continuous color map, like those
#            found here: http://wiki.scipy.org/Cookbook/Matplotlib/Show_colormaps
#            RdYlBu has low values at red and increases through the yellows, and maximum
#            values are shown in dark blue.
#            
#            Discharges beneath 1*10^-6 cubic meters are not shown, using the following
#            function calls:
#            
#            # All discharges beneath the minimum are shown in white.
#            >>> pylab.clim(vmin=0.000001) # doctest: +SKIP
#            >>> palette.set_under('w', 0.000001) # doctest: +SKIP
#                
#            To change this minimum, both the pylab.clim() and pylab.set_under() values must be changed.
#            
#        '''
#
#
#        # We create matrices with values entering and leaving each node.
#        grid._setup_active_inlink_and_outlink_matrices()
#        outlink = grid.node_active_outlink_matrix
#        inlink = grid.node_active_inlink_matrix
#        
#        ## And then we change them to lists for easier manipulation
#        outlink1 = outlink.tolist()
#        inlink1 =inlink.tolist()
#        #
#        ## All values in the list are tested so that
#        ## only appropriate inlink/outlink values with
#        ## correct signs are considered.
#        #newin0, newout0 = change_signs(inlink1[0], outlink1[0])
#        #newin1, newout1 = change_signs(inlink1[1], outlink1[1])
#        
#        #
#        ## New in-arrays and out-arrays are generated with the corrected inlink/outlink values
#        #in0 = np.array(newin0)
#        #in1 = np.array(newin1)
#       # out0 = np.array(newout0)
#        #out1 = np.array(newout1)
#        
#        # Net discharge changes are then calculated for each node.
#       # self.q_node = self._water_discharge[in0]+self._water_discharge[in1]+self._water_discharge[out0]+self._water_discharge[out1] 
#        
#        # But we are only interested in interior nodes. 
#        # So we create a new list and plan to populate it
#        # with discharge values only at the interior node IDs.
#        fixed_q = grid.zeros(centering='node')
#        for each in self.interior_nodes:
#            fixed_q[each] = self.q_node[each]
#            
#        # Now to actually create the figure.
#        plt.figure('DISCHARGE')
#        
#        # This function takes the discharge vector and converts it to raster.
#        hr = grid.node_vector_to_raster(fixed_q)
#        
#        # Creates a continuous color map of red -> yellow -> blue
#        palette = pylab.cm.RdYlBu
#        
#        # Creating the grid image to show.
#        im2 = pylab.imshow(hr, cmap=palette, extent=[0, grid.number_of_node_columns *grid.dx,0, grid.number_of_node_rows * grid.dx])
#        
#        # This sets the minimum on the colorbar. Discharges beneath 1*10^-6 cubic meters per second are not shown.
#        #pylab.clim(vmin=0.000001)
#        
#        # All discharges beneath the minimum are shown in white.
#        #palette.set_under('w', 0.000001)
#        
#        # Creates the colorbar for the grid image
#        cb = pylab.colorbar(im2)
#        
#        # Set titles for the colorbar and figure.
#        cb.set_label('DISCHARGE (m)', fontsize=12)
#        pylab.title('DISCHARGE')
#        plt.show()

#def change_signs(inarr1, outarr1):
#    ## We are only interested in the net
#    ## changes in discharge for plotting purposes.
#    ## Here were make sure that the signs are correct.
#    ## All inlinks should be positive.
#    ## All outlinks should be negative.
#    for i in inarr1:
#        if i < 0:
#            correctind = inarr1.index(i)
#            inarr1[correctind] == 0
#            
#    for k in outarr1:
#        if k>0:
#            correctind = inarr1.index(k)
#            outarr1[correctind] == 0
#    return inarr1, outarr1