"""
BaseMap is a generic Map class from which all other Map classes inherit from.
"""
from __future__ import absolute_import

#pylint: disable=E1101,E1121,W0404
__authors__ = ["Keith Hughitt, Steven Christe"]
__email__ = "keith.hughitt@nasa.gov"

from copy import copy
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.cm as cm
from datetime import datetime
from sunpy.wcs import wcs as wcs
from sunpy.util.util import toggle_pylab
        
"""
Questions
---------
1. map.wavelength, map.meas or? (use hv/vso/etc conventions?)
2. Are self.r_sun and radius below different? (rsun or rsun_obs for AIA?)
"""

class BaseMap(np.ndarray):
    """
    BaseMap(data, header)
    
    A spatially-aware data array based on the SolarSoft Map object
    
    Parameters
    ----------
    data : numpy.ndarray, list
        A 2d list or ndarray containing the map data
    header : dict
        A dictionary of the original image header tags

    Attributes
    ----------
    header : dict
        A dictionary representation of the image header
    date : datetime
        Image observation time
    det : str
        Detector name
    inst : str
        Instrument name
    meas : str, int
        Measurement name. For AIA this is the wavelength of image
    obs : str
        Observatory name
    rsun : float
        Radius of the sun
    exptime : float
        Exposure time of the image in seconds.
    name : str
        Nickname for the image type (e.g. "AIA 171")
    center : dict
        X and Y coordinate of the center of the map in units. Usually represents the offset between the center of the Sun and the center of the map.
    scale : dict
        Image scale along the x and y axes in units/pixel
    units : dict
        Image coordinate units along the x and y axes

    Examples
    --------
    >>> aia = sunpy.Map(sunpy.AIA_171_IMAGE)
    >>> aia.T
    AIAMap([[ 0.3125,  1.    , -1.1875, ..., -0.625 ,  0.5625,  0.5   ],
    [-0.0625,  0.1875,  0.375 , ...,  0.0625,  0.0625, -0.125 ],
    [-0.125 , -0.8125, -0.5   , ..., -0.3125,  0.5625,  0.4375],
    ..., 
    [ 0.625 ,  0.625 , -0.125 , ...,  0.125 , -0.0625,  0.6875],
    [-0.625 , -0.625 , -0.625 , ...,  0.125 , -0.0625,  0.6875],
    [ 0.    ,  0.    , -1.1875, ...,  0.125 ,  0.    ,  0.6875]])
    >>> aia.header.get('cunit1')
    'arcsec'
    >>> aia.show()
    >>> import matplotlib.cm as cm
    >>> import matplotlib.colors as colors
    >>> aia.show(cmap=cm.hot, norm=colors.Normalize(1, 2048))
    
    See Also
    --------
    numpy.ndarray Parent class for the Map object
    
    References
    ----------
    | http://docs.scipy.org/doc/numpy/reference/arrays.classes.html
    | http://docs.scipy.org/doc/numpy/user/basics.subclassing.html
    | http://docs.scipy.org/doc/numpy/reference/ufuncs.html
    | http://www.scipy.org/Subclasses

    """
    def __new__(cls, data, header=None): #pylint: disable=W0613
        """Creates a new BaseMap instance"""        
        if isinstance(data, np.ndarray):
            obj = data.view(cls)
        elif isinstance(data, list):
            obj = np.asarray(data).view(cls)
        else:
            raise TypeError('Invalid input')
        
        return obj
    
    def __init__(self, data, header=None): #pylint: disable=W0613
        """BaseMap constructor"""
        if header:
            self.header = header
            self.date = None
            self.name = None
            self.cmap = None
            self.exptime = None
            
            # Set object attributes dynamically
            for attr, value in list(self.get_properties(header).items()):
                setattr(self, attr, value)

            self.center = {
                "x": wcs.get_center(header, axis='x'),
                "y": wcs.get_center(header, axis='y')
            }
            self.scale = {
                "x": header.get('cdelt1'),
                "y": header.get('cdelt2')
            }
            self.units = {
                "x": wcs.get_units(header, axis='x'), 
                "y": wcs.get_units(header, axis='y')
            }
            self.rsun = wcs.get_solar_limb(header)
            
    def __array_finalize__(self, obj):
        """Finishes instantiation of the new map object"""
        if obj is None:
            return

        if hasattr(obj, 'header'):
            # Preserve object properties
            properties = self.get_properties(obj.header)
            for attr, value in list(properties.items()):
                setattr(self, attr, getattr(obj, attr, value))
                
            for x in ['header', 'center', 'scale', 'units', 'rsun']:
                setattr(self, x, getattr(obj, x, value))
        
    def __array_wrap__(self, out_arr, context=None):
        """Returns a wrapped instance of a Map object"""
        return np.ndarray.__array_wrap__(self, out_arr, context)
                
    def __add__(self, other):
        """Add two maps. Currently does not take into account the alignment  
        between the two maps."""
        result = np.ndarray.__add__(self, other)
        
        return result
    
    def __getitem__(self, key):
        """Overiding indexing operation to ensure that header is updated"""
        if isinstance(key, tuple) and type(key[0]) is slice:
            x_range = [key[1].start, key[1].stop]
            y_range = [key[0].start, key[0].stop]

            return self.submap(y_range, x_range, units="pixels")
        else:
            return np.ndarray.__getitem__(self, key)
    
    def __sub__(self, other):
        """Subtract two maps. Currently does not take into account the alignment
        between the two maps.
        
        numpy dtype nums:
            1    int8
            2    uint8
            3    int16
            4    uint16
        """
        from matplotlib import colors
        
        # if data is stored as unsigned, cast up (e.g. uint8 => int16)
        if self.dtype.kind == "u":
            dtype = "int%d" % (int(self.dtype.name[4:]) * 2)
            self = self.astype(np.dtype(dtype))
        if other.dtype.kind == "u":
            dtype = "int%d" % (int(other.dtype.name[4:]) * 2)
            other = other.astype(np.dtype(dtype))

        result = np.ndarray.__sub__(self, other)
            
        def norm():
            mean = result.mean()
            std = result.std()
            vmin = max(result.min(), mean - 6 * std)
            vmax = min(result.max(), mean + 6 * std)
            
            return colors.Normalize(vmin, vmax)
        
        result.norm = norm
        result.cmap = cm.gray #@UndefinedVariable 
        
        return result
    
    def std(self, *args, **kwargs):
        """overide np.ndarray.std()"""
        return np.array(self, copy=False, subok=False).std(*args, **kwargs)
    
    @classmethod
    def parse_file(cls, filepath):
        """Reads in a map file and returns a header and data array"""
        from sunpy.io import read_file
        from sunpy.map.header import MapHeader
        
        data, dict_header = read_file(filepath)
        
        header = MapHeader(dict_header)
        
        return header, data
    
    @classmethod
    def read(cls, filepath):
        """Map class factory
    
        Attempts to determine the type of data associated with input and returns
        an instance of either the generic BaseMap class or a subclass of BaseMap
        such as AIAMap, EUVIMap, etc.
        
        Parameters
        ----------
        filepath : string
            Path to a valid FITS or JPEG 2000 file of a type supported by SunPy.
            
        Returns
        -------
        out : Map
            Returns a Map instance for the particular type of data loaded.
        """
        header, data = cls.parse_file(filepath)
 
        if cls.__name__ is not "BaseMap":
            return cls(data, header)

        for cls in BaseMap.__subclasses__():
            if cls.is_datasource_for(header):
                return cls(data, header)
        raise UnrecognizedDataSouceError("File header not recognized by SunPy.")
    
    @classmethod
    def get_properties(cls, header=None): #pylint: disable=W0613
        """Returns default map properties""" 
        return {
            'cmap': cm.gray,
            'date': datetime.today(),
            'det': "None",
            'inst': "None",
            'meas': "None",
            'obs': "None",
            'exptime': "None", 
            'name': "Default Map",
            'r_sun': None
        }
    
    @property
    def xrange(self):
        """Return the X range of the image in arcsec from edge to edge."""        
        xmin = self.center['x'] - self.shape[1] / 2 * self.scale['x']
        xmax = self.center['x'] + self.shape[1] / 2 * self.scale['x']
        return [xmin, xmax]
    
    @property
    def yrange(self):
        """Return the Y range of the image in arcsec from edge to edge."""
        ymin = self.center['y'] - self.shape[0] / 2 * self.scale['y']
        ymax = self.center['y'] + self.shape[0] / 2 * self.scale['y']
        return [ymin, ymax]
    
    def data_to_pixel(self, value, dim):
        """Convert pixel-center data coordinates to pixel values"""
        if dim not in ['x', 'y']:
            raise ValueError("Invalid dimension. Must be one of 'x' or 'y'.")
        size = self.shape[dim == 'x'] # 1 if dim == 'x', 0 if dim == 'y'.
        
        return (value - self.center[dim]) / self.scale[dim] + ((size - 1) / 2.)
    
    def resample(self, dimensions, method='linear'):
        """Returns a new Map that has been resampled up or down
        
        Arbitrary resampling of the Map to new dimension sizes.
        
        Uses the same parameters and creates the same co-ordinate lookup points
        as IDL''s congrid routine, which apparently originally came from a 
        VAX/VMS routine of the same name.
        
        Parameters
        ----------
        dimensions : tuple
            Dimensions that new Map should have.
            Note: the first argument corresponds to the 'x' axis and the second
            argument corresponds to the 'y' axis.
        method : {'neighbor' | 'nearest' | 'linear' | 'spline'}
            Method to use for resampling interpolation.
                * neighbor - Closest value from original data
                * nearest and linear - Uses n x 1-D interpolations using
                  scipy.interpolate.interp1d
                * spline - Uses ndimage.map_coordinates
    
        Returns
        -------
        out : Map
            A new Map which has been resampled to the desired dimensions.
        
        References
        ----------
        | http://www.scipy.org/Cookbook/Rebinning (Original source, 2011/11/19)
        """
        from sunpy.image import resample

        # Note: because the underlying ndarray is transposed in sense when
        #   compared to the Map, the ndarray is transposed, resampled, then
        #   transposed back
        # Note: "center" defaults to True in this function because data
        #   coordinates in a Map are at pixel centers

        # Make a copy of the original data and perform resample
        data = resample(np.asarray(self).copy().T, dimensions,
                        method, center = True)
        
        # Update image scale and number of pixels
        header = self.header.copy()

        # Note that 'x' and 'y' correspond to 1 and 0 in self.shape, respectively
        scale_factor_x = (float(self.shape[1]) / dimensions[0])
        scale_factor_y = (float(self.shape[0]) / dimensions[1])
        
        header['naxis1'] = int(dimensions[0])
        header['naxis2'] = int(dimensions[1])
        header['cdelt1'] *= scale_factor_x
        header['cdelt2'] *= scale_factor_y
        header['crpix1'] = (dimensions[0] + 1) / 2.
        header['crval1'] = self.center['x']
        header['crpix2'] = (dimensions[1] + 1) / 2.
        header['crval2'] = self.center['y']

        return self.__class__(data.T, header)

    def submap(self, range_a, range_b, units="data"):
        """Returns a submap of the map with the specified range
        
        Parameters
        ----------
        range_a : list
            The range of the Map to select across either the x axis.
        range_b : list
            The range of the Map to select across either the y axis.
        units : {'data' | 'pixels'}, optional
            The units for the supplied ranges.
            
        Returns
        -------
        out : Map
            A new map instance is returned representing to specified sub-region.
        
        Examples
        --------
        >>> aia.submap([-5,5],[-5,5])
        AIAMap([[ 341.3125,  266.5   ,  329.375 ,  330.5625,  298.875 ],
        [ 347.1875,  273.4375,  247.4375,  303.5   ,  305.3125],
        [ 322.8125,  302.3125,  298.125 ,  299.    ,  261.5   ],
        [ 334.875 ,  289.75  ,  269.25  ,  256.375 ,  242.3125],
        [ 273.125 ,  241.75  ,  248.8125,  263.0625,  249.0625]])
        
        >>> aia.submap([0,5],[0,5], units='pixels')
        AIAMap([[ 0.3125, -0.0625, -0.125 ,  0.    , -0.375 ],
        [ 1.    ,  0.1875, -0.8125,  0.125 ,  0.3125],
        [-1.1875,  0.375 , -0.5   ,  0.25  , -0.4375],
        [-0.6875, -0.3125,  0.8125,  0.0625,  0.1875],
        [-0.875 ,  0.25  ,  0.1875,  0.    , -0.6875]])
        """
        if units is "data":
            #x_pixels = [self.data_to_pixel(elem, 'x') for elem in range_a]
            x_pixels = [np.ceil(self.data_to_pixel(range_a[0], 'x')),
                        np.floor(self.data_to_pixel(range_a[1], 'x')) + 1]
            #y_pixels = [self.data_to_pixel(elem, 'y') for elem in range_b]
            y_pixels = [np.ceil(self.data_to_pixel(range_b[0], 'y')),
                        np.floor(self.data_to_pixel(range_b[1], 'y')) + 1]
        elif units is "pixels":
            x_pixels = range_a
            y_pixels = range_b
        else:
            raise ValueError(
                "Invalid unit. Must be one of 'data' or 'pixels'")

        # Make a copy of the header with updated centering information        
        header = self.header.copy()
        header['crpix1'] = header['crpix1'] - x_pixels[0]
        header['crpix2'] = header['crpix2'] - y_pixels[0]
        header['naxis1'] = x_pixels[1] - x_pixels[0]
        header['naxis2'] = y_pixels[1] - y_pixels[0]

#        self.center = {
#            "x": wcs.get_center(header, axis='x'),
#            "y": wcs.get_center(header, axis='y')
#        }

        # Get ndarray representation of submap
        data = np.asarray(self)[y_pixels[0]:y_pixels[1], 
                                x_pixels[0]:x_pixels[1]]

        return self.__class__(data.copy(), header)
   
    @toggle_pylab
    def plot(self, overlays=None, draw_limb=True, gamma=None, draw_grid=False, 
             **matplot_args):
        """Plots the map object using matplotlib
        
        Parameters
        ----------
        overlays : list
            List of overlays to include in the plot
        draw_limb : bool
            Whether the solar limb should be plotted.
        draw_grid : bool
            Whether solar meridians and parallels
        grid_spacing : float
            Set the spacing between meridians and parallels for the grid
        gamma : float
            Gamma value to use for the color map
        **matplot_args : dict
            Matplotlib Any additional imshow arguments that should be used
            when plotting the image.
        """
        if overlays is None:
            overlays = []
        if draw_limb:
            overlays = overlays + [self._draw_limb]
        # TODO: need to be able to pass the grid spacing to _draw_grid from the 
        # plot command.
        if draw_grid:
            overlays = overlays + [self._draw_grid]
        # Create a figure and add title and axes
        fig = plt.figure()
        
        axes = fig.add_subplot(111)
        axes.set_title("%s %s" % (self.name, self.date))
        
        if self.header.get('CTYPE1') == 'HPLN-TAN':
            axes.set_xlabel('X-position [' + self.units['x'] + ']')
        
        if self.header.get('CTYPE1') == 'HG':
            axes.set_xlabel('Longitude [' + self.units['x'] + ']')
        
        if self.header.get('CTYPE2') == 'HPLT-TAN':
            axes.set_ylabel('Y-position [' + self.units['y'] + ']')

        if self.header.get('CTYPE2') == 'HG':
            axes.set_ylabel('Latitude [' + self.units['y'] + ']')

        # Determine extent
        extent = self.xrange + self.yrange

        # Matplotlib arguments
        params = {
            "cmap": self.cmap,
            "norm": self.norm()
        }
        params.update(matplot_args)
        if gamma is not None:
            params['cmap'] = copy(params['cmap'])
            params['cmap'].set_gamma(gamma)

        im = axes.imshow(self, origin='lower', extent=extent, **params)
        fig.colorbar(im)
        
        for overlay in overlays:
            fig, axes = overlay(fig, axes)
        return fig
    
    @toggle_pylab
    def plot_simple(self, overlays=None, draw_limb=False, gamma=None, 
                    draw_grid=False, **matplot_args):
        """Plots the map object using matplotlib
        
        Parameters
        ----------
        overlays : list
            List of overlays to include in the plot
        draw_limb : bool
            Whether the solar limb should be plotted.
        draw_grid : bool
            Whether solar meridians and parallels
        grid_spacing : float
            Set the spacing between meridians and parallels for the grid
        gamma : float
            Gamma value to use for the color map
        **matplot_args : dict
            Matplotlib Any additional imshow arguments that should be used
            when plotting the image.
        """
        if overlays is None:
            overlays = []
        if draw_limb:
            overlays = overlays + [self._draw_limb]

        # TODO: need to be able to pass the grid spacing to _draw_grid from the 
        # plot command.
        if draw_grid:
            overlays = overlays + [self._draw_grid]

        fig = plt.figure(frameon=False)
        
        axes = plt.Axes(fig, [0., 0., 1., 1.])
        axes.set_axis_off()
        fig.add_axes(axes)

        # Determine extent
        extent = self.xrange + self.yrange

        # Matplotlib arguments
        params = {
            "cmap": self.cmap,
            "norm": self.norm()
        }
        params.update(matplot_args)
        
        if gamma is not None:
            params['cmap'] = copy(params['cmap'])
            params['cmap'].set_gamma(gamma)

        axes.imshow(self, origin='lower', extent=extent, aspect='normal', **params)
        
        for overlay in overlays:
            fig, axes = overlay(fig, axes)
        return fig
    
    def norm(self):
        """Default normalization method"""
        return None
    
    def show(self, overlays=None, draw_limb=False, gamma=1.0, **matplot_args):
        """Displays map on screen. Arguments are same as plot()."""
        self.plot(overlays, draw_limb, gamma, **matplot_args).show()
        
    def _draw_limb(self, fig, axes):
        """Draws a circle representing the solar limb"""
        circ = patches.Circle([0, 0], radius=self.rsun, fill=False, 
                              color='white')
        axes.add_artist(circ)
        return fig, axes
    
    def _draw_grid(self, fig, axes, grid_spacing=20):
        """Draws a grid over the surface of the Sun"""
        # define the number of points for each latitude or longitude line
        num_points = 20
        hg_longitude_deg = np.linspace(-90, 90, num=num_points)
        hg_latitude_deg = np.arange(-90, 90, grid_spacing)
    
        # draw the latitude lines
        for lat in hg_latitude_deg:
            hg_latitude_deg_mesh, hg_longitude_deg_mesh = np.meshgrid(
                lat * np.ones(num_points), hg_longitude_deg)
            x, y = wcs.convert_hg_hpc(self.header, hg_longitude_deg_mesh, 
                                      hg_latitude_deg_mesh, units='arcsec')
            axes.plot(x, y, color='white', linestyle='dotted')
        
        hg_longitude_deg = np.arange(-90, 90, grid_spacing)
        hg_latitude_deg = np.linspace(-90, 90, num=num_points)
    
        # draw the longitude lines
        for lon in hg_longitude_deg:
            hg_longitude_deg_mesh, hg_latitude_deg_mesh = np.meshgrid(
                lon * np.ones(num_points), hg_latitude_deg)
            x, y = wcs.convert_hg_hpc(self.header, hg_longitude_deg_mesh, 
                                      hg_latitude_deg_mesh, units='arcsec')
            axes.plot(x, y, color='white', linestyle='dotted')        
        
        return fig, axes
    
class UnrecognizedDataSouceError(ValueError):
    """Exception to raise when an unknown datasource is encountered"""
    pass
    